"""Circuit Routing: tiles, the board aggregate, its events and connectivity.

Standard library only. A graph puzzle, not a simulation of electrical current.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping


QUARTER_TURNS = 4  # a full turn

# Error messages, named once so that every raise states which rule refused the value.
CELL_NOT_WHOLE = "row and column are non-negative integers"
ORIENTATION_RANGE = "an orientation is 0, 1, 2 or 3 quarter-turns"
TILE_WITHOUT_PORT = "a tile has at least one port"
PORT_NOT_DIRECTION = "ports are north, east, south or west"
TILE_WITHOUT_ROLE = "a tile needs a role and an orientation"
BOARD_WITHOUT_IDENTITY = "a board needs an identity"
BOARD_TOO_SMALL = "a board has at least one row and one column"
BUDGET_NOT_POSITIVE = "the move budget is a positive integer"
MOVES_OUT_OF_RANGE = "moves used lie between zero and the budget"
BOARD_NOT_CELL_MAP = "a board maps cells to tiles"
TILE_OFF_BOARD = "every tile lies on the board"
SOURCE_COUNT = "a board has exactly one source"
LAMP_MISSING = "a board has at least one lamp"
CELL_REQUIRED = "a cell is required"
NO_TILE = "there is no tile at that cell"
TILE_FIXED = "source and lamp tiles are fixed"
BOARD_FINISHED = "the board is {}"


class Port(Enum):
    NORTH = "north"
    EAST = "east"
    SOUTH = "south"
    WEST = "west"

    @property
    def clockwise(self) -> Port:
        return _CLOCKWISE[self]

    @property
    def opposite(self) -> Port:
        return _CLOCKWISE[_CLOCKWISE[self]]

    @property
    def step(self) -> tuple[int, int]:
        """Row and column change towards the neighbour on this side."""
        return _STEP[self]


_CLOCKWISE = {
    Port.NORTH: Port.EAST,
    Port.EAST: Port.SOUTH,
    Port.SOUTH: Port.WEST,
    Port.WEST: Port.NORTH,
}
_STEP = {Port.NORTH: (-1, 0), Port.EAST: (0, 1), Port.SOUTH: (1, 0), Port.WEST: (0, -1)}


class Role(Enum):
    SOURCE = "source"
    WIRE = "wire"
    LAMP = "lamp"


class BoardState(Enum):
    ACTIVE = "active"
    SOLVED = "solved"
    EXHAUSTED = "exhausted"


class BoardFinishedError(Exception):
    """A solved or exhausted board accepts no rotation."""


class InvalidRotationError(ValueError):
    """The cell is off the board, empty, or holds a fixed tile."""


@dataclass(frozen=True, slots=True)
class Cell:
    """Zero-based row and column."""

    row: int
    col: int

    def __post_init__(self) -> None:
        for value in (self.row, self.col):
            if type(value) is not int or value < 0:
                raise ValueError(CELL_NOT_WHOLE)

    def towards(self, port: Port) -> tuple[int, int]:
        d_row, d_col = port.step
        return self.row + d_row, self.col + d_col


@dataclass(frozen=True, slots=True)
class Orientation:
    """Clockwise quarter-turns from the base shape: 0, 1, 2 or 3."""

    quarter_turns: int = 0

    def __post_init__(self) -> None:
        if type(self.quarter_turns) is not int or not 0 <= self.quarter_turns < QUARTER_TURNS:
            raise ValueError(ORIENTATION_RANGE)

    def turned(self) -> Orientation:
        return Orientation((self.quarter_turns + 1) % QUARTER_TURNS)


@dataclass(frozen=True, slots=True)
class Tile:
    """Base ports, an orientation and a role. Rotating gives a new tile."""

    base_ports: frozenset[Port]
    role: Role = Role.WIRE
    orientation: Orientation = field(default_factory=Orientation)

    def __post_init__(self) -> None:
        if not isinstance(self.base_ports, frozenset) or not self.base_ports:
            raise ValueError(TILE_WITHOUT_PORT)
        if any(not isinstance(port, Port) for port in self.base_ports):
            raise TypeError(PORT_NOT_DIRECTION)
        if not isinstance(self.role, Role) or not isinstance(self.orientation, Orientation):
            raise TypeError(TILE_WITHOUT_ROLE)

    @property
    def ports(self) -> frozenset[Port]:
        """The base ports after the tile's quarter-turns."""
        ports = self.base_ports
        for _ in range(self.orientation.quarter_turns):
            ports = frozenset(port.clockwise for port in ports)
        return ports

    def rotated(self) -> Tile:
        return Tile(self.base_ports, self.role, self.orientation.turned())


class Connectivity:
    """Pure domain service: which cells the source reaches."""

    @staticmethod
    def powered(tiles: Mapping[Cell, Tile]) -> frozenset[Cell]:
        sources = [cell for cell, tile in tiles.items() if tile.role is Role.SOURCE]
        seen: set[Cell] = set(sources)
        frontier = list(sources)
        while frontier:
            cell = frontier.pop()
            for port in tiles[cell].ports:
                row, col = cell.towards(port)
                if row < 0 or col < 0:
                    continue  # borders never wrap
                neighbour = Cell(row, col)
                other = tiles.get(neighbour)
                # a connection needs the facing port on the other side as well
                if other is None or neighbour in seen or port.opposite not in other.ports:
                    continue
                seen.add(neighbour)
                frontier.append(neighbour)
        return frozenset(seen)


