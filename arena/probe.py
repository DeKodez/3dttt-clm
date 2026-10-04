"""Understanding probes — quiz agents on the rules and on reading positions."""

import random
from dataclasses import dataclass
from time import perf_counter
from typing import Callable, Optional

from arena.agents.base import Agent
from arena.agents.text import RULES, move_phrase, state_text
from arena.engine import Engine, Move
from game.enums import CellState, Player
from ui.constants import FACE_LABELS

SCRIPTED_OPENING: list[Move] = [
    (1, 1, 0),
    (2, 2, 0),
    (5, 0, 2),
    (2, 2, 2),
    (5, 1, 2),
    (4, 2, 0),
    (1, 0, 0),
    (4, 2, 2),
    (1, 0, 2),
    (4, 0, 0),
    (1, 2, 0),
    (4, 1, 0),
]


@dataclass
class QuizItem:
    """One question with a known ground-truth answer."""

    id: str
    category: str
    state: str
    instructions: str
    options: dict[str, Optional[str]]
    expected: str
    note: str = ""

    def to_dict(self) -> dict:
        """JSON-ready view (state omitted, it is large and repetitive)."""
        return {
            "id": self.id,
            "category": self.category,
            "instructions": self.instructions,
            "expected": self.expected,
            "note": self.note,
        }


@dataclass
class QuizResult:
    """One graded answer."""

    id: str
    category: str
    expected: str
    choice: Optional[str]
    correct: bool
    latency_ms: float
    confidence: Optional[float]
    error: Optional[str] = None

    def to_dict(self) -> dict:
        """JSON-ready view."""
        return {
            "id": self.id,
            "category": self.category,
            "expected": self.expected,
            "choice": self.choice,
            "correct": self.correct,
            "latency_ms": round(self.latency_ms, 2),
            "confidence": self.confidence,
            "error": self.error,
        }


def scenario_engine() -> Engine:
    """Fixed opening: Front won by X, Back won by O, Right in play, X to move."""
    engine = Engine()
    for move in SCRIPTED_OPENING:
        if not engine.make_move(move):
            raise RuntimeError(f"scripted move failed: {move}")
    return engine


def move_wins_face(engine: Engine, move: Move, player: Player) -> bool:
    """True if playing `move` right now immediately wins a face for `player`."""
    if engine.current_player != player:
        return False
    clone = engine.clone()
    before = clone.scores()[player]
    return clone.make_move(move) and clone.scores()[player] > before


def _options(rng: random.Random, values: list[str]) -> dict[str, Optional[str]]:
    """Build a criteria map with shuffled option order to reduce position bias."""
    keys = list(values)
    rng.shuffle(keys)
    return {key: None for key in keys}


