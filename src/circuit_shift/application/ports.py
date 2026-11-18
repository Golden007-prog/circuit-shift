# Copyright 2026 TM-59
"""Persistence ports used by the application layer."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from circuit_shift.domain import Board, Event


@dataclass(frozen=True, slots=True)
class BoardRecord:
    """A stored board with its ordered events."""

    board: Board
    events: tuple[Event, ...]


class BoardRepository(Protocol):
    """Port for storing boards; `save` succeeds only if no move was saved since the read."""

    def add(self, board: Board) -> None:
        """Store a new board with no events."""

    def get(self, board_id: str) -> BoardRecord | None:
        """Return the board and its events, or None when it does not exist."""

    def save(self, board: Board, events: tuple[Event, ...], expected_moves: int) -> bool:
        """Write the board and append `events` if its moves still equal `expected_moves`."""
