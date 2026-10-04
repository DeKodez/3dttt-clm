"""Agent — the decision interface every player implements."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Optional

from arena.engine import Engine, Move


@dataclass
class AgentResult:
    """Outcome of one decision, with timing and diagnostics."""

    move: Optional[Move]
    latency_ms: float
    invalid: bool = False
    error: Optional[str] = None
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """JSON-ready view."""
        return {
            "move": list(self.move) if self.move else None,
            "latency_ms": round(self.latency_ms, 2),
            "invalid": self.invalid,
            "error": self.error,
            "meta": self.meta,
        }


class Agent(ABC):
    """Base class that times decisions and flags illegal moves.

    Subclasses implement `_choose`; the public `decide` wrapper never
    raises, so one bad model response cannot crash a match.
    """

    def __init__(self, name: str) -> None:
        self.name = name

    @abstractmethod
    def _choose(self, engine: Engine) -> tuple[Optional[Move], dict[str, Any]]:
        """Return the chosen move and optional metadata."""

    def ask_choice(
        self,
        state: str,
        instructions: str,
        options: dict[str, Optional[str]],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Generic multiple-choice query used by the understanding probe."""
        raise NotImplementedError(f"{self.name} does not support quiz questions")

    def decide(self, engine: Engine) -> AgentResult:
        """Time one decision against the current position."""
        start = perf_counter()
        move: Optional[Move] = None
        meta: dict[str, Any] = {}
        error: Optional[str] = None
        try:
            move, meta = self._choose(engine)
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
        latency_ms = (perf_counter() - start) * 1000.0
        invalid = not engine.is_legal(move)
        if move is None and error is None:
            error = "no move returned"
        return AgentResult(
            move=move,
            latency_ms=latency_ms,
            invalid=invalid,
            error=error,
            meta=meta,
        )
