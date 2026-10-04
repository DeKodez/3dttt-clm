"""Tests for the match runner and stats."""

from arena.agents.baselines import RandomAgent, TacticalAgent
from arena.match import play_game, play_match
from arena.probe import build_quiz, quiz_summary, run_quiz


def test_game_record_is_consistent():
    record = play_game(RandomAgent(seed=1), RandomAgent(seed=2), seed=3)
    assert record.winner in (None, "X", "O")
    assert sum(record.scores.values()) <= 6
    assert record.moves
    assert record.result_label


def test_match_swaps_sides_and_aggregates():
    result = play_match(
        RandomAgent(seed=1), TacticalAgent(seed=2), games=2, seed=10
    )
    first, second = result.games
    assert first.x_agent == "random"
    assert second.x_agent == "tactical"
    for stat in result.stats.values():
        assert stat.games == 2
        assert stat.wins + stat.losses + stat.draws == 2
        assert stat.moves > 0
        assert stat.invalid_moves == 0
        assert stat.latency_summary()["p50_ms"] >= 0.0


def test_events_stream_full_lifecycle():
    events = []
    play_game(RandomAgent(seed=1), RandomAgent(seed=2), seed=3, on_event=events.append)
    types = [event["type"] for event in events]
    assert types[0] == "game_start"
    assert types[-1] == "game_end"
    assert types.count("move") == len([t for t in types if t == "move"])
    assert events[0]["state"]["current_player"] == "X"
    assert events[-1]["state"]["game_over"] is True


def test_quiz_ground_truth_is_gradeable():
    items = build_quiz(seed=7)
    assert len(items) >= 15
    ids = {item.id for item in items}
    assert {"rules_faces", "board_turn", "board_win_move"} <= ids

    class EchoAgent:
        name = "echo"

        def ask_choice(self, state, instructions, options):
            return {"choice": options and list(options)[0], "confidence": 0.5}, {}

    results = run_quiz(EchoAgent(), items)
    summary = quiz_summary(results)
    assert summary["total"] == len(items)
    assert 0.0 <= summary["accuracy"] <= 1.0
    assert set(summary["by_category"]) == {"rules", "board"}
