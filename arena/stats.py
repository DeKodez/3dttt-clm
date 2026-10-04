"""Stats — win rates and latency percentiles for arena matches."""

from dataclasses import dataclass, field
from typing import Any, Optional


def percentile(values: list[float], fraction: float) -> float:
    """Nearest-rank percentile (fraction in [0, 1])."""
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(fraction * (len(ordered) - 1))))
    return ordered[index]


@dataclass
class AgentStats:
    """Aggregated results for one agent across games."""

    name: str
    games: int = 0
    wins: int = 0
    losses: int = 0
    draws: int = 0
    moves: int = 0
    invalid_moves: int = 0
    errors: int = 0
    latencies: list[float] = field(default_factory=list)

    def record_game(self, outcome: str) -> None:
        """Record one finished game as 'win', 'loss', or 'draw'."""
        self.games += 1
        if outcome == "win":
            self.wins += 1
        elif outcome == "loss":
            self.losses += 1
        else:
            self.draws += 1

    def record_move(
        self, latency_ms: float, invalid: bool, error: Optional[str]
    ) -> None:
        """Record one decision's latency and whether it was usable."""
        self.moves += 1
        self.latencies.append(latency_ms)
        if invalid:
            self.invalid_moves += 1
        if error:
            self.errors += 1

    @property
    def win_rate(self) -> float:
        """Fraction of games won."""
        return self.wins / self.games if self.games else 0.0

    def latency_summary(self) -> dict[str, float]:
        """Mean, p50, p95, and max decision latency in milliseconds."""
        return {
            "mean_ms": (
                round(sum(self.latencies) / len(self.latencies), 2)
                if self.latencies
                else 0.0
            ),
            "p50_ms": round(percentile(self.latencies, 0.50), 2),
            "p95_ms": round(percentile(self.latencies, 0.95), 2),
            "max_ms": round(max(self.latencies), 2) if self.latencies else 0.0,
        }

    def summary(self) -> dict[str, Any]:
        """JSON-ready aggregate for reports and the live UI."""
        return {
            "name": self.name,
            "games": self.games,
            "wins": self.wins,
            "losses": self.losses,
            "draws": self.draws,
            "win_rate": round(self.win_rate, 4),
            "moves": self.moves,
            "invalid_moves": self.invalid_moves,
            "errors": self.errors,
            "latency": self.latency_summary(),
        }
