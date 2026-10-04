"""Tests for the headless engine adapter."""

import random

from arena.engine import Engine
from arena.match import MAX_MOVES
from game.enums import CellState, Player


def test_initial_legal_moves():
    engine = Engine()
    moves = engine.legal_moves()
    assert len(moves) == 9
    assert all(move[0] == engine.active_face for move in moves)
    assert not engine.is_legal(engine.nuke_move(engine.active_face))
    assert engine.current_player == Player.X
    assert not engine.is_game_over()


def test_move_and_turn_switch():
    engine = Engine()
    assert engine.make_move((1, 1, 1))  # middle cell: the face stays in play
    assert engine.active_face == 1
    assert engine.faces[1].get_cell(1, 1) == Player.X.cell_state
    assert engine.current_player == Player.O
    assert not engine.make_move((1, 1, 1))
    assert engine.current_player == Player.O


def test_side_cell_rotates_to_neighbour():
    engine = Engine()
    assert engine.make_move((1, 0, 1))  # Front up -> Top
    assert engine.active_face == 0
    assert engine.make_move((0, 0, 1))  # Top up -> Back
    assert engine.active_face == 4
    assert engine.make_move((4, 1, 0))  # Back left -> Right
    assert engine.active_face == 5


def test_corner_cell_rotates_to_opposite():
    engine = Engine()
    assert engine.make_move((1, 0, 0))  # Front corner -> Back
    assert engine.active_face == 4
    assert engine.make_move((4, 2, 2))  # Back corner -> Front
    assert engine.active_face == 1


def test_rotation_skipped_when_target_face_locked():
    engine = Engine()
    for row in range(3):
        engine.faces[4].place(row, 0, Player.O)  # Back won by O
    assert engine.make_move((1, 0, 2))  # corner targets Back, which is locked
    assert engine.active_face == 1


def test_completing_face_rotates_to_a_random_unfinished_face():
    engine = Engine()
    engine.faces[1].place(0, 0, Player.X)
    engine.faces[1].place(0, 1, Player.X)
    engine.faces[4].place(0, 0, Player.O)
    engine.faces[4].place(0, 1, Player.O)
    engine.faces[4].place(0, 2, Player.O)
    assert engine.make_move((1, 0, 2))
    assert engine.faces[1].winner == Player.X
    assert engine.active_face not in (1, 4)  # not the completed or its target


def test_moves_outside_the_active_face_are_rejected():
    engine = Engine()
    assert not engine.is_legal((0, 0, 0))
    assert not engine.make_move((0, 0, 0))
    assert engine.faces[0].get_cell(0, 0) == CellState.EMPTY
    assert engine.current_player == Player.X


def test_face_locks_on_win_and_scores():
    engine = Engine()
    for move in [
        (1, 0, 0),  # X corner -> Back
        (4, 1, 1),  # O middle -> stays on Back
        (4, 0, 0),  # X corner -> Front
        (1, 1, 1),  # O middle -> stays on Front
        (1, 0, 2),  # X corner -> Back
        (4, 2, 2),  # O corner -> Front
        (1, 0, 1),  # X completes row 0
    ]:
        assert engine.make_move(move)
    assert engine.faces[1].is_locked()
    assert engine.faces[1].winner == Player.X
    assert engine.scores()[Player.X] == 1
    assert not engine.is_legal((1, 1, 1))


def test_nuke_wipes_the_face_in_play():
    engine = Engine()
    engine.faces[1].place(1, 1, Player.O)
    engine.faces[1].place(2, 2, Player.O)
    assert engine.is_legal(engine.nuke_move(1))
    assert engine.make_move(engine.nuke_move(1))
    assert engine.faces[1].get_cell(1, 1) == CellState.EMPTY
    assert engine.faces[1].get_cell(2, 2) == CellState.EMPTY
    assert engine.active_face == 1
    assert engine.current_player == Player.O
    assert not engine.is_legal(engine.nuke_move(1))  # face is now empty
    engine.faces[1].place(0, 0, Player.O)
    assert engine.is_legal(engine.nuke_move(1))  # O still has theirs
    assert not engine.make_move(engine.nuke_move(0))  # wrong face


def test_nuke_is_once_per_player():
    engine = Engine()
    engine.faces[1].place(1, 1, Player.O)
    assert engine.make_move(engine.nuke_move(1))
    engine.faces[1].place(0, 0, Player.O)
    assert engine.make_move(engine.nuke_move(1))  # O nukes
    engine.faces[1].place(1, 0, Player.X)
    assert not engine.is_legal(engine.nuke_move(1))  # X already spent theirs


def test_clone_reproduces_the_full_state():
    engine = Engine()
    for move in [(1, 0, 1), (0, 0, 1), (4, 1, 0)]:
        assert engine.make_move(move)
    clone = engine.clone()
    assert clone.snapshot() == engine.snapshot()
    assert clone.active_face == engine.active_face
    clone.make_move((5, 1, 1))
    assert clone.snapshot() != engine.snapshot()


def test_clone_matches_across_random_games():
    engine = Engine()
    rng = random.Random(5)
    while not engine.is_game_over():
        moves = engine.legal_moves()
        assert moves
        assert engine.make_move(rng.choice(moves))
        clone = engine.clone()
        assert clone.snapshot() == engine.snapshot()


def test_game_ends_when_all_faces_locked():
    engine = Engine()
    while not engine.is_game_over():
        moves = engine.legal_moves()
        assert moves
        assert engine.make_move(moves[0])
    assert all(face.is_locked() for face in engine.faces)
    assert len(engine.move_log) <= MAX_MOVES