def build_quiz(seed: int = 7) -> list[QuizItem]:
    """Rules questions plus board-reading questions with computed ground truth."""
    rng = random.Random(seed)
    items: list[QuizItem] = []

    def add(
        item_id: str,
        category: str,
        state: str,
        instructions: str,
        values: list[str],
        expected: str,
        note: str = "",
    ) -> None:
        items.append(
            QuizItem(
                id=item_id,
                category=category,
                state=state,
                instructions=instructions,
                options=_options(rng, values),
                expected=expected,
                note=note,
            )
        )

    add(
        "rules_faces",
        "rules",
        RULES,
        "How many faces does the cube have?",
        ["6", "4", "9", "12"],
        "6",
    )
    add(
        "rules_first",
        "rules",
        RULES,
        "Who moves first at the start of every game?",
        ["X", "O", "It is chosen randomly each game", "The player with fewer face wins"],
        "X",
    )
    add(
        "rules_turns",
        "rules",
        RULES,
        "How do turns work across the six faces?",
        [
            "Turns alternate globally: X then O then X, no matter which face is in play",
            "Each face has its own independent turn order",
            "The player who completes a face moves again",
            "Both players move at the same time",
        ],
        "Turns alternate globally: X then O then X, no matter which face is in play",
    )
    add(
        "rules_active_face",
        "rules",
        RULES,
        "How many faces can be played at any moment?",
        [
            "Exactly one: the face that is in play",
            "All faces that are not yet locked",
            "Any two faces of the player's choice",
            "All six faces",
        ],
        "Exactly one: the face that is in play",
    )
    add(
        "rules_rotation_middle",
        "rules",
        RULES,
        "After a player marks the middle cell of the face in play, play moves where?",
        [
            "Nowhere: the same face stays in play",
            "To the opposite face",
            "To the face of the opponent's choice",
            "To a random face",
        ],
        "Nowhere: the same face stays in play",
    )
    add(
        "rules_rotation_side",
        "rules",
        RULES,
        "After a player marks a side (edge-middle) cell, which face comes into play?",
        [
            "The face that shares that edge, rotated 90 degrees",
            "The opposite face, rotated 180 degrees",
            "The same face stays in play",
            "A random unfinished face",
        ],
        "The face that shares that edge, rotated 90 degrees",
    )
    add(
        "rules_rotation_corner",
        "rules",
        RULES,
        "After a player marks a corner cell, which face comes into play?",
        [
            "The opposite face, rotated 180 degrees",
            "The face sharing the nearest edge, rotated 90 degrees",
            "The same face stays in play",
            "A random unfinished face",
        ],
        "The opposite face, rotated 180 degrees",
    )
    add(
        "rules_rotation_locked",
        "rules",
        RULES,
        "What happens if the rotation would move play to a face that is already completed?",
        [
            "Play stays on the current face",
            "The nearest unfinished face becomes the face in play",
            "The completing player chooses a new face",
            "The game ends immediately",
        ],
        "Play stays on the current face",
    )
    add(
        "rules_nuke",
        "rules",
        RULES,
        "What does a nuke do?",
        [
            "Each player may wipe every mark on the face in play once per game",
            "It removes one opponent mark anywhere on the cube",
            "It resets all six faces to empty",
            "It blocks the opponent's next move",
        ],
        "Each player may wipe every mark on the face in play once per game",
    )
    add(
        "rules_lock_win",
        "rules",
        RULES,
        "What happens to a face when a player gets 3 in a row on it?",
        [
            "That face is locked immediately and can never be played again",
            "The face resets to empty and play continues",
            "The opponent gets an extra move somewhere else",
            "Play continues on that face until all 9 cells are full",
        ],
        "That face is locked immediately and can never be played again",
    )
    add(
        "rules_lock_draw",
        "rules",
        RULES,
        "What happens when all 9 cells of a face are filled without 3 in a row?",
        [
            "The face is a draw and is locked",
            "The face resets to empty and play continues",
            "The face stays open for future moves",
            "The player who filled the last cell wins that face",
        ],
        "The face is a draw and is locked",
    )
    add(
        "rules_end",
        "rules",
        RULES,
        "When does the game end?",
        [
            "When all 6 faces are locked",
            "As soon as one player wins 2 faces",
            "After 20 total moves",
            "When a player has no legal move",
        ],
        "When all 6 faces are locked",
    )
    add(
        "rules_overall",
        "rules",
        RULES,
        "How is the overall winner of the game decided?",
        [
            "The player who won the most faces",
            "The player who placed the most marks",
            "The player who won the Top face",
            "The player who made the final move",
        ],
        "The player who won the most faces",
    )
    add(
        "rules_win_count",
        "rules",
        RULES,
        "How many face wins are needed to win the game?",
        [
            "Strictly more face wins than the opponent when all faces are locked",
            "At least 2 face wins",
            "At least 4 face wins",
            "All 6 faces must be won",
        ],
        "Strictly more face wins than the opponent when all faces are locked",
    )

    engine = scenario_engine()
    state = state_text(engine)
    scores = engine.scores()
    active_face = engine.active_face
    active_label = FACE_LABELS[active_face]
    locked = [index for index, face in enumerate(engine.faces) if face.is_locked()]
    locked_labels = [FACE_LABELS[index] for index in locked]
    active_empty = sum(
        1
        for row in range(3)
        for col in range(3)
        if engine.faces[active_face].get_cell(row, col) == CellState.EMPTY
    )
    placements = [move for move in engine.legal_moves() if move[1] >= 0]
    winning_move = next(
        (move for move in placements if move_wins_face(engine, move, Player.X)),
        None,
    )
    quiet_move = next(
        (
            move
            for move in placements
            if not move_wins_face(engine, move, Player.X)
        ),
        None,
    )
    off_face_move = next(
        (
            (face_index, row, col)
            for face_index in range(6)
            if face_index not in locked and face_index != active_face
            for row in range(3)
            for col in range(3)
            if engine.faces[face_index].get_cell(row, col) == CellState.EMPTY
        ),
        None,
    )

    def score_options(expected: str) -> list[str]:
        """Four face-win score options, guaranteed to contain the truth."""
        ordered = [expected]
        for candidate in ("X 1 - O 1", "X 2 - O 0", "X 0 - O 2", "X 1 - O 0"):
            if candidate not in ordered:
                ordered.append(candidate)
        return ordered

    add(
        "board_turn",
        "board",
        state,
        "In this position, which player is to move next?",
        ["X", "O"],
        engine.current_player.symbol,
    )
    add(
        "board_active_face",
        "board",
        state,
        "Which face is in play in this position?",
        list(FACE_LABELS),
        active_label,
    )
    add(
        "board_locked",
        "board",
        state,
        "Which faces are locked in this position?",
        [
            f"{locked_labels[0]} and {locked_labels[1]}",
            f"Only {locked_labels[0]}",
            f"Only {locked_labels[1]}",
            "No faces are locked",
        ],
        f"{locked_labels[0]} and {locked_labels[1]}",
    )
    add(
        "board_locked_winner",
        "board",
        state,
        f"Who won the {locked_labels[0]} face in this position?",
        ["X", "O", "It is a draw", "It is still in progress"],
        engine.faces[locked[0]].winner.symbol,
    )
    if placements:
        legal_row, legal_col = placements[0][1], placements[0][2]
        add(
            "board_active_legal",
            "board",
            state,
            f"Is playing at {active_label}, row {legal_row}, column "
            f"{legal_col} a legal move in this position?",
            ["Yes", "No"],
            "Yes",
            note=f"{active_label} is the face in play and that cell is empty",
        )
    if off_face_move is not None:
        off_face, off_row, off_col = off_face_move
        add(
            "board_off_face_legal",
            "board",
            state,
            f"Is playing at {FACE_LABELS[off_face]}, row {off_row}, column "
            f"{off_col} a legal move right now?",
            ["Yes", "No"],
            "No",
            note=f"only {active_label} is in play",
        )
    add(
        "board_scores",
        "board",
        state,
        "What are the current face-win scores?",
        score_options(f"X {scores[Player.X]} - O {scores[Player.O]}"),
        f"X {scores[Player.X]} - O {scores[Player.O]}",
    )
    add(
        "board_empty_active",
        "board",
        state,
        f"How many empty cells does the {active_label} face have in this position?",
        [
            str(active_empty - 1),
            str(active_empty),
            str(active_empty + 1),
            str(active_empty + 2),
        ],
        str(active_empty),
    )
    if winning_move is not None:
        add(
            "board_win_move",
            "board",
            state,
            f"Does the move '{move_phrase(winning_move, Player.X)}' "
            "immediately win a face for X?",
            ["Yes", "No"],
            "Yes",
        )
    if quiet_move is not None:
        add(
            "board_nonwin_move",
            "board",
            state,
            f"Does the move '{move_phrase(quiet_move, Player.X)}' "
            "immediately win a face for X?",
            ["Yes", "No"],
            "No",
        )
    add(
        "board_nuke",
        "board",
        state,
        f"Can X legally nuke the {active_label} face right now?",
        ["Yes", "No"],
        "Yes" if engine.is_legal(engine.nuke_move(active_face)) else "No",
    )
    return items


