"""Generate SystemOne choice-task fine-tuning rows for CLM from arena positions.

Every row replays exactly what ``CLMAgent`` sends at inference:

* ``state``: ``arena.agents.text.state_text(engine)``
* ``questions``: ``arena.agents.text.turn_questions(table, player, opponent)``

so ``clm.schema.build_pairs`` on the server/trainer reconstructs the same
state/candidate texts the head sees in a real match.

Gold labels come from a deterministic oracle:

* ``threat_check``: the opponent currently has an immediate winning cell on
  the face in play.
* ``answer``: win > safe block > nuke (only to deny an immediate win) >
  positional heuristic.  Boosts can oversample the rare decisions (double
  threats, missed wins, correct nukes) that the reference head gets wrong.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from arena.agents.baselines import LINES, TacticalAgent, _would_win
from arena.agents.text import _winning_cells, move_options, state_text, turn_questions
from arena.engine import NUKE_ROW, Engine, Move
from game.enums import Player


def _score_move(engine: Engine, move: Move) -> float:
    """Deterministic positional score (baselines heuristic without the rng jitter)."""
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
    return score


def _best_positional(engine: Engine, moves: list[Move]) -> Move:
    """Highest-scoring move, ties broken by enumeration order."""
    return max(moves, key=lambda move: _score_move(engine, move))


def oracle(engine: Engine) -> tuple[Move, str]:
    """Return (best legal move, strategy label) for the player to move."""
    player = engine.current_player
    opponent = player.next()
    opp_symbol = opponent.cell_state
    moves = engine.legal_moves()
    placements = [move for move in moves if move[1] != NUKE_ROW]
    nukes = [move for move in moves if move[1] == NUKE_ROW]

    wins = [
        move
        for move in placements
        if _would_win(engine.faces[move[0]].cells, move[1], move[2], player)
    ]
    if wins:
        return _best_positional(engine, wins), "win"

    active = engine.active_face
    threats = _winning_cells(engine.faces[active].cells, opp_symbol)
    if not threats:
        return _best_positional(engine, placements), "positional"

    safe: list[Move] = []
    for move in placements:
        clone = engine.clone()
        clone.make_move(move)
        if clone.is_game_over() or clone.active_face != active:
            safe.append(move)
        elif not _winning_cells(clone.faces[active].cells, opp_symbol):
            safe.append(move)
    if safe:
        blocks = [move for move in safe if (move[1], move[2]) in threats]
        return _best_positional(engine, blocks or safe), "block"
    if nukes:
        return nukes[0], "nuke"
    return _best_positional(engine, placements), "lost"


def _row(engine: Engine, row_id: str, mode: str, move_idx: int) -> dict:
    """One training row: the inference wire payload plus oracle gold labels."""
    player = engine.current_player
    opponent = player.next()
    table = move_options(engine)
    questions = turn_questions(table, player, opponent)
    move, strategy = oracle(engine)
    key = next(key for key, value in table.items() if value == move)

    active = engine.faces[engine.active_face]
    threats = _winning_cells(active.cells, opponent.cell_state)
    threat = bool(threats)

    return {
        "id": row_id,
        "state": state_text(engine),
        "questions": questions,
        "gold": {
            "threat_check": {
                "label": "true" if threat else "false",
                "probabilities": {"true": 1.0} if threat else {"false": 1.0},
            },
            "answer": {"label": key, "probabilities": {key: 1.0}},
        },
        "meta": {
            "mode": mode,
            "move_idx": move_idx,
            "strategy": strategy,
            "threat": threat,
            "n_threats": len(threats),
            "n_options": len(table),
        },
    }


def _position_key(engine: Engine) -> str:
    return state_text(engine)


def _play_game(mode: str, seed: int, game_index: int, seen: set[str], rows: list[dict]) -> None:
    """Collect deduplicated rows from one game with the requested player policies."""
    rng = random.Random((seed, mode, game_index))
    engine = Engine()
    tactical = TacticalAgent(name="tactical", seed=seed * 1000 + game_index)

    def random_move() -> Move:
        return rng.choice(engine.legal_moves())

    def tactical_move() -> Move:
        return tactical._choose(engine)[0]

    if mode == "random":
        choosers = {Player.X: random_move, Player.O: random_move}
    elif mode == "tactical":
        choosers = {Player.X: tactical_move, Player.O: tactical_move}
    elif mode == "mixed":
        choosers = (
            {Player.X: tactical_move, Player.O: random_move}
            if game_index % 2 == 0
            else {Player.X: random_move, Player.O: tactical_move}
        )
    else:
        raise ValueError(f"unknown mode {mode!r}")

    move_idx = 0
    while not engine.is_game_over():
        position = _position_key(engine)
        if position not in seen:
            seen.add(position)
            rows.append(_row(engine, f"{mode}-g{game_index}-m{move_idx}", mode, move_idx))
        engine.make_move(choosers[engine.current_player]())
        move_idx += 1


def boost(rows: list[dict], double_threat: int, own_win: int, nuke: int) -> list[dict]:
    """Duplicate rare decision rows to rebalance the training set."""
    out: list[dict] = []
    for row in rows:
        copies = 1
        meta = row["meta"]
        if meta["n_threats"] >= 2:
            copies += double_threat
        if meta["strategy"] == "win":
            copies += own_win
        if meta["strategy"] == "nuke":
            copies += nuke
        for copy in range(copies):
            if copy == 0:
                out.append(row)
            else:
                duplicate = dict(row)
                duplicate["id"] = f"{row['id']}-b{copy}"
                out.append(duplicate)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", default="training/data/3dttt-v1")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--random-games", type=int, default=400)
    parser.add_argument("--tactical-games", type=int, default=400)
    parser.add_argument("--mixed-games", type=int, default=200)
    parser.add_argument("--test-every", type=int, default=10, help="every Nth game goes to test")
    parser.add_argument("--boost-double-threat", type=int, default=8)
    parser.add_argument("--boost-own-win", type=int, default=4)
    parser.add_argument("--boost-nuke", type=int, default=8)
    args = parser.parse_args()

    train_rows: list[dict] = []
    test_rows: list[dict] = []
    seen: set[str] = set()
    game_index = 0
    for mode, count in (
        ("random", args.random_games),
        ("tactical", args.tactical_games),
        ("mixed", args.mixed_games),
    ):
        for _ in range(count):
            target = test_rows if game_index % args.test_every == args.test_every - 1 else train_rows
            _play_game(mode, args.seed, game_index, seen, target)
            game_index += 1

    stats = {
        "train_rows": len(train_rows),
        "test_rows": len(test_rows),
        "train_unique_positions": len({row["id"] for row in train_rows}),
        "strategy": dict(Counter(row["meta"]["strategy"] for row in train_rows)),
        "threat": dict(Counter("true" if row["meta"]["threat"] else "false" for row in train_rows)),
        "n_threats": dict(sorted(Counter(row["meta"]["n_threats"] for row in train_rows).items())),
    }

    boosted = boost(train_rows, args.boost_double_threat, args.boost_own_win, args.boost_nuke)
    stats["train_rows_boosted"] = len(boosted)
    stats["strategy_boosted"] = dict(Counter(row["meta"]["strategy"] for row in boosted))
    stats["threat_boosted"] = dict(
        Counter("true" if row["meta"]["threat"] else "false" for row in boosted)
    )

    out_dir = ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "train.jsonl", "w") as handle:
        for row in boosted:
            handle.write(json.dumps(row) + "\n")
    with open(out_dir / "test.jsonl", "w") as handle:
        for row in test_rows:
            handle.write(json.dumps(row) + "\n")
    with open(out_dir / "stats.json", "w") as handle:
        json.dump(stats, handle, indent=1)

    print(json.dumps(stats, indent=1))
    print(f"wrote {out_dir}")


if __name__ == "__main__":
    main()
