"""Text renderings of the game used as model state and move candidates."""

from typing import Optional

from arena.engine import NUKE_ROW, Engine, Move
from game.enums import CellState, Player
from game.faces import rotation_target
from ui.constants import FACE_LABELS, NUM_FACES

RULES = """3D Tic-Tac-Toe rules:
- The board is a cube with 6 square faces. Each face is an independent 3x3 tic-tac-toe board.
- Faces: 0=Top, 1=Front, 2=Left, 3=Bottom, 4=Back, 5=Right.
- Players are X and O. X always moves first, and turns alternate globally (not per face).
- Only ONE face is in play at a time ("Face in play" below). On your turn you may only play on an empty cell of that face.
- Cube rotation: after each mark, the cube turns based on the cell that was played. Middle cell: the face stays in play. Side (edge) cell: the cube rotates to the neighbouring face in that direction (up/down/left/right). Corner cell: the cube rotates 180 degrees to the opposite face.
- A rotation is skipped if the target face is already locked — the face stays in play instead.
- A face locks when a player gets 3 in a row on it, or when all 9 cells are filled (draw). If a move completes the face and the rotation yields no movement, the cube moves to a random unfinished face.
- The game ends when all 6 faces are locked; the player who won the most faces wins, equal face wins is a tie.
- NUKE (once per player per game): instead of placing a mark, you may wipe every mark from the face in play. The face stays in play and the turn passes. A nuke is only offered while that face has marks on it.
- Turn timers are disabled in this tournament."""

_SYMBOLS = {CellState.EMPTY: ".", CellState.X: "X", CellState.O: "O"}

_LINES = (
    [[(row, col) for col in range(3)] for row in range(3)]
    + [[(row, col) for row in range(3)] for col in range(3)]
    + [[(0, 0), (1, 1), (2, 2)], [(0, 2), (1, 1), (2, 0)]]
)


def _winning_cells(cells, symbol: CellState) -> list[tuple[int, int]]:
    """Empty cells where `symbol` would immediately complete a line."""
    out = []
    for line in _LINES:
        values = [cells[row][col] for row, col in line]
        if values.count(symbol) == 2 and values.count(CellState.EMPTY) == 1:
            out.append(line[values.index(CellState.EMPTY)])
    return sorted(set(out))


def _cells_text(cells: list[tuple[int, int]]) -> str:
    """Render a list of cells as 'row r col c' phrases, or 'none'."""
    if not cells:
        return "none"
    return "; ".join(f"row {row} col {col}" for row, col in cells)


def grid_text(cells) -> str:
    """Render one face's 3x3 grid as text rows."""
    lines = []
    for row in range(3):
        marks = " ".join(_SYMBOLS[cells[row][col]] for col in range(3))
        lines.append(f"    row {row}: {marks}")
    return "\n".join(lines)


def state_text(engine: Engine) -> str:
    """Render the full position (rules, faces, scores, turn) as model input."""
    scores = engine.scores()
    lines = [RULES, "", "Current position:"]
    for index in range(NUM_FACES):
        face = engine.faces[index]
        label = FACE_LABELS[index]
        if face.is_locked():
            outcome = (
                f"won by {face.winner.symbol}" if face.winner else "drawn (no winner)"
            )
            lines.append(f"Face {index} ({label}): LOCKED — {outcome}")
        else:
            marker = " [IN PLAY]" if index == engine.active_face else ""
            lines.append(f"Face {index} ({label}): in progress{marker}")
        lines.append(grid_text(face.cells))
    lines.append("")
    lines.append(f"Face wins so far: X {scores[Player.X]}, O {scores[Player.O]}")
    lines.append(
        f"Face in play: {FACE_LABELS[engine.active_face]} "
        f"(face {engine.active_face})."
    )
    active = engine.faces[engine.active_face]
    lines.append(
        "Immediate wins on this face — "
        f"X: {_cells_text(_winning_cells(active.cells, CellState.X))}; "
        f"O: {_cells_text(_winning_cells(active.cells, CellState.O))}."
    )
    rotation_parts = []
    for row in range(3):
        for col in range(3):
            if active.cells[row][col] != CellState.EMPTY:
                continue
            target = rotation_target(engine.active_face, row, col)
            if target is None:
                consequence = "cube stays (middle cell)"
            elif engine.faces[target].is_locked():
                consequence = (
                    f"rotates to {FACE_LABELS[target]} (face {target})"
                    " — LOCKED, cube stays"
                )
            else:
                consequence = f"rotates to {FACE_LABELS[target]} (face {target})"
            rotation_parts.append(f"row {row} col {col}: {consequence}")
    if rotation_parts:
        lines.append(
            "Rotation if you play on this face — " + "; ".join(rotation_parts) + "."
        )
    nukes_used = engine.controller.nukes_used
    x_nuke = "used" if nukes_used[Player.X] else "available"
    o_nuke = "used" if nukes_used[Player.O] else "available"
    lines.append(f"One-time nukes — X: {x_nuke}, O: {o_nuke}.")
    lines.append(f"{engine.current_player.symbol} to move.")
    return "\n".join(lines)


