"""Engine — headless match state built on the existing GameController."""

from typing import Optional

from game.enums import CellState, FaceStatus, Player
from game.game_controller import GameController
from game.faces import NUM_FACES
from ui.constants import FACE_LABELS

Move = tuple[int, int, int]

NUKE_ROW = -1  # sentinel row/col marking a nuke action


class Engine:
    """Thin adapter over GameController for agent play.

    Adds move enumeration, JSON serialization, and result reporting
    while delegating every rule decision to the existing game logic.
    Nukes are enabled: the move (face, NUKE_ROW, NUKE_ROW) wipes the
    face in play, once per player per game.
    """

    def __init__(self) -> None:
        self.controller = GameController(nukes_enabled=True)
        self.move_log: list[Move] = []

    @property
    def faces(self):
        """The six Board instances."""
        return self.controller.faces

    @property
    def current_player(self) -> Player:
        """The player whose turn it is."""
        return self.controller.current_player

    @property
    def active_face(self) -> int:
        """Index of the face currently in play."""
        return self.controller.active_face

    @property
    def last_move(self) -> Optional[Move]:
        """The most recent move, if any."""
        return self.move_log[-1] if self.move_log else None

    @staticmethod
    def nuke_move(face_index: int) -> Move:
        """The move tuple representing a nuke on the given face."""
        return (face_index, NUKE_ROW, NUKE_ROW)

    @staticmethod
    def is_nuke(move: Optional[Move]) -> bool:
        """True if the move tuple is a nuke action."""
        return move is not None and move[1] == NUKE_ROW

    def _can_nuke(self, face_index: int) -> bool:
        """True if the current player may nuke this face right now."""
        if not self.controller.can_nuke(face_index):
            return False
        face = self.faces[face_index]
        return any(
            face.get_cell(row, col) != CellState.EMPTY
            for row in range(3)
            for col in range(3)
        )

    def legal_moves(self) -> list[Move]:
        """All moves available on the face in play, in stable order.

        Includes the nuke action (sentinel coordinates NUKE_ROW) when
        the face in play has marks to wipe and the current player has
        not spent their one-time nuke yet.
        """
        face_index = self.active_face
        face = self.faces[face_index]
        moves: list[Move] = []
        if not face.is_locked():
            for row in range(3):
                for col in range(3):
                    if face.get_cell(row, col) == CellState.EMPTY:
                        moves.append((face_index, row, col))
        if self._can_nuke(face_index):
            moves.append(self.nuke_move(face_index))
        return moves

    def is_legal(self, move: Optional[Move]) -> bool:
        """Return True if the move is currently valid for the current player."""
        if move is None:
            return False
        face_index, row, col = move
        if not 0 <= face_index < NUM_FACES:
            return False
        if col == NUKE_ROW:
            return self.is_nuke(move) and self._can_nuke(face_index)
        if self.is_nuke(move):
            return False
        if face_index != self.active_face:
            return False
        face = self.faces[face_index]
        if face.is_locked() or not (0 <= row <= 2 and 0 <= col <= 2):
            return False
        return face.get_cell(row, col) == CellState.EMPTY

    def make_move(self, move: Move) -> bool:
        """Apply a move (or nuke) if legal; returns whether it was accepted."""
        if self.is_nuke(move):
            if not self.controller.nuke_face(move[0]):
                return False
            self.move_log.append(move)
            return True
        face_index, row, col = move
        if not self.controller.make_move(face_index, row, col):
            return False
        self.move_log.append(move)
        return True

    def is_game_over(self) -> bool:
        """True once every face is locked."""
        return self.controller.is_game_over()

    def scores(self) -> dict[Player, int]:
        """Current face-win totals per player."""
        return self.controller.score_tracker.get_scores()

    def winner(self) -> Optional[Player]:
        """The match winner, or None for a tie (only meaningful when over)."""
        return self.controller.score_tracker.get_winner()

    def result_label(self) -> str:
        """Human-readable result, e.g. 'Player X wins 4-2!'."""
        return self.controller.get_result_text()

    def clone(self) -> "Engine":
        """A deep copy of the current position, replayed on a fresh engine."""
        clone = Engine()
        for move in self.move_log:
            if not clone.make_move(move):
                raise RuntimeError(f"clone replay failed at {move}")
        return clone

    def snapshot(self) -> dict:
        """JSON-ready view of the full match state for the live UI."""
        return {
            "faces": [
                {
                    "name": FACE_LABELS[index],
                    "status": face.status.value,
                    "winner": face.winner.symbol if face.winner else None,
                    "cells": [
                        [cell.value for cell in row] for row in face.cells
                    ],
                    "winning_cells": (
                        [list(cell) for cell in face.winning_cells]
                        if face.winning_cells
                        else None
                    ),
                }
                for index, face in enumerate(self.faces)
            ],
            "scores": {
                player.symbol: count
                for player, count in self.scores().items()
            },
            "current_player": self.current_player.symbol,
            "active_face": self.active_face,
            "nukes_enabled": self.controller.nukes_enabled,
            "nukes_used": {
                player.symbol: used
                for player, used in self.controller.nukes_used.items()
            },
            "game_over": self.is_game_over(),
            "move_count": len(self.move_log),
        }
