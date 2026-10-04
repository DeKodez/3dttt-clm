"""Match runner — plays games between two agents with event callbacks."""

import random
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from arena.agents.base import Agent
from arena.engine import Engine, Move
from arena.stats import AgentStats
from game.enums import Player

EventCallback = Callable[[dict[str, Any]], None]

# Safety cap on one game. The 54 cells can be refilled after a nuke and
# each player holds one nuke, so a legitimate game can exceed 54 moves.
MAX_MOVES = 100


@dataclass
class MoveRecord:
    """One applied move, including the agent's latency and diagnostics."""

    player: str
    move: Move
    latency_ms: float
    invalid: bool
    error: Optional[str]
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """JSON-ready view."""
        return {
            "player": self.player,
            "move": list(self.move),
            "latency_ms": round(self.latency_ms, 2),
            "invalid": self.invalid,
            "error": self.error,
            "meta": self.meta,
        }


@dataclass
class GameRecord:
    """Everything that happened in one game."""

    index: int
    x_agent: str
    o_agent: str
    winner: Optional[str]
    scores: dict[str, int]
    result_label: str
    moves: list[MoveRecord] = field(default_factory=list)

    def to_dict(self) -> dict:
        """JSON-ready view."""
        return {
            "index": self.index,
            "x_agent": self.x_agent,
            "o_agent": self.o_agent,
            "winner": self.winner,
            "scores": self.scores,
            "result_label": self.result_label,
            "moves": [move.to_dict() for move in self.moves],
        }


@dataclass
class MatchResult:
    """A series of games plus per-agent aggregates."""

    agents: list[str]
    games: list[GameRecord]
    stats: dict[str, AgentStats]

    def to_dict(self) -> dict:
        """JSON-ready view."""
        return {
            "agents": self.agents,
            "games": [game.to_dict() for game in self.games],
            "stats": {name: stat.summary() for name, stat in self.stats.items()},
        }


def play_game(
    agent_x: Agent,
    agent_o: Agent,
    index: int = 0,
    seed: Optional[int] = None,
    on_event: Optional[EventCallback] = None,
) -> GameRecord:
    """Play one full game to completion.

    An illegal or failed decision falls back to a random legal move so
    the game always finishes; the original choice is still recorded.
    """
    engine = Engine()
    fallback_rng = random.Random(seed)
    record = GameRecord(
        index=index,
        x_agent=agent_x.name,
        o_agent=agent_o.name,
        winner=None,
        scores={},
        result_label="",
    )
    if on_event:
        on_event(
            {
                "type": "game_start",
                "index": index,
                "x_agent": agent_x.name,
                "o_agent": agent_o.name,
                "state": engine.snapshot(),
            }
        )

    while not engine.is_game_over():
        agent = agent_x if engine.current_player == Player.X else agent_o
        result = agent.decide(engine)
        move = result.move
        if not engine.is_legal(move):
            legal = engine.legal_moves()
            if not legal:
                break
            move = fallback_rng.choice(legal)
        engine.make_move(move)
        move_record = MoveRecord(
            player=agent.name,
            move=move,
            latency_ms=result.latency_ms,
            invalid=result.invalid,
            error=result.error,
            meta=result.meta,
        )
        record.moves.append(move_record)
        if on_event:
            payload = move_record.to_dict()
            payload["type"] = "move"
            payload["state"] = engine.snapshot()
            on_event(payload)
        if len(record.moves) >= MAX_MOVES:
            break

    winner = engine.winner()
    record.winner = winner.symbol if winner else None
    record.scores = {
        player.symbol: count for player, count in engine.scores().items()
    }
    record.result_label = engine.result_label()
    if on_event:
        on_event(
            {
                "type": "game_end",
                "index": index,
                "state": engine.snapshot(),
                "winner": record.winner,
                "scores": record.scores,
                "result_label": record.result_label,
            }
        )
    return record


def play_match(
    agent_a: Agent,
    agent_b: Agent,
    games: int = 4,
    seed: Optional[int] = None,
    on_event: Optional[EventCallback] = None,
) -> MatchResult:
    """Play a series, swapping sides every game for fairness."""
    stats = {
        agent_a.name: AgentStats(agent_a.name),
        agent_b.name: AgentStats(agent_b.name),
    }
    records: list[GameRecord] = []
    for index in range(games):
        if index % 2 == 0:
            agent_x, agent_o = agent_a, agent_b
        else:
            agent_x, agent_o = agent_b, agent_a
        record = play_game(
            agent_x,
            agent_o,
            index=index,
            seed=None if seed is None else seed + index,
            on_event=on_event,
        )
        records.append(record)
        for name, stat in stats.items():
            for move in record.moves:
                if move.player == name:
                    stat.record_move(move.latency_ms, move.invalid, move.error)
            if record.winner is None:
                outcome = "draw"
            else:
                winner_name = (
                    record.x_agent if record.winner == "X" else record.o_agent
                )
                outcome = "win" if winner_name == name else "loss"
            stat.record_game(outcome)
    return MatchResult(
        agents=[agent_a.name, agent_b.name],
        games=records,
        stats=stats,
    )
