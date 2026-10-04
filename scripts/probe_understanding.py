"""CLI — probe an agent's understanding of the game and its playability."""

import argparse
import json
from pathlib import Path

from arena.agents.registry import build_agent
from arena.match import play_match
from arena.probe import QuizResult, build_quiz, quiz_summary, run_quiz

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = REPO_ROOT / "results"


def _print_result(result: QuizResult) -> None:
    status = "PASS" if result.correct else "FAIL"
    choice = result.choice if result.choice is not None else (result.error or "no answer")
    print(
        f"[{status}] {result.id} ({result.latency_ms:.0f} ms): "
        f"chose {choice!r}, expected {result.expected!r}"
    )


def main() -> None:
    """Run the quiz and playability games, then save a JSON report."""
    parser = argparse.ArgumentParser(
        description="Probe an agent's understanding of the game and its playability."
    )
    parser.add_argument(
        "--agent", default="jev", help="agent name (jev, clm, random, tactical)"
    )
    parser.add_argument(
        "--games", type=int, default=3, help="games against the opponent baseline"
    )
    parser.add_argument(
        "--opponent", default="random", help="opponent name (random, tactical)"
    )
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--quiz-only", action="store_true")
    parser.add_argument("--play-only", action="store_true")
    args = parser.parse_args()

    kwargs = {"seed": args.seed} if args.agent in ("random", "tactical") else {}
    agent = build_agent(args.agent, **kwargs)

    report: dict = {
        "agent": args.agent,
        "opponent": args.opponent,
        "quiz": None,
        "play": None,
        "summary": {},
    }

    if not args.play_only:
        print(f"\n=== Understanding quiz: {args.agent} ===")
        results = run_quiz(agent, build_quiz(seed=args.seed), on_result=_print_result)
        summary = quiz_summary(results)
        report["quiz"] = {
            "results": [result.to_dict() for result in results],
            "summary": summary,
        }
        print(
            f"\nQuiz score: {summary['correct']}/{summary['total']} "
            f"({summary['accuracy']:.0%})"
        )
        for category, bucket in summary["by_category"].items():
            print(f"  {category}: {bucket['correct']}/{bucket['total']}")

    if not args.quiz_only:
        print(
            f"\n=== Playability: {args.agent} vs {args.opponent}, "
            f"{args.games} games ==="
        )
        opponent_kwargs = (
            {"seed": args.seed + 100} if args.opponent in ("random", "tactical") else {}
        )
        opponent = build_agent(args.opponent, **opponent_kwargs)
        match = play_match(agent, opponent, games=args.games, seed=args.seed)
        report["play"] = match.to_dict()
        for name, stat in match.stats.items():
            latency = stat.latency_summary()
            print(
                f"{name}: {stat.wins}W-{stat.losses}L-{stat.draws}D "
                f"(win rate {stat.win_rate:.0%}), invalid moves {stat.invalid_moves}, "
                f"errors {stat.errors}, p50 {latency['p50_ms']:.0f} ms, "
                f"p95 {latency['p95_ms']:.0f} ms"
            )
        report["summary"] = {
            "quiz_accuracy": (
                report["quiz"]["summary"]["accuracy"] if report["quiz"] else None
            ),
            "win_rate": match.stats[agent.name].win_rate,
            "invalid_moves": match.stats[agent.name].invalid_moves,
            "errors": match.stats[agent.name].errors,
        }

    RESULTS_DIR.mkdir(exist_ok=True)
    suffix = "" if args.opponent == "random" else f"_vs_{args.opponent}"
    output_path = RESULTS_DIR / f"probe_{args.agent}{suffix}.json"
    output_path.write_text(json.dumps(report, indent=2))
    print(f"\nSaved report to {output_path}")


if __name__ == "__main__":
    main()
