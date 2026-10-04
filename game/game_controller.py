"""GameController — orchestrates the 6-face game flow."""

import random

from game.board import Board
from game.enums import GamePhase, Player
from game.faces import DEFAULT_FACE, rotation_target
from game.score_tracker import ScoreTracker


class GameController:
    """Central orchestrator for the 3D tic-tac-toe game.

    Manages 6 Board instances, global turn order, delegates scoring
    to ScoreTracker, and determines when the game ends.
    Only one face is in play at a time: every accepted move advances
    ``active_face`` according to the cube-rotation rules in game.faces.
    Knows nothing about UI or rendering.
    """

    NUM_FACES = 6

    def __init__(self, nukes_enabled: bool = False) -> None:
        self.faces: list[Board] = [Board() for _ in range(self.NUM_FACES)]
        self.current_player: Player = Player.X
        self.score_tracker: ScoreTracker = ScoreTracker()
        self.phase: GamePhase = GamePhase.PLAYING
        self.active_face: int = DEFAULT_FACE
        self.nukes_enabled: bool = nukes_enabled
        self.nukes_used: dict[Player, bool] = {
            Player.X: False,
            Player.O: False,
        }

    def make_move(self, face_index: int, row: int, col: int) -> bool:
        """Attempt to place the current player's mark on the face in play.

        Delegates to the Board, records a win if the face was just won,
        rotates the cube per the cell played, switches turn, and checks
        if the game is over. Moves on any other face are rejected.

        Args:
            face_index: Index of the face (0-5); must equal active_face.
            row: Row index (0-2).
            col: Column index (0-2).

        Returns:
            True if the move was accepted, False otherwise.
        """
        if self.phase != GamePhase.PLAYING:
            return False

        if not (0 <= face_index < self.NUM_FACES):
            return False

        if face_index != self.active_face:
            return False

        face = self.faces[face_index]
        was_locked = face.is_locked()

        if not face.place(row, col, self.current_player):
            return False

        just_locked = not was_locked and face.is_locked()

        # If this move just locked the face (win), record the score
        if just_locked and face.winner is not None:
            self.score_tracker.record_win(face.winner)

        self._advance_active_face(face_index, row, col, just_locked)
        self._switch_turn()
        self._check_game_over()
        return True

    def _advance_active_face(
        self, face_index: int, row: int, col: int, face_locked: bool
    ) -> None:
        """Move the cube to the face in play for the next turn.

        The cell played decides the rotation: middle stays, side cells
        rotate to the adjacent face, corners to the opposite face. A
        locked target face leaves the cube where it is. If the played
        face was just completed and the rotation yields no movement,
        the cube moves to a random unfinished face — deterministic for
        the position, so replayed games pick the same face.
        """
        target = rotation_target(face_index, row, col)
        if target is not None and not self.faces[target].is_locked():
            self.active_face = target
            return

        if not face_locked:
            self.active_face = face_index
            return

        unfinished = [
            index
            for index in range(self.NUM_FACES)
            if not self.faces[index].is_locked()
        ]
        if not unfinished:
            self.active_face = face_index
            return

        seed = ",".join(
            [str(face_index), str(row), str(col)]
            + [str(index) for index in unfinished]
        )
        rng = random.Random(seed)
        self.active_face = rng.choice(unfinished)

    def nuke_face(self, face_index: int) -> bool:
        """Nuke (reset) the face in play.

        The nuke wipes the active board back to empty; the face stays
        in play. It consumes the current player's one-time nuke and
        ends their turn.

        Args:
            face_index: Index of the face (0-5); must equal active_face.

        Returns:
            True if the nuke was used, False if it was blocked.
        """
        if not self.nukes_enabled:
            return False

        if self.phase != GamePhase.PLAYING:
            return False

        if self.nukes_used[self.current_player]:
            return False

        if not (0 <= face_index < self.NUM_FACES):
            return False

        if face_index != self.active_face:
            return False

        face = self.faces[face_index]
        if face.is_locked():
            return False

        face.reset()
        self.nukes_used[self.current_player] = True
        self._switch_turn()
        return True

    def can_nuke(self, face_index: int) -> bool:
        """Return True if the current player can nuke the face in play."""
        if not self.nukes_enabled:
            return False
        if self.phase != GamePhase.PLAYING:
            return False
        if self.nukes_used[self.current_player]:
            return False
        if not (0 <= face_index < self.NUM_FACES):
            return False
        if face_index != self.active_face:
            return False
        return not self.faces[face_index].is_locked()

    def skip_turn(self) -> bool:
        """Skip the current player's turn (e.g. timer expired).

        Returns:
            True if the turn was skipped, False if the game isn't playing.
        """
        if self.phase != GamePhase.PLAYING:
            return False
        self._switch_turn()
        return True

    def get_face(self, index: int) -> Board:
        """Return the Board at the given index."""
        return self.faces[index]

    def is_game_over(self) -> bool:
        """Return True if the game has finished."""
        return self.phase == GamePhase.FINISHED

    def get_result_text(self) -> str:
        """Return a human-readable result string."""
        return self.score_tracker.get_result_text()

    def _switch_turn(self) -> None:
        """Toggle the current player."""
        self.current_player = self.current_player.next()

    def _check_game_over(self) -> None:
        """If all 6 faces are locked, set the game phase to FINISHED."""
        if all(face.is_locked() for face in self.faces):
            self.phase = GamePhase.FINISHED
