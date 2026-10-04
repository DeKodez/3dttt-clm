"""Aggregate head-to-head summary files into pooled statistics.

Usage:
  PYTHONPATH=. python eval/aggregate_head_to_head.py [--out aggregate.json] \
      results/head_to_head_jev_vs_clm_ft1_valid*.summary.json results/rematch_batch/*.summary.json

Prints pooled W/L/D, splits by starting side, and Wilson 95% CIs for the
win-equivalent rate (win = 1, draw = 0.5) and the decisive-game win rate.
"""

import argparse
import json
import math
from pathlib import Path


def wilson(k: float, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return (center - half, center + half)


class Pool:
    def __init__(self, side: str) -> None:
        self.side = side
        self.games = 0
        self.wins = 0
        self.losses = 0
        self.draws = 0

    def add(self, won: bool, lost: bool) -> None:
        self.games += 1
        if won:
            self.wins += 1
        elif lost:
            self.losses += 1
        else:
            self.draws += 1

    def line(self) -> str:
        n = self.games
        if n == 0:
            return f"{self.side}: no games"
        we = (self.wins + 0.5 * self.draws) / n
        lo, hi = wilson(self.wins + 0.5 * self.draws, n)
        decisive = self.wins + self.losses
        dec = f"{self.wins / decisive:.0%}" if decisive else "n/a"
        dec_ci = wilson(self.wins, decisive) if decisive else (0.0, 0.0)
        return (
            f"{self.side}: {n} games  {self.wins}W-{self.losses}L-{self.draws}D  "
            f"win-equiv {we:.0%} [95% CI {lo:.0%}-{hi:.0%}]  "
            f"decisive {dec} [95% CI {dec_ci[0]:.0%}-{dec_ci[1]:.0%}]"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+")
    parser.add_argument("--subject", default="clm", help="agent to pool stats for")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    pool = Pool(args.subject)
    as_x = Pool(f"{args.subject} as X")
    as_o = Pool(f"{args.subject} as O")
    per_file = []
    for path in sorted(args.files):
        data = json.loads(Path(path).read_text())
        w = l = d = 0
        for game in data["result"]["games"]:
            subject_side = "x" if game["x_agent"] == args.subject else "o"
            winner = game["winner"]
            if isinstance(winner, str) and winner.upper() in ("X", "O"):
                winner_agent = game["x_agent"] if winner.upper() == "X" else game["o_agent"]
            else:
                winner_agent = winner
            won = winner_agent == args.subject
            lost = winner_agent is not None and not won
            if winner_agent is None:
                d += 1
            elif won:
                w += 1
            else:
                l += 1
            pool.add(won, lost)
            (as_x if subject_side == "x" else as_o).add(won, lost)
        per_file.append(
            {
                "file": str(path),
                "seed": data["seed"],
                "games": len(data["result"]["games"]),
                "wins": w,
                "losses": l,
                "draws": d,
            }
        )
        print(f"seed {data['seed']:>4}: {w}W-{l}L-{d}D  ({Path(path).name})")

    print()
    print(pool.line())
    print(as_x.line())
    print(as_o.line())

    aggregate = {
        "subject": args.subject,
        "files": per_file,
        "pooled": vars(pool),
        "as_x": vars(as_x),
        "as_o": vars(as_o),
    }
    if args.out:
        Path(args.out).write_text(json.dumps(aggregate, indent=1))
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
