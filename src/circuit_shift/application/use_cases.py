# Copyright 2026 TM-59
"""Framework-independent board use cases."""

from typing import TYPE_CHECKING
from uuid import uuid4

from circuit_shift.domain import Board, Cell, Event, starter_board

if TYPE_CHECKING:
    from collections.abc import Callable

    from circuit_shift.application.ports import BoardRecord, BoardRepository


class BoardNotFoundError(LookupError):
    """No board exists with the requested identity."""


class BoardConflictError(RuntimeError):
    """The board changed after it was read."""


class StartBoard:
    """Create the starter board with a new identity and store it."""

    def __init__(
        self, repository: BoardRepository, board_id_factory: Callable[[], str] | None = None
    ) -> None:
        """Use `repository` for storage and `id_factory` for new identities."""
        self._repository = repository
        self._board_id_factory = board_id_factory or (lambda: str(uuid4()))

    def execute(self) -> Board:
        """Start a board and return it."""
        board = starter_board(self._board_id_factory())
        self._repository.add(board)
        return board


class ReadBoard:
    """Read a stored board and its events."""

    def __init__(self, repository: BoardRepository) -> None:
        """Use `repository` to read boards."""
        self._repository = repository

    def execute(self, board_id: str) -> BoardRecord:
        """Return the stored board with identity `board_id`."""
        record = self._repository.get(board_id)
        if record is None:
            raise BoardNotFoundError(board_id)
        return record


class RotateBoard:
    """Rotate one tile of a stored board."""

    def __init__(self, repository: BoardRepository) -> None:
        """Use `repository` to read and save boards."""
        self._repository = repository

    def execute(self, board_id: str, cell: Cell) -> tuple[Event, ...]:
        """Rotate the tile at `cell`, save, and return the events."""
        record = self._repository.get(board_id)
        if record is None:
            raise BoardNotFoundError(board_id)
        expected_moves = record.board.moves_used
        events = record.board.rotate(cell)
        if not self._repository.save(record.board, events, expected_moves):
            raise BoardConflictError(board_id)
        return events