def run_quiz(
    agent: Agent,
    items: list[QuizItem],
    on_result: Optional[Callable[[QuizResult], None]] = None,
) -> list[QuizResult]:
    """Ask every quiz item through the agent's Choice interface and grade it."""
    results: list[QuizResult] = []
    for item in items:
        start = perf_counter()
        choice: Optional[str] = None
        confidence: Optional[float] = None
        error: Optional[str] = None
        try:
            answer, _ = agent.ask_choice(item.state, item.instructions, item.options)
            choice = answer.get("choice")
            confidence = answer.get("confidence")
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
        latency_ms = (perf_counter() - start) * 1000.0
        result = QuizResult(
            id=item.id,
            category=item.category,
            expected=item.expected,
            choice=choice,
            correct=choice == item.expected,
            latency_ms=latency_ms,
            confidence=confidence,
            error=error,
        )
        results.append(result)
        if on_result:
            on_result(result)
    return results


def quiz_summary(results: list[QuizResult]) -> dict:
    """Accuracy overall and per category."""
    by_category: dict[str, dict[str, float]] = {}
    for result in results:
        bucket = by_category.setdefault(result.category, {"correct": 0, "total": 0})
        bucket["total"] += 1
        bucket["correct"] += int(result.correct)
    for bucket in by_category.values():
        bucket["accuracy"] = round(bucket["correct"] / bucket["total"], 4) if bucket["total"] else 0.0
    correct = sum(1 for result in results if result.correct)
    return {
        "correct": correct,
        "total": len(results),
        "accuracy": round(correct / len(results), 4) if results else 0.0,
        "by_category": by_category,
    }
