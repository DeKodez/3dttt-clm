"""Tests for baseline agents and text helpers."""

from arena.agents.baselines import RandomAgent, TacticalAgent
from arena.agents.text import move_options, move_phrase, parse_move_id, state_text
from arena.engine import Engine
from game.enums import Player


def test_random_agent_stays_legal_for_a_full_game():
    agent = RandomAgent(seed=1)
    engine = Engine()
    while not engine.is_game_over():
        result = agent.decide(engine)
        assert not result.invalid
        assert result.error is None
        assert engine.make_move(result.move)


def test_tactical_takes_immediate_win():
    engine = Engine()
    engine.faces[1].place(0, 0, Player.X)
    engine.faces[1].place(0, 1, Player.X)
    engine.faces[1].place(2, 0, Player.O)
    agent = TacticalAgent(seed=1)
    result = agent.decide(engine)
    assert result.move == (1, 0, 2)
    assert result.meta["strategy"] == "win"


def test_tactical_blocks_immediate_threat():
    engine = Engine()
    engine.faces[1].place(0, 0, Player.O)
    engine.faces[1].place(0, 1, Player.O)
    engine.faces[1].place(1, 1, Player.X)
    agent = TacticalAgent(seed=1)
    result = agent.decide(engine)
    assert result.move == (1, 0, 2)
    assert result.meta["strategy"] == "block"


def test_move_options_cover_legal_moves():
    engine = Engine()
    table = move_options(engine)
    assert len(table) == len(engine.legal_moves())
    phrase = move_phrase((1, 1, 2), Player.X)
    matching = [key for key in table if key.startswith(phrase + " — ")]
    assert len(matching) == 1
    assert table[matching[0]] == (1, 1, 2)
    assert "Face 3 (Bottom): in progress" in state_text(engine)
    assert "Face in play: Front (face 1)." in state_text(engine)


def test_move_options_offer_the_nuke_when_marks_exist():
    engine = Engine()
    assert not any(move[1] == -1 for move in engine.legal_moves())
    engine.faces[1].place(1, 1, Player.O)
    table = move_options(engine)
    nuke_phrase = move_phrase(engine.nuke_move(1), Player.X)
    matching = [key for key in table if key.startswith(nuke_phrase + " — ")]
    assert len(matching) == 1
    assert table[matching[0]] == (1, -1, -1)
    assert "One-time nukes — X: available, O: available." in state_text(engine)


def test_annotations_report_immediate_wins_and_outcomes():
    engine = Engine()
    for move in [(1, 0, 0), (4, 0, 0), (1, 0, 1), (0, 2, 1)]:
        assert engine.make_move(move)
    state = state_text(engine)
    assert "Immediate wins on this face — X: row 0 col 2; O: none." in state
    option = next(
        key
        for key in move_options(engine)
        if key.startswith("Play X at Front, row 0, column 2")
    )
    assert "completes X's line" in option
    assert "locks for X" in option


def test_parse_move_id_round_trip():
    assert parse_move_id("f3_r1_c2") == (3, 1, 2)
    assert parse_move_id("F0_R0_C0") == (0, 0, 0)
    assert parse_move_id("nope") is None
    assert parse_move_id("f9_r0_c0") is None
