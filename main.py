"""3D Tic-Tac-Toe — Entry Point."""
# pylint: disable=no-member

import time
from typing import Optional

import pygame

from game.game_controller import GameController
from ui.constants import (
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
    FACE_ADJACENCY,
    DEFAULT_FACE,
    SKIP_POPUP_DURATION,
)
from ui.input_handler import InputHandler, NavigateAction, NukeAction, PlaceMoveAction
from ui.renderer import Renderer


def main() -> None:
    """Initialize Pygame, wire up components, and run the game loop."""
    pygame.init()
    surface = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("3D Tic-Tac-Toe")
    clock = pygame.time.Clock()

    renderer = Renderer()
    input_handler = InputHandler()

    # --- Start-screen option state ---
    nukes_enabled = True
    timer_enabled = False
    timer_seconds_text = "15"
    timer_input_focused = False

    game = GameController(nukes_enabled=nukes_enabled)
    active_face_index = DEFAULT_FACE
    running = True
    on_start_screen = True

    # --- Timer runtime state ---
    turn_start: float = 0.0
    timer_total: int = 0
    skip_popup_start: float = 0.0
    skipped_player_symbol: str = ""

    def _reset_turn_timer() -> None:
        nonlocal turn_start
        turn_start = time.monotonic()

    def _handle_timer_input(event: pygame.event.Event) -> None:
        nonlocal timer_seconds_text
        if event.key == pygame.K_BACKSPACE:
            timer_seconds_text = timer_seconds_text[:-1]
        elif event.unicode.isdigit() and len(timer_seconds_text) < 2:
            candidate = timer_seconds_text + event.unicode
            if int(candidate) <= 60:
                timer_seconds_text = candidate

    def _handle_start_screen_click(pos: tuple[int, int]) -> None:
        nonlocal nukes_enabled, timer_enabled, timer_input_focused

        nuke_rect = renderer.get_nuke_toggle_rect()
        timer_rect = renderer.get_timer_toggle_rect()
        input_rect = renderer.get_timer_input_rect()

        if timer_enabled and input_rect.collidepoint(pos):
            timer_input_focused = True
        elif nuke_rect.collidepoint(pos):
            nukes_enabled = not nukes_enabled
        elif timer_rect.collidepoint(pos):
            timer_enabled = not timer_enabled
            if timer_enabled:
                timer_input_focused = True
            else:
                timer_input_focused = False
        else:
            timer_input_focused = False
            _start_game()

    def _start_game() -> None:
        nonlocal game, active_face_index, on_start_screen
        nonlocal timer_total, timer_seconds_text
        # Clamp timer value
        try:
            val = int(timer_seconds_text) if timer_seconds_text else 15
        except ValueError:
            val = 15
        val = max(1, min(60, val))
        timer_seconds_text = str(val)
        timer_total = val if timer_enabled else 0
        game = GameController(nukes_enabled=nukes_enabled)
        active_face_index = game.active_face
        on_start_screen = False
        _reset_turn_timer()

    while running:
        mouse_pos = pygame.mouse.get_pos()
        now = time.monotonic()

        # --- Compute timer remaining ---
        timer_remaining: Optional[float] = None
        if not on_start_screen and timer_total > 0 and not game.is_game_over():
            timer_remaining = max(0.0, timer_total - (now - turn_start))

        # --- Skip popup alpha (fades out) ---
        skip_alpha = 0.0
        if skip_popup_start > 0.0:
            elapsed = now - skip_popup_start
            if elapsed < SKIP_POPUP_DURATION:
                skip_alpha = 1.0 - (elapsed / SKIP_POPUP_DURATION)
            else:
                skip_popup_start = 0.0

        # --- Auto-skip on timeout ---
        if (
            timer_remaining is not None
            and timer_remaining <= 0.0
            and skip_alpha == 0.0
        ):
            skipped_player_symbol = game.current_player.symbol
            game.skip_turn()
            skip_popup_start = now
            _reset_turn_timer()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif on_start_screen and timer_input_focused:
                    _handle_timer_input(event)

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if on_start_screen:
                    _handle_start_screen_click(event.pos)
                else:
                    action = input_handler.handle_click(event.pos)

                    if isinstance(action, NavigateAction):
                        active_face_index = FACE_ADJACENCY[active_face_index][
                            action.direction
                        ]

                    elif isinstance(action, NukeAction):
                        if not game.is_game_over():
                            if game.nuke_face(active_face_index):
                                active_face_index = game.active_face
                                _reset_turn_timer()

                    elif isinstance(action, PlaceMoveAction):
                        if not game.is_game_over():
                            if game.make_move(
                                active_face_index, action.row, action.col
                            ):
                                # The cube rotates: follow the face in play
                                active_face_index = game.active_face
                                _reset_turn_timer()

        if on_start_screen:
            renderer.draw_start_screen(
                surface, nukes_enabled, timer_enabled,
                timer_seconds_text, timer_input_focused, mouse_pos,
            )
        else:
            renderer.draw(
                surface, game, active_face_index, mouse_pos,
                timer_remaining=timer_remaining,
                timer_total=timer_total if timer_total > 0 else None,
                skip_popup_alpha=skip_alpha,
                skipped_player_symbol=skipped_player_symbol,
            )

        pygame.display.flip()
        clock.tick(30)

    pygame.quit()


if __name__ == "__main__":
    main()
