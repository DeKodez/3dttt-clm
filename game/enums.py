"""Game enums — CellState, Player, FaceStatus, GamePhase."""

from enum import Enum

class CellState(Enum):
    """Represents the state of a single cell on a face."""

    EMPTY = " "
    X = "X"
    O = "O"


class Player(Enum):
    """Represents a player in the game."""

    X = "X"
    O = "O"

    @property
    def symbol(self) -> str:
        """Returns the player's symbol as a string."""
        return self.value

    @property
    def cell_state(self) -> CellState:
        """Returns the CellState corresponding to this player."""
        return CellState.X if self == Player.X else CellState.O

    def next(self) -> "Player":
        """Returns the other player."""
        return Player.O if self == Player.X else Player.X


class FaceStatus(Enum):
    """Represents the current status of a face (3x3 board)."""

    IN_PROGRESS = "in_progress"
    WON_X = "won_x"
    WON_O = "won_o"
    DRAW = "draw"


class GamePhase(Enum):
    """Represents the overall phase of the game."""

    PLAYING = "playing"
    FINISHED = "finished"