def move_instructions(player: Player, opponent: Player) -> str:
    """Shared multiple-choice instruction text used by both agents."""
    return (
        f"Which move should {player.symbol} play next? "
        f"If any option completes {player.symbol}'s line, that wins the face — "
        "take it. Otherwise check whether the opponent can win this face "
        "immediately, whether blocking survives the rotation, and whether the "
        "one-time nuke (which wipes the face and leaves it in play) is the only "
        "way to deny them. Use the nuke only to remove an immediate opponent "
        "win; otherwise save it. Pick the single best legal move for the "
        "current player."
    )


def turn_questions(
    table: dict[str, Move], player: Player, opponent: Player
) -> dict[str, dict]:
    """The two typed questions both agents ask each turn (parity contract)."""
    return {
        "threat_check": {
            "type": "noul",
            "instructions": (
                f"Can {opponent.symbol} win the face in play immediately — "
                f"does {opponent.symbol} have an empty cell right now where "
                "playing it would complete three in a row?"
            ),
            "criteria": {
                "true": (
                    f"Yes — {opponent.symbol} has an empty cell on the face "
                    "in play that completes three in a row this turn."
                ),
                "false": (
                    f"No — {opponent.symbol} has no move on the face in play "
                    "that completes three in a row this turn."
                ),
            },
        },
        "answer": {
            "type": "choice",
            "instructions": move_instructions(player, opponent),
            "criteria": {phrase: None for phrase in table},
        },
    }


def move_phrase(move: Move, player: Player) -> str:
    """Human-readable name for a move, used as the option text models choose."""
    face_index, row, col = move
    if row == NUKE_ROW:
        return f"Nuke the {FACE_LABELS[face_index]} face (wipe every mark on it)"
    return (
        f"Play {player.symbol} at {FACE_LABELS[face_index]}, "
        f"row {row}, column {col}"
    )


def _outcome_text(engine: Engine, move: Move) -> str:
    """Factual consequences of playing `move` from the current position."""
    player = engine.current_player
    opponent = Player.O if player == Player.X else Player.X
    opp_symbol = CellState.O if player == Player.X else CellState.X
    face_index = engine.active_face
    before_face = engine.faces[face_index]

    if move[1] == NUKE_ROW:
        marks = sum(
            before_face.get_cell(row, col) != CellState.EMPTY
            for row in range(3)
            for col in range(3)
        )
        parts = [f"wipes {marks} mark" + ("" if marks == 1 else "s")]
        threats = _winning_cells(before_face.cells, opp_symbol)
        if threats:
            parts.append(
                f"removes {opponent.symbol}'s immediate win at {_cells_text(threats)}"
            )
        else:
            parts.append("no immediate win to deny")
        parts.append("face stays in play")
        parts.append(f"{opponent.symbol} to move here next")
        return "; ".join(parts)

    before_threats = _winning_cells(before_face.cells, opp_symbol)
    clone = engine.clone()
    clone.make_move(move)
    after_face = clone.faces[face_index]
    after_threats = _winning_cells(after_face.cells, opp_symbol)

    parts = []
    if after_face.is_locked() and after_face.winner is not None:
        parts.append(
            f"completes {player.symbol}'s line — this face locks for {player.symbol}"
        )
    elif after_face.is_locked():
        parts.append("fills this face — locked draw, no score")
    else:
        blocked = [cell for cell in before_threats if cell not in after_threats]
        if blocked:
            parts.append(f"blocks {opponent.symbol}'s win at {_cells_text(blocked)}")

    if not after_face.is_locked():
        if clone.active_face == face_index:
            target = rotation_target(face_index, move[1], move[2])
            reason = (
                "middle cell" if target is None else f"{FACE_LABELS[target]} locked"
            )
            parts.append(f"cube stays on this face ({reason})")
        else:
            parts.append(
                f"cube rotates to {FACE_LABELS[clone.active_face]} "
                f"(face {clone.active_face})"
            )
        if clone.active_face == face_index and after_threats:
            parts.append(
                f"leaves {opponent.symbol} to play here with an immediate win at "
                f"{_cells_text(after_threats)}"
            )
    elif clone.is_game_over():
        parts.append("this was the last face — match ends")
    else:
        next_index = clone.active_face
        parts.append(
            f"next face in play: {FACE_LABELS[next_index]} (face {next_index})"
        )
    return "; ".join(parts)


def move_options(engine: Engine) -> dict[str, Move]:
    """Map each legal move's annotated option text to its (face, row, col)."""
    player = engine.current_player
    options = {}
    for move in engine.legal_moves():
        label = move_phrase(move, player)
        options[f"{label} — {_outcome_text(engine, move)}"] = move
    return options


def parse_move_id(text: str) -> Optional[Move]:
    """Parse compact ids like 'f3_r1_c2' (used in debugging and docs)."""
    parts = text.strip().lower().replace("-", "_").split("_")
    if len(parts) != 3:
        return None
    digits = []
    for part in parts:
        if not part or not part[1:].isdigit() or part[0] not in "frc":
            return None
        digits.append(int(part[1:]))
    face_index, row, col = digits
    if not (0 <= face_index < NUM_FACES and 0 <= row <= 2 and 0 <= col <= 2):
        return None
    return (face_index, row, col)
