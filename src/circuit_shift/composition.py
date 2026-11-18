"""Composition root: wire the use cases to SQLite and build the FastAPI app."""

import os
from typing import TYPE_CHECKING

from fastapi import FastAPI

from circuit_shift.application.use_cases import ReadBoard, RotateBoard, StartBoard
from circuit_shift.infrastructure.repository import SQLiteBoardRepository
from circuit_shift.presentation.health import router

if TYPE_CHECKING:
    from pathlib import Path

    from circuit_shift.application.ports import BoardRepository


class BoardUseCases:
    """The three board use cases sharing one repository."""

    def __init__(self, repository: BoardRepository) -> None:
        """Build every use case on `repository`."""
        self.start = StartBoard(repository)
        self.read = ReadBoard(repository)
        self.rotate = RotateBoard(repository)


def build_board_use_cases(path: str | Path | None = None) -> BoardUseCases:
    """Wire the use cases to the SQLite repository at `path`."""
    database_path = path or os.environ.get(
        "CIRCUIT_SHIFT_DB_PATH", "test-results/circuit-shift.sqlite3"
    )
    return BoardUseCases(SQLiteBoardRepository(database_path))


def create_app() -> FastAPI:
    """Build the FastAPI application with its routes."""
    app = FastAPI(title="Circuit Shift", docs_url=None, redoc_url=None)
    app.state.board_use_cases = build_board_use_cases()
    app.include_router(router)
    return app
