"""Use cases against an in-memory repository port."""

from copy import deepcopy

import pytest

from circuit_shift.application.ports import BoardRecord, BoardRepository
from circuit_shift.application.use_cases import (
    BoardConflictError,
    BoardNotFoundError,
    ReadBoard,
    RotateBoard,
    StartBoard,
)
from circuit_shift.domain import Board, Cell, Event, TileRotated


class MemoryBoardRepository:
    """In-memory BoardRepository with an injectable rejected save."""

    def __init__(self) -> None:
        """Start empty, accepting saves."""
        self.records: dict[str, BoardRecord] = {}
        self.conflict = False

    def add(self, board: Board) -> None:
        """Store a copy of the board."""
        self.records[board.board_id] = BoardRecord(deepcopy(board), ())

    def get(self, board_id: str) -> BoardRecord | None:
        """Return a copy of the stored record."""
        record = self.records.get(board_id)
        return deepcopy(record) if record is not None else None

    def save(self, board: Board, events: tuple[Event, ...], expected_moves: int) -> bool:
        """Save when the moves match and saves are not rejected."""
        record = self.records[board.board_id]
        if self.conflict or record.board.moves_used != expected_moves:
            return False
        self.records[board.board_id] = BoardRecord(deepcopy(board), (*record.events, *events))
        return True


def test_req_usecase_start_read_and_rotate_preserve_event_history() -> None:
    """REQ-USECASE: start, read and rotate keep the event history."""
    repository: BoardRepository = MemoryBoardRepository()
    board = StartBoard(repository, lambda: "board-1").execute()
    rotation = RotateBoard(repository).execute(board.board_id, Cell(0, 1))

    stored = ReadBoard(repository).execute(board.board_id)
    assert stored.board.board_id == "board-1"
    assert stored.board.moves_used == 1
    assert stored.board.tiles[Cell(0, 1)].orientation.quarter_turns == 1
    assert stored.events == rotation
    assert isinstance(stored.events[0], TileRotated)


def test_req_usecase_unknown_board_and_invalid_rotation_do_not_save() -> None:
    """REQ-USECASE: unknown boards and invalid rotations store nothing."""
    repository = MemoryBoardRepository()
    board = StartBoard(repository, lambda: "board-1").execute()
    rotate = RotateBoard(repository)

    with pytest.raises(BoardNotFoundError):
        rotate.execute("missing", Cell(0, 1))
    with pytest.raises(BoardNotFoundError):
        ReadBoard(repository).execute("missing")
    with pytest.raises(ValueError, match="fixed"):
        rotate.execute(board.board_id, Cell(0, 0))

    stored = ReadBoard(repository).execute(board.board_id)
    assert stored.board.moves_used == 0
    assert stored.events == ()


def test_req_usecase_stale_write_is_reported_as_a_conflict() -> None:
    """REQ-USECASE: a rejected save is reported as a conflict."""
    repository = MemoryBoardRepository()
    board = StartBoard(repository, lambda: "board-1").execute()
    repository.conflict = True

    with pytest.raises(BoardConflictError):
        RotateBoard(repository).execute(board.board_id, Cell(0, 1))

    stored = ReadBoard(repository).execute(board.board_id)
    assert stored.board.moves_used == 0
    assert stored.events == ()
