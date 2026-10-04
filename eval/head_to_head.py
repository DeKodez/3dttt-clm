"""Head-to-head series runner — plays N games between two agents.

Re-created CLI for the match series (the originals were ad-hoc). Writes a
``<out>.summary.json`` in the same schema as the prompt-era series, and
refuses to record a series containing any invalid move — see
``docs/INVALID_EVAL_POSTMORTEM.md``.

Usage:
  python eval/head_to_head.py --agent-a jev --agent-b clm \
      --games 4 --seed 11 --out results/head_to_head_jev_vs_clm_ft1_valid.summary.json

Preflight before a recorded series (also enforced here):
  - ``$CLM_BASE_URL/health`` answers (the runner fails on first invalid move)
  - first CLM move has ``invalid: false`` and non-empty ``meta``
"""

import argparse
import json
import time
from pathlib import Path

from arena.agents.registry import build_agent
from arena.match import play_match


def _close(agent) -> None:
    client = getattr(agent, "client", None)
    if client is not None and hasattr(client, "close"):
        client.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent-a", default="jev")
    parser.add_argument("--agent-b", default="clm")
    parser.add_argument("--games", type=int, default=4)
    parser.add_argument("--seed", type=int, default=11)
    parser.add_argument("--out", required=True)
    parser.add_argument("--frames-out", default=None)
    parser.add_argument("--min-move-delay", type=float, default=0.0)
    parser.add_argument(
        "--allow-invalid",
        action="store_true",
        help="record the series even if moves failed (do not use for evidence)",
    )
    args = parser.parse_args()

    frames: list[dict] = []

    def on_event(event: dict) -> None:
        frames.append(event)
        if args.min_move_delay and event.get("type") == "move":
            time.sleep(args.min_move_delay)

    agent_a = build_agent(args.agent_a)
    agent_b = build_agent(args.agent_b)
    start = time.time()
    try:
        match = play_match(
            agent_a,
            agent_b,
            games=args.games,
            seed=args.seed,
            on_event=on_event,
        )
    finally:
        _close(agent_a)
        _close(agent_b)
    elapsed = time.time() - start

    invalid = [
        {"game": game.index, "player": move.player, "move": list(move.move), "error": move.error}
        for game in match.games
        for move in game.moves
        if move.invalid
    ]
    summary = {
        "agents": match.agents,
        "games": args.games,
        "seed": args.seed,
        "min_move_delay": args.min_move_delay,
        "elapsed_s": round(elapsed, 1),
        "frames": len(frames),
        "invalid_moves": invalid,
        "result": match.to_dict(),
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    if args.frames_out:
        frames_path = Path(args.frames_out)
        frames_path.parent.mkdir(parents=True, exist_ok=True)
        with frames_path.open("w") as handle:
            for frame in frames:
                handle.write(json.dumps(frame) + "\n")

    if invalid and not args.allow_invalid:
        failed = out.with_suffix(".FAILED.json")
        failed.write_text(json.dumps(summary, indent=1))
        print(f"INVALID SERIES: {len(invalid)} failed moves; wrote {failed}")
        for entry in invalid[:5]:
            print(f"  game {entry['game']} {entry['player']} {entry['move']}: {entry['error']}")
        return 2

    out.write_text(json.dumps(summary, indent=1))
    print(f"wrote {out} ({args.games} games, {elapsed:.0f}s)")
    for name, stat in match.stats.items():
        s = stat.summary()
        print(
            f"  {name}: {s['wins']}W {s['losses']}L {s['draws']}D "
            f"({s['win_rate']:.0%})  invalid {s['invalid_moves']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
