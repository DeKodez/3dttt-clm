"""Board — manages a single 3x3 tic-tac-toe face."""

from typing import Optional

from game.enums import CellState, FaceStatus, Player


class Board:
    """A single 3x3 tic-tac-toe face.

    Responsible for managing its grid of cells, detecting wins and draws,
    and locking itself when the face is resolved. Knows nothing about
    other faces, scoring, or UI.
    """

    def __init__(self) -> None:
        self.cells: list[list[CellState]] = [
            [CellState.EMPTY for _ in range(3)] for _ in range(3)
        ]
        self.status: FaceStatus = FaceStatus.IN_PROGRESS
        self.winner: Optional[Player] = None
        self.winning_cells: Optional[list[tuple[int, int]]] = None

    def place(self, row: int, col: int, player: Player) -> bool:
        """Place a mark on the given cell.

        Args:
            row: Row index (0-2).
            col: Column index (0-2).
            player: The player making the move.

        Returns:
            True if the move was accepted, False if invalid
            (cell occupied, face locked, or out of bounds).
        """
        if self.is_locked():
            return False

        if not (0 <= row <= 2 and 0 <= col <= 2):
            return False

        if self.cells[row][col] != CellState.EMPTY:
            return False

        self.cells[row][col] = player.cell_state
        self._update_status()
        return True

    def reset(self) -> None:
        """Wipe the board back to its initial empty state.

        Only meaningful for in-progress boards (caller should check).
        """
        self.cells = [
            [CellState.EMPTY for _ in range(3)] for _ in range(3)
        ]
        self.status = FaceStatus.IN_PROGRESS
        self.winner = None
        self.winning_cells = None

    def is_locked(self) -> bool:
        """Returns True if this face is no longer playable (won or drawn)."""
        return self.status != FaceStatus.IN_PROGRESS

    def get_cell(self, row: int, col: int) -> CellState:
        """Returns the state of a specific cell."""
        return self.cells[row][col]

    def _update_status(self) -> None:
        """Check for a winner or draw and update status accordingly."""
        winner = self._check_winner()
        if winner is not None:
            self.winner = winner
            self.status = (
                FaceStatus.WON_X if winner == Player.X else FaceStatus.WON_O
            )
        elif self._is_full():
            self.status = FaceStatus.DRAW

    def _check_winner(self) -> Optional[Player]:
        """Check all rows, columns, and diagonals for 3-in-a-row.

        Returns:
            The winning Player, or None if no winner yet.
        """
        lines = []

        # Rows
        for r in range(3):
            lines.append([(r, 0), (r, 1), (r, 2)])

        # Columns
        for c in range(3):
            lines.append([(0, c), (1, c), (2, c)])

        # Diagonals
        lines.append([(0, 0), (1, 1), (2, 2)])
        lines.append([(0, 2), (1, 1), (2, 0)])

        for line in lines:
            states = [self.cells[r][c] for r, c in line]
            if states[0] != CellState.EMPTY and states[0] == states[1] == states[2]:
                self.winning_cells = line
                return Player.X if states[0] == CellState.X else Player.O

        return None

    def _is_full(self) -> bool:
        """Returns True if all 9 cells are occupied."""
        return all(
            self.cells[r][c] != CellState.EMPTY
            for r in range(3)
            for c in range(3)
        )
