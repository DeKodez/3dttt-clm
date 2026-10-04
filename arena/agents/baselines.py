"""Baseline agents: random legal moves and a simple tactical heuristic."""

import random
from typing import Any, Optional

from arena.agents.base import Agent
from arena.engine import Engine, Move
from game.enums import CellState, Player

LINES: list[list[tuple[int, int]]] = []
for _r in range(3):
    LINES.append([(_r, _c) for _c in range(3)])
for _c in range(3):
    LINES.append([(_r, _c) for _r in range(3)])
LINES.append([(0, 0), (1, 1), (2, 2)])
LINES.append([(0, 2), (1, 1), (2, 0)])


def _would_win(cells, row: int, col: int, player: Player) -> bool:
    """True if placing `player` at (row, col) completes 3 in a row."""
    mark = player.cell_state
    for line in LINES:
        if (row, col) not in line:
            continue
        values = [cells[r][c] for r, c in line]
        if any(value not in (CellState.EMPTY, mark) for value in values):
            continue
        if values.count(mark) == 2:
            return True
    return False


def _heuristic(engine: Engine, move: Move, rng: random.Random) -> float:
    """Score a quiet move: center/corner bias, own lines, enemy lines, face lead."""
    face_index, row, col = move
    face = engine.faces[face_index]
    player = engine.current_player
    opponent = player.next()
    score = 0.0

    if (row, col) == (1, 1):
        score += 4.0
    elif (row + col) % 2 == 0:
        score += 2.0

    for line in LINES:
        if (row, col) not in line:
            continue
        values = [face.cells[r][c] for r, c in line]
        own = values.count(player.cell_state)
        enemy = values.count(opponent.cell_state)
        if enemy == 0:
            score += own * 3.0
        if own == 0:
            score -= enemy * 4.0

    own_cells = sum(
        1 for r in range(3) for c in range(3) if face.cells[r][c] == player.cell_state
    )
    enemy_cells = sum(
        1 for r in range(3) for c in range(3) if face.cells[r][c] == opponent.cell_state
    )
    score += (own_cells - enemy_cells) * 0.5
    score += rng.random() * 0.5
    return score


class RandomAgent(Agent):
    """Chooses uniformly among legal moves."""

    def __init__(self, name: str = "random", seed: Optional[int] = None) -> None:
        super().__init__(name)
        self._rng = random.Random(seed)

    def _choose(self, engine: Engine) -> tuple[Optional[Move], dict[str, Any]]:
        moves = engine.legal_moves()
        if not moves:
            raise RuntimeError("no legal moves available")
        return self._rng.choice(moves), {"strategy": "random"}


class TacticalAgent(Agent):
    """Wins when possible, blocks immediate threats, otherwise plays a heuristic."""

    def __init__(self, name: str = "tactical", seed: Optional[int] = None) -> None:
        super().__init__(name)
        self._rng = random.Random(seed)

    def _choose(self, engine: Engine) -> tuple[Optional[Move], dict[str, Any]]:
        moves = engine.legal_moves()
        if not moves:
            raise RuntimeError("no legal moves available")

        player = engine.current_player
        opponent = player.next()
        placements = [move for move in moves if move[1] >= 0] or moves

        for move in placements:
            face_index, row, col = move
            if _would_win(engine.faces[face_index].cells, row, col, player):
                return move, {"strategy": "win"}

        for move in placements:
            face_index, row, col = move
            if _would_win(engine.faces[face_index].cells, row, col, opponent):
                return move, {"strategy": "block"}

        best = max(placements, key=lambda move: _heuristic(engine, move, self._rng))
        return best, {"strategy": "positional"}