@dataclass(frozen=True, slots=True)
class TileRotated:
    board_id: str
    cell: Cell
    orientation: Orientation
    move: int


@dataclass(frozen=True, slots=True)
class BoardSolved:
    board_id: str
    moves_used: int


Event = TileRotated | BoardSolved


@dataclass(slots=True)
class Board:
    """Aggregate: tiles on a rectangle, a move budget, moves used and the derived state."""

    board_id: str
    rows: int
    cols: int
    tiles: dict[Cell, Tile]
    move_budget: int
    moves_used: int = 0

    def __post_init__(self) -> None:
        self._check_shape()
        self.tiles = dict(self.tiles)
        self._check_tiles()

    def _check_shape(self) -> None:
        if not self.board_id:
            raise ValueError(BOARD_WITHOUT_IDENTITY)
        for size in (self.rows, self.cols):
            if type(size) is not int or size < 1:
                raise ValueError(BOARD_TOO_SMALL)
        if type(self.move_budget) is not int or self.move_budget < 1:
            raise ValueError(BUDGET_NOT_POSITIVE)
        if type(self.moves_used) is not int or not 0 <= self.moves_used <= self.move_budget:
            raise ValueError(MOVES_OUT_OF_RANGE)

    def _check_tiles(self) -> None:
        for cell, tile in self.tiles.items():
            if not isinstance(cell, Cell) or not isinstance(tile, Tile):
                raise TypeError(BOARD_NOT_CELL_MAP)
            if cell.row >= self.rows or cell.col >= self.cols:
                raise ValueError(TILE_OFF_BOARD)
        roles = [tile.role for tile in self.tiles.values()]
        if roles.count(Role.SOURCE) != 1:
            raise ValueError(SOURCE_COUNT)
        if roles.count(Role.LAMP) < 1:
            raise ValueError(LAMP_MISSING)

    @property
    def powered(self) -> frozenset[Cell]:
        return Connectivity.powered(self.tiles)

    @property
    def lamps(self) -> frozenset[Cell]:
        return frozenset(cell for cell, tile in self.tiles.items() if tile.role is Role.LAMP)

    @property
    def state(self) -> BoardState:
        if self.lamps <= self.powered:
            return BoardState.SOLVED  # solving on the last move wins before exhaustion
        if self.moves_used >= self.move_budget:
            return BoardState.EXHAUSTED
        return BoardState.ACTIVE

    def rotate(self, cell: Cell) -> tuple[Event, ...]:
        """Turn the wire at `cell` clockwise once. Returns the events that happened.

        Nothing changes when the board is finished or the command is invalid.
        """
        if self.state is not BoardState.ACTIVE:
            raise BoardFinishedError(BOARD_FINISHED.format(self.state.value))
        if not isinstance(cell, Cell):
            raise InvalidRotationError(CELL_REQUIRED)
        tile = self.tiles.get(cell)
        if tile is None:
            raise InvalidRotationError(NO_TILE)
        if tile.role is not Role.WIRE:
            raise InvalidRotationError(TILE_FIXED)
        turned = tile.rotated()
        self.tiles[cell] = turned
        self.moves_used += 1
        events: list[Event] = [
            TileRotated(self.board_id, cell, turned.orientation, self.moves_used)
        ]
        if self.lamps <= self.powered:
            events.append(BoardSolved(self.board_id, self.moves_used))
        return tuple(events)


def tile(ports: str, role: Role = Role.WIRE, turns: int = 0) -> Tile:
    """Build a tile from port letters: "ne" gives a wire with base ports north and east."""
    letters = {"n": Port.NORTH, "e": Port.EAST, "s": Port.SOUTH, "w": Port.WEST}
    return Tile(frozenset(letters[letter] for letter in ports), role, Orientation(turns))


def starter_board(board_id: str = "starter") -> Board:
    """Return the first fixed board: 3 x 3, one source, two lamps, six moves.

    The source at the top left opens east. One lamp sits on the right edge and opens
    north; the other at the bottom left opens east. Four rotations solve it (the tests
    find that minimum by trying every combination): the T once, the corner twice, the
    middle bar once. Two tiles are decoys.
    """
    tiles = {
        Cell(0, 0): tile("e", Role.SOURCE),
        Cell(0, 1): tile("nes"),
        Cell(0, 2): tile("ne"),
        Cell(1, 0): tile("ns"),
        Cell(1, 1): tile("ew"),
        Cell(1, 2): tile("n", Role.LAMP),
        Cell(2, 0): tile("e", Role.LAMP),
        Cell(2, 1): tile("nw"),
        Cell(2, 2): tile("ne"),
    }
    return Board(board_id, 3, 3, tiles, move_budget=6)
