"""Renderer — all Pygame drawing logic. Reads game state, never mutates it."""
# pylint: disable=no-member

import math
import os
from typing import Optional

import pygame

from game.board import Board
from game.enums import CellState, FaceStatus, Player
from game.game_controller import GameController
from ui.constants import (
    ACTIVE_FACE_BORDER_WIDTH,
    ACTIVE_FACE_COLOR,
    ARROW_BG,
    ARROW_HOVER,
    ARROW_ICON,
    ARROW_PADDING,
    ARROW_SIZE,
    ARROWS,
    BG_COLOR,
    CELL_HOVER,
    CELL_SIZE,
    CUBE_EDGE_BACK_COLOR,
    CUBE_EDGE_COLOR,
    CUBE_LEGEND_CX,
    CUBE_LEGEND_CY,
    CUBE_LEGEND_R,
    FACE_ADJACENCY,
    FACE_LABELS,
    FACE_LABEL_Y,
    FONT_SIZE_CUBE_LABEL,
    FONT_SIZE_FACE_LABEL,
    FONT_SIZE_GAME_OVER,
    FONT_SIZE_GAME_OVER_SUB,
    FONT_SIZE_LOCKED_LABEL,
    FONT_SIZE_START_SUB,
    FONT_SIZE_START_TITLE,
    FONT_SIZE_STATUS,
    FONT_SIZE_TOGGLE_LABEL,
    GRID_COLOR,
    GRID_HEIGHT,
    GRID_LINE_WIDTH,
    GRID_ORIGIN_X,
    GRID_ORIGIN_Y,
    GRID_WIDTH,
    INACTIVE_OVERLAY,
    LOCKED_LABEL_COLOR,
    LOCKED_OVERLAY,
    MARK_LINE_WIDTH,
    MARK_PADDING,
    NUKE_BUTTON_BG,
    NUKE_BUTTON_BORDER,
    NUKE_BUTTON_BORDER_DISABLED,
    NUKE_BUTTON_DISABLED,
    NUKE_BUTTON_HOVER,
    NUKE_BUTTON_SIZE,
    NUKE_BUTTON_X,
    NUKE_BUTTON_Y,
    NUKE_ICON_SIZE,
    NUM_FACES,
    O_COLOR,
    SKIP_POPUP_BG,
    START_SCREEN_BG,
    START_SCREEN_BORDER,
    START_SCREEN_TEXT_COLOR,
    STATUS_BAR_HEIGHT,
    STATUS_BAR_Y,
    STATUS_BG,
    TEXT_COLOR,
    TIMER_COLOR_NORMAL,
    TIMER_COLOR_URGENT,
    TIMER_COLOR_WARN,
    TIMER_INPUT_BG,
    TIMER_INPUT_BORDER,
    TIMER_INPUT_BORDER_FOCUSED,
    TIMER_INPUT_H,
    TIMER_INPUT_TEXT_COLOR,
    TIMER_INPUT_W,
    FONT_SIZE_TIMER,
    TOGGLE_KNOB_COLOR,
    TOGGLE_OFF_COLOR,
    TOGGLE_ON_COLOR,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
    X_COLOR,
)


class Renderer:
    """Handles all drawing to the Pygame surface.

    Reads game state via GameController but never mutates it.
    """

    def __init__(self) -> None:
        self._font_face_label = pygame.font.SysFont(None, FONT_SIZE_FACE_LABEL)
        self._font_cube_label = pygame.font.SysFont(None, FONT_SIZE_CUBE_LABEL)
        self._font_status = pygame.font.SysFont(None, FONT_SIZE_STATUS)
        self._font_locked_label = pygame.font.SysFont(None, FONT_SIZE_LOCKED_LABEL)
        self._font_game_over = pygame.font.SysFont(None, FONT_SIZE_GAME_OVER)
        self._font_game_over_sub = pygame.font.SysFont(None, FONT_SIZE_GAME_OVER_SUB)
        self._font_start_title = pygame.font.SysFont(None, FONT_SIZE_START_TITLE)
        self._font_start_sub = pygame.font.SysFont(None, FONT_SIZE_START_SUB)
        self._font_toggle_label = pygame.font.SysFont(None, FONT_SIZE_TOGGLE_LABEL)
        self._font_timer = pygame.font.SysFont(None, FONT_SIZE_TIMER)
        self._cube_geometry = self._compute_cube_geometry()
        self._nuke_icon = self._load_nuke_icon()
        self._nuke_icon_disabled = self._make_disabled_icon(self._nuke_icon)

    def draw(
        self,
        surface: pygame.Surface,
        game: GameController,
        active_face_index: int,
        mouse_pos: tuple[int, int] = (0, 0),
        timer_remaining: Optional[float] = None,
        timer_total: Optional[int] = None,
        skip_popup_alpha: float = 0.0,
        skipped_player_symbol: str = "",
    ) -> None:
        """Master draw call — clears screen and draws everything."""
        surface.fill(BG_COLOR)

        active_board = game.get_face(active_face_index)
        in_play = (
            active_face_index == game.active_face
            and not active_board.is_locked()
            and not game.is_game_over()
        )

        self._draw_face_label(surface, active_face_index, active_board, in_play)
        self._draw_cube_legend(
            surface, active_face_index, game.faces, game.active_face
        )
        self._draw_arrows(surface, active_face_index, game.faces, mouse_pos)
        self._draw_grid(surface, active_board)

        # Hover highlight on valid cells (only on the face in play)
        if in_play:
            self._draw_cell_hover(surface, active_board, mouse_pos)

        # Locked face overlay
        if active_board.is_locked():
            self._draw_locked_overlay(surface, active_board)
        elif not in_play:
            self._draw_inactive_overlay(surface, game.active_face)

        # Gold frame around the face in play
        if in_play:
            border_rect = pygame.Rect(
                GRID_ORIGIN_X, GRID_ORIGIN_Y, GRID_WIDTH, GRID_HEIGHT
            )
            pygame.draw.rect(
                surface, ACTIVE_FACE_COLOR, border_rect, ACTIVE_FACE_BORDER_WIDTH
            )

        # Nuke button
        if game.nukes_enabled:
            can_nuke = game.can_nuke(active_face_index)
            self._draw_nuke_button(surface, can_nuke, mouse_pos)

        self._draw_status_bar(
            surface,
            game.current_player,
            game.score_tracker.get_scores(),
            game.active_face,
            timer_remaining,
            timer_total,
        )

        if skip_popup_alpha > 0.0:
            self._draw_skip_popup(surface, skip_popup_alpha, skipped_player_symbol)

        if game.is_game_over():
            self._draw_game_over(surface, game.get_result_text(), game.faces)

    # --- Face label (top center) ---

    def _draw_face_label(
        self,
        surface: pygame.Surface,
        face_index: int,
        board: Board,
        in_play: bool,
    ) -> None:
        """Draw the current face name and status above the grid."""
        label = FACE_LABELS[face_index]

        if board.status == FaceStatus.WON_X:
            label += "  \u2014  Won by X"
            color = X_COLOR
        elif board.status == FaceStatus.WON_O:
            label += "  \u2014  Won by O"
            color = O_COLOR
        elif board.status == FaceStatus.DRAW:
            label += "  \u2014  Draw"
            color = (150, 150, 150)
        elif in_play:
            label += "  \u2014  In play"
            color = ACTIVE_FACE_COLOR
        else:
            label += "  \u2014  not in play"
            color = (130, 130, 130)

        text_surf = self._font_face_label.render(label, True, color)
        text_rect = text_surf.get_rect(centerx=WINDOW_WIDTH // 2, y=FACE_LABEL_Y)
        surface.blit(text_surf, text_rect)

    # --- Inactive face overlay ---

    def _draw_inactive_overlay(
        self, surface: pygame.Surface, active_face_index: int
    ) -> None:
        """Dim a face that is not in play and point at the active one."""
        ox, oy = GRID_ORIGIN_X, GRID_ORIGIN_Y
        overlay = pygame.Surface((GRID_WIDTH, GRID_HEIGHT), pygame.SRCALPHA)
        overlay.fill(INACTIVE_OVERLAY)
        surface.blit(overlay, (ox, oy))

        hint = f"Not in play \u2014 {FACE_LABELS[active_face_index]} is active"
        label_surf = self._font_locked_label.render(hint, True, ACTIVE_FACE_COLOR)
        label_rect = label_surf.get_rect(
            centerx=ox + GRID_WIDTH // 2,
            centery=oy + GRID_HEIGHT // 2,
        )
        surface.blit(label_surf, label_rect)

    # --- Cell hover highlight ---

    def _draw_cell_hover(
        self,
        surface: pygame.Surface,
        board: Board,
        mouse_pos: tuple[int, int],
    ) -> None:
        """Draw a subtle highlight on the cell under the mouse cursor."""
        mx, my = mouse_pos
        ox, oy = GRID_ORIGIN_X, GRID_ORIGIN_Y

        if not (ox <= mx < ox + GRID_WIDTH and oy <= my < oy + GRID_HEIGHT):
            return

        col = min((mx - ox) // CELL_SIZE, 2)
        row = min((my - oy) // CELL_SIZE, 2)

        # Only highlight empty cells
        if board.get_cell(row, col) != CellState.EMPTY:
            return

        cell_rect = pygame.Rect(
            ox + col * CELL_SIZE + 1,
            oy + row * CELL_SIZE + 1,
            CELL_SIZE - 2,
            CELL_SIZE - 2,
        )
        hover_surf = pygame.Surface(
            (cell_rect.width, cell_rect.height), pygame.SRCALPHA
        )
        hover_surf.fill((*CELL_HOVER, 120))
        surface.blit(hover_surf, cell_rect.topleft)

    # --- Locked face overlay ---

    def _draw_locked_overlay(
        self, surface: pygame.Surface, board: Board
    ) -> None:
        """Draw a dim overlay on a locked face with a status label."""
        ox, oy = GRID_ORIGIN_X, GRID_ORIGIN_Y
        overlay = pygame.Surface((GRID_WIDTH, GRID_HEIGHT), pygame.SRCALPHA)
        overlay.fill(LOCKED_OVERLAY)
        surface.blit(overlay, (ox, oy))

        if board.status == FaceStatus.WON_X:
            label = "Won by X"
            color = X_COLOR
        elif board.status == FaceStatus.WON_O:
            label = "Won by O"
            color = O_COLOR
        else:
            label = "Draw"
            color = LOCKED_LABEL_COLOR

        label_surf = self._font_locked_label.render(label, True, color)
        label_rect = label_surf.get_rect(
            centerx=ox + GRID_WIDTH // 2,
            bottom=oy + GRID_HEIGHT - 10,
        )
        surface.blit(label_surf, label_rect)

    # --- Mini isometric cube legend (top left) ---

    @staticmethod
    def _compute_cube_geometry() -> dict:
        """Pre-compute the vertices, face polygons, and edges for the legend cube."""
        cx = CUBE_LEGEND_CX
        cy = CUBE_LEGEND_CY
        r = CUBE_LEGEND_R

        dx = int(r * math.cos(math.radians(30)))
        dy = r // 2

        center = (cx, cy)
        top = (cx, cy - r)
        tr = (cx + dx, cy - dy)
        br = (cx + dx, cy + dy)
        bottom = (cx, cy + r)
        bl = (cx - dx, cy + dy)
        tl = (cx - dx, cy - dy)

        # Each face maps to a rhombus (2 triangular sectors of the hexagon).
        # Opposite faces occupy non-overlapping areas.
        face_polygons = [
            [center, tl, top, tr],        # 0: Top     — upper rhombus
            [center, tr, br, bottom],     # 1: Front   — lower-right rhombus
            [center, bottom, bl, tl],     # 2: Left    — lower-left rhombus
            [center, br, bottom, bl],     # 3: Bottom  — lower rhombus
            [center, bl, tl, top],        # 4: Back    — upper-left rhombus
            [center, top, tr, br],        # 5: Right   — upper-right rhombus
        ]

        # Outer hexagon edges (always solid)
        outer_edges = [
            (top, tr), (tr, br), (br, bottom),
            (bottom, bl), (bl, tl), (tl, top),
        ]

        # Front spokes (from nearest corner v0 → center, drawn solid)
        front_spokes = [(center, top), (center, br), (center, bl)]

        # Back spokes (from farthest corner v6 → center, drawn dashed)
        back_spokes = [(center, bottom), (center, tr), (center, tl)]

        return {
            "face_polygons": face_polygons,
            "outer_edges": outer_edges,
            "front_spokes": front_spokes,
            "back_spokes": back_spokes,
        }

    def _draw_cube_legend(
        self,
        surface: pygame.Surface,
        active_face_index: int,
        faces: list[Board],
        in_play_face: int,
    ) -> None:
        """Draw the mini isometric cube with the face in play highlighted."""
        geo = self._cube_geometry

        # Fill won/drawn faces with tinted colors
        for i, face in enumerate(faces):
            if face.status == FaceStatus.WON_X:
                self._fill_polygon_alpha(
                    surface, geo["face_polygons"][i], (*X_COLOR, 60)
                )
            elif face.status == FaceStatus.WON_O:
                self._fill_polygon_alpha(
                    surface, geo["face_polygons"][i], (*O_COLOR, 60)
                )
            elif face.status == FaceStatus.DRAW:
                self._fill_polygon_alpha(
                    surface, geo["face_polygons"][i], (150, 150, 150, 40)
                )

        # Highlight the viewed face (white), then the face in play (gold)
        if active_face_index != in_play_face:
            self._fill_polygon_alpha(
                surface, geo["face_polygons"][active_face_index], (255, 255, 255, 70)
            )
        self._fill_polygon_alpha(
            surface, geo["face_polygons"][in_play_face], (*ACTIVE_FACE_COLOR, 110)
        )

        # Outer hexagon edges (solid)
        for start, end in geo["outer_edges"]:
            pygame.draw.line(surface, CUBE_EDGE_COLOR, start, end, 2)

        # Front spokes (solid)
        for start, end in geo["front_spokes"]:
            pygame.draw.line(surface, CUBE_EDGE_COLOR, start, end, 2)

        # Back spokes (dashed)
        for start, end in geo["back_spokes"]:
            self._draw_dashed_line(surface, CUBE_EDGE_BACK_COLOR, start, end, 1)

        # Small label beneath the cube
        label_surf = self._font_cube_label.render(
            FACE_LABELS[active_face_index], True, TEXT_COLOR
        )
        label_rect = label_surf.get_rect(
            centerx=CUBE_LEGEND_CX, top=CUBE_LEGEND_CY + CUBE_LEGEND_R + 6
        )
        surface.blit(label_surf, label_rect)

    @staticmethod
    def _fill_polygon_alpha(
        surface: pygame.Surface,
        polygon: list[tuple[int, int]],
        color_rgba: tuple[int, int, int, int],
    ) -> None:
        """Draw a filled polygon with per-pixel alpha onto the surface."""
        xs = [p[0] for p in polygon]
        ys = [p[1] for p in polygon]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        w = max_x - min_x + 1
        h = max_y - min_y + 1

        temp = pygame.Surface((w, h), pygame.SRCALPHA)
        offset_polygon = [(x - min_x, y - min_y) for x, y in polygon]
        pygame.draw.polygon(temp, color_rgba, offset_polygon)
        surface.blit(temp, (min_x, min_y))

    @staticmethod
    def _draw_dashed_line(
        surface: pygame.Surface,
        color: tuple[int, int, int],
        start: tuple[int, int],
        end: tuple[int, int],
        width: int = 1,
        dash_len: int = 4,
        gap_len: int = 3,
    ) -> None:
        """Draw a dashed line between two points."""
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        length = math.sqrt(dx * dx + dy * dy)
        if length == 0:
            return
        dx_n, dy_n = dx / length, dy / length

        pos = 0.0
        drawing = True
        while pos < length:
            seg = min(dash_len if drawing else gap_len, length - pos)
            if drawing:
                sx = int(start[0] + dx_n * pos)
                sy = int(start[1] + dy_n * pos)
                ex = int(start[0] + dx_n * (pos + seg))
                ey = int(start[1] + dy_n * (pos + seg))
                pygame.draw.line(surface, color, (sx, sy), (ex, ey), width)
            pos += seg
            drawing = not drawing

    # --- Arrow buttons ---

    def _draw_arrows(
        self,
        surface: pygame.Surface,
        active_face_index: int,
        faces: list[Board],
        mouse_pos: tuple[int, int],
    ) -> None:
        """Draw the 4 directional arrow buttons with status-tinted borders."""
        mx, my = mouse_pos

        for direction, pos in ARROWS.items():
            rect = pygame.Rect(pos[0], pos[1], ARROW_SIZE, ARROW_SIZE)
            hovered = rect.collidepoint(mx, my)

            # Background (lighter on hover)
            bg = ARROW_HOVER if hovered else ARROW_BG
            pygame.draw.rect(surface, bg, rect, border_radius=4)

            # Tinted border based on neighbor face status
            neighbor_idx = FACE_ADJACENCY[active_face_index][direction]
            neighbor = faces[neighbor_idx]
            if neighbor.status == FaceStatus.WON_X:
                border_color = X_COLOR
            elif neighbor.status == FaceStatus.WON_O:
                border_color = O_COLOR
            elif neighbor.status == FaceStatus.DRAW:
                border_color = (100, 100, 100)
            else:
                border_color = (80, 80, 80)
            pygame.draw.rect(surface, border_color, rect, 2, border_radius=4)

            cx = rect.centerx
            cy = rect.centery
            p = ARROW_PADDING

            if direction == "up":
                tri = [
                    (cx, rect.top + p),
                    (rect.left + p, rect.bottom - p),
                    (rect.right - p, rect.bottom - p),
                ]
            elif direction == "down":
                tri = [
                    (cx, rect.bottom - p),
                    (rect.left + p, rect.top + p),
                    (rect.right - p, rect.top + p),
                ]
            elif direction == "left":
                tri = [
                    (rect.left + p, cy),
                    (rect.right - p, rect.top + p),
                    (rect.right - p, rect.bottom - p),
                ]
            else:  # right
                tri = [
                    (rect.right - p, cy),
                    (rect.left + p, rect.top + p),
                    (rect.left + p, rect.bottom - p),
                ]

            pygame.draw.polygon(surface, ARROW_ICON, tri)

    # --- Grid ---

    def _draw_grid(self, surface: pygame.Surface, board: Board) -> None:
        """Draw the 3x3 grid lines and any X/O marks."""
        ox, oy = GRID_ORIGIN_X, GRID_ORIGIN_Y

        # Draw cell backgrounds
        for r in range(3):
            for c in range(3):
                rect = pygame.Rect(
                    ox + c * CELL_SIZE,
                    oy + r * CELL_SIZE,
                    CELL_SIZE,
                    CELL_SIZE,
                )
                pygame.draw.rect(surface, BG_COLOR, rect)

        # Draw grid lines
        for i in range(1, 3):
            # Vertical
            x = ox + i * CELL_SIZE
            pygame.draw.line(
                surface, GRID_COLOR, (x, oy), (x, oy + GRID_HEIGHT), GRID_LINE_WIDTH
            )
            # Horizontal
            y = oy + i * CELL_SIZE
            pygame.draw.line(
                surface, GRID_COLOR, (ox, y), (ox + GRID_WIDTH, y), GRID_LINE_WIDTH
            )

        # Draw border
        border_rect = pygame.Rect(ox, oy, GRID_WIDTH, GRID_HEIGHT)
        pygame.draw.rect(surface, GRID_COLOR, border_rect, GRID_LINE_WIDTH)

        # Draw marks
        for r in range(3):
            for c in range(3):
                cell = board.get_cell(r, c)
                cx = ox + c * CELL_SIZE + CELL_SIZE // 2
                cy = oy + r * CELL_SIZE + CELL_SIZE // 2
                if cell == CellState.X:
                    self._draw_x(surface, (cx, cy), CELL_SIZE)
                elif cell == CellState.O:
                    self._draw_o(surface, (cx, cy), CELL_SIZE)

        # Draw winning line if face is won
        if board.winner is not None and board.winning_cells is not None:
            self._draw_winning_line(surface, board)

    def _draw_x(
        self, surface: pygame.Surface, center: tuple[int, int], size: int
    ) -> None:
        """Draw an X mark (two diagonal lines)."""
        half = size // 2 - MARK_PADDING
        cx, cy = center
        pygame.draw.line(
            surface,
            X_COLOR,
            (cx - half, cy - half),
            (cx + half, cy + half),
            MARK_LINE_WIDTH,
        )
        pygame.draw.line(
            surface,
            X_COLOR,
            (cx + half, cy - half),
            (cx - half, cy + half),
            MARK_LINE_WIDTH,
        )

    def _draw_o(
        self, surface: pygame.Surface, center: tuple[int, int], size: int
    ) -> None:
        """Draw an O mark (circle)."""
        radius = size // 2 - MARK_PADDING
        pygame.draw.circle(surface, O_COLOR, center, radius, MARK_LINE_WIDTH)

    def _draw_winning_line(self, surface: pygame.Surface, board: Board) -> None:
        """Draw a prominent line through the 3 winning cells with a glow."""
        if board.winning_cells is None:
            return

        ox, oy = GRID_ORIGIN_X, GRID_ORIGIN_Y
        color = X_COLOR if board.winner == Player.X else O_COLOR

        start_r, start_c = board.winning_cells[0]
        end_r, end_c = board.winning_cells[2]

        start_pos = (
            ox + start_c * CELL_SIZE + CELL_SIZE // 2,
            oy + start_r * CELL_SIZE + CELL_SIZE // 2,
        )
        end_pos = (
            ox + end_c * CELL_SIZE + CELL_SIZE // 2,
            oy + end_r * CELL_SIZE + CELL_SIZE // 2,
        )

        # Glow backdrop (wider, semi-transparent)
        glow_color = (*color, 60)
        glow_surf = pygame.Surface(
            (GRID_WIDTH + 20, GRID_HEIGHT + 20), pygame.SRCALPHA
        )
        glow_start = (start_pos[0] - ox + 10, start_pos[1] - oy + 10)
        glow_end = (end_pos[0] - ox + 10, end_pos[1] - oy + 10)
        pygame.draw.line(glow_surf, glow_color, glow_start, glow_end, 16)
        surface.blit(glow_surf, (ox - 10, oy - 10))

        # Main line
        pygame.draw.line(surface, color, start_pos, end_pos, MARK_LINE_WIDTH + 3)

    # --- Status bar ---

    def _draw_status_bar(
        self,
        surface: pygame.Surface,
        current_player: Player,
        scores: dict[Player, int],
        active_face: int,
        timer_remaining: Optional[float] = None,
        timer_total: Optional[int] = None,
    ) -> None:
        """Draw the status bar showing whose turn it is and current scores."""
        bar_rect = pygame.Rect(0, STATUS_BAR_Y, WINDOW_WIDTH, STATUS_BAR_HEIGHT)
        pygame.draw.rect(surface, STATUS_BG, bar_rect)

        # Turn indicator (left side), with the face in play
        turn_color = X_COLOR if current_player == Player.X else O_COLOR
        turn_text = (
            f"Player {current_player.symbol}'s turn"
            f"  \u00b7  {FACE_LABELS[active_face]} in play"
        )
        turn_surf = self._font_status.render(turn_text, True, turn_color)
        surface.blit(turn_surf, (20, STATUS_BAR_Y + 10))

        # Timer countdown (center)
        if timer_remaining is not None and timer_total is not None:
            self._draw_timer_countdown(
                surface, timer_remaining, timer_total
            )

        # Score (right side)
        x_score = scores[Player.X]
        o_score = scores[Player.O]
        score_text = f"X: {x_score}  |  O: {o_score}"
        score_surf = self._font_status.render(score_text, True, TEXT_COLOR)
        score_rect = score_surf.get_rect(
            right=WINDOW_WIDTH - 20, top=STATUS_BAR_Y + 10
        )
        surface.blit(score_surf, score_rect)

    # --- Timer countdown ---

    def _draw_timer_countdown(
        self,
        surface: pygame.Surface,
        remaining: float,
        total: int,
    ) -> None:
        """Draw a compact timer in the center of the status bar."""
        secs = max(0, math.ceil(remaining))
        fraction = remaining / total if total > 0 else 0.0

        # Color shifts: normal → warn → urgent
        if fraction > 0.5:
            color = TIMER_COLOR_NORMAL
        elif fraction > 0.2:
            color = TIMER_COLOR_WARN
        else:
            color = TIMER_COLOR_URGENT

        timer_text = f"{secs}s"
        text_surf = self._font_timer.render(timer_text, True, color)
        text_rect = text_surf.get_rect(
            centerx=WINDOW_WIDTH // 2, centery=STATUS_BAR_Y + STATUS_BAR_HEIGHT // 2
        )
        surface.blit(text_surf, text_rect)

        # Thin progress bar underneath the text
        bar_w = 60
        bar_h = 3
        bar_x = WINDOW_WIDTH // 2 - bar_w // 2
        bar_y = text_rect.bottom + 1

        # Background track
        pygame.draw.rect(
            surface, (60, 60, 60),
            (bar_x, bar_y, bar_w, bar_h),
            border_radius=1,
        )
        # Filled portion
        fill_w = max(0, int(bar_w * fraction))
        if fill_w > 0:
            pygame.draw.rect(
                surface, color,
                (bar_x, bar_y, fill_w, bar_h),
                border_radius=1,
            )

    # --- Turn-skipped popup ---

    def _draw_skip_popup(
        self,
        surface: pygame.Surface,
        alpha: float,
        player_symbol: str,
    ) -> None:
        """Draw a brief centered popup indicating a turn was skipped."""
        overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        a = int(180 * alpha)
        overlay.fill((0, 0, 0, a))
        surface.blit(overlay, (0, 0))

        text = f"Player {player_symbol}'s turn skipped!"
        text_color = (*TEXT_COLOR, int(255 * alpha))
        text_surf = self._font_face_label.render(text, True, text_color[:3])

        # Apply alpha to the text surface
        temp = pygame.Surface(text_surf.get_size(), pygame.SRCALPHA)
        temp.blit(text_surf, (0, 0))
        temp.set_alpha(int(255 * alpha))

        text_rect = temp.get_rect(
            center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2)
        )
        surface.blit(temp, text_rect)

    # --- Game over ---

    def _draw_game_over(
        self,
        surface: pygame.Surface,
        result_text: str,
        faces: list[Board],
    ) -> None:
        """Draw a semi-transparent overlay with the final result and face breakdown."""
        overlay = pygame.Surface(
            (WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA
        )
        overlay.fill((0, 0, 0, 180))
        surface.blit(overlay, (0, 0))

        center_x = WINDOW_WIDTH // 2
        center_y = WINDOW_HEIGHT // 2

        # Title: "GAME OVER"
        title_surf = self._font_game_over.render("GAME OVER", True, TEXT_COLOR)
        title_rect = title_surf.get_rect(center=(center_x, center_y - 80))
        surface.blit(title_surf, title_rect)

        # Result text (e.g. "Player X wins 4-2!")
        result_surf = self._font_face_label.render(result_text, True, TEXT_COLOR)
        result_rect = result_surf.get_rect(center=(center_x, center_y - 45))
        surface.blit(result_surf, result_rect)

        # Per-face breakdown
        breakdown_y = center_y - 10
        for i in range(NUM_FACES):
            face = faces[i]
            label = FACE_LABELS[i]

            if face.status == FaceStatus.WON_X:
                status_str = "X"
                color = X_COLOR
            elif face.status == FaceStatus.WON_O:
                status_str = "O"
                color = O_COLOR
            else:
                status_str = "-"
                color = (120, 120, 120)

            line_text = f"{label}: {status_str}"
            line_surf = self._font_game_over_sub.render(line_text, True, color)

            # Arrange in two columns (3 per column)
            col = i // 3
            row = i % 3
            lx = center_x - 80 + col * 160
            ly = breakdown_y + row * 26
            line_rect = line_surf.get_rect(centerx=lx, top=ly)
            surface.blit(line_surf, line_rect)

        # Sub text
        sub_text = "Navigate with arrows to review  |  Press ESC to exit"
        sub_surf = self._font_game_over_sub.render(sub_text, True, (160, 160, 160))
        sub_rect = sub_surf.get_rect(center=(center_x, center_y + 100))
        surface.blit(sub_surf, sub_rect)

    # --- Nuke button ---

    @staticmethod
    def _load_nuke_icon() -> pygame.Surface:
        """Load and scale the nuke icon PNG."""
        icon_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "assets", "nuke_button.png"
        )
        icon = pygame.image.load(icon_path).convert_alpha()
        return pygame.transform.smoothscale(icon, (NUKE_ICON_SIZE, NUKE_ICON_SIZE))

    @staticmethod
    def _make_disabled_icon(icon: pygame.Surface) -> pygame.Surface:
        """Create a dimmed/greyed-out version of the nuke icon."""
        disabled = icon.copy()
        dark = pygame.Surface(disabled.get_size(), pygame.SRCALPHA)
        dark.fill((0, 0, 0, 160))
        disabled.blit(dark, (0, 0))
        return disabled

    def _draw_nuke_button(
        self,
        surface: pygame.Surface,
        can_nuke: bool,
        mouse_pos: tuple[int, int],
    ) -> None:
        """Draw the nuke button in the top-right corner."""
        rect = pygame.Rect(
            NUKE_BUTTON_X, NUKE_BUTTON_Y,
            NUKE_BUTTON_SIZE, NUKE_BUTTON_SIZE,
        )
        mx, my = mouse_pos
        hovered = rect.collidepoint(mx, my)

        if can_nuke:
            bg_rgba = NUKE_BUTTON_HOVER if hovered else NUKE_BUTTON_BG
            border = NUKE_BUTTON_BORDER
            icon = self._nuke_icon
        else:
            bg_rgba = (*NUKE_BUTTON_DISABLED, 255)
            border = NUKE_BUTTON_BORDER_DISABLED
            icon = self._nuke_icon_disabled

        # Draw background with alpha support
        bg_surf = pygame.Surface(
            (NUKE_BUTTON_SIZE, NUKE_BUTTON_SIZE), pygame.SRCALPHA
        )
        pygame.draw.rect(
            bg_surf, bg_rgba,
            (0, 0, NUKE_BUTTON_SIZE, NUKE_BUTTON_SIZE),
            border_radius=6,
        )
        surface.blit(bg_surf, rect.topleft)
        pygame.draw.rect(surface, border, rect, 2, border_radius=6)

        # Center icon in button
        icon_x = rect.x + (NUKE_BUTTON_SIZE - NUKE_ICON_SIZE) // 2
        icon_y = rect.y + (NUKE_BUTTON_SIZE - NUKE_ICON_SIZE) // 2
        surface.blit(icon, (icon_x, icon_y))

    # --- Start screen ---

    # Layout y-offsets relative to center_y
    _TITLE_Y_OFFSET = -80
    _NUKE_ROW_Y_OFFSET = -16
    _TIMER_ROW_Y_OFFSET = 22
    _START_HINT_Y_OFFSET = 80

    def draw_start_screen(
        self,
        surface: pygame.Surface,
        nukes_enabled: bool,
        timer_enabled: bool,
        timer_seconds_text: str,
        timer_input_focused: bool,
        mouse_pos: tuple[int, int],
    ) -> None:
        """Draw a full-window start screen overlay that blocks interaction."""
        overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT))
        overlay.fill(START_SCREEN_BG)
        surface.blit(overlay, (0, 0))

        pygame.draw.rect(
            surface, START_SCREEN_BORDER,
            (0, 0, WINDOW_WIDTH, WINDOW_HEIGHT), 4,
        )

        cx = WINDOW_WIDTH // 2
        cy = WINDOW_HEIGHT // 2

        # Title
        title_surf = self._font_start_title.render(
            "3D Tic-Tac-Toe", True, TEXT_COLOR
        )
        title_rect = title_surf.get_rect(center=(cx, cy + self._TITLE_Y_OFFSET))
        surface.blit(title_surf, title_rect)

        # Nuke toggle row
        self._draw_toggle_row(
            surface, "Nukes", nukes_enabled,
            cx, cy + self._NUKE_ROW_Y_OFFSET, mouse_pos,
        )

        # Timer toggle row
        self._draw_toggle_row(
            surface, "Timer", timer_enabled,
            cx, cy + self._TIMER_ROW_Y_OFFSET, mouse_pos,
        )

        # Timer seconds input (only when timer is on)
        if timer_enabled:
            self._draw_timer_input(
                surface, timer_seconds_text, timer_input_focused,
                cx, cy + self._TIMER_ROW_Y_OFFSET, mouse_pos,
            )

        # Start hint
        sub_surf = self._font_start_sub.render(
            "Click anywhere to start", True, START_SCREEN_TEXT_COLOR
        )
        sub_rect = sub_surf.get_rect(center=(cx, cy + self._START_HINT_Y_OFFSET))
        surface.blit(sub_surf, sub_rect)

    # --- Toggle helpers ---

    def _get_toggle_rect(self, label: str, row_cy: int) -> pygame.Rect:
        """Return the clickable rect for a toggle row."""
        toggle_w, toggle_h = 40, 22
        pad_x, pad_y = 20, 10
        label_surf = self._font_toggle_label.render(label, True, TEXT_COLOR)
        total_w = label_surf.get_width() + 10 + toggle_w
        start_x = WINDOW_WIDTH // 2 - total_w // 2
        return pygame.Rect(
            start_x - pad_x,
            row_cy - toggle_h // 2 - pad_y,
            total_w + pad_x * 2,
            toggle_h + pad_y * 2,
        )

    def get_nuke_toggle_rect(self) -> pygame.Rect:
        """Return the clickable rect for the nuke toggle."""
        cy = WINDOW_HEIGHT // 2 + self._NUKE_ROW_Y_OFFSET
        return self._get_toggle_rect("Nukes", cy)

    def get_timer_toggle_rect(self) -> pygame.Rect:
        """Return the clickable rect for the timer toggle."""
        cy = WINDOW_HEIGHT // 2 + self._TIMER_ROW_Y_OFFSET
        return self._get_toggle_rect("Timer", cy)

    def get_timer_input_rect(self) -> pygame.Rect:
        """Return the clickable rect for the timer seconds input box."""
        cx = WINDOW_WIDTH // 2
        cy = WINDOW_HEIGHT // 2 + self._TIMER_ROW_Y_OFFSET
        toggle_w = 40
        label_surf = self._font_toggle_label.render("Timer", True, TEXT_COLOR)
        total_w = label_surf.get_width() + 10 + toggle_w
        start_x = cx - total_w // 2
        input_x = start_x + total_w + 12
        input_y = cy - TIMER_INPUT_H // 2
        return pygame.Rect(input_x, input_y, TIMER_INPUT_W, TIMER_INPUT_H)

    def _draw_toggle_row(
        self,
        surface: pygame.Surface,
        label: str,
        enabled: bool,
        center_x: int,
        center_y: int,
        mouse_pos: tuple[int, int],
    ) -> None:
        """Draw a reusable label + toggle switch row."""
        toggle_w, toggle_h = 40, 22
        label_surf = self._font_toggle_label.render(label, True, TEXT_COLOR)
        total_w = label_surf.get_width() + 10 + toggle_w
        start_x = center_x - total_w // 2

        # Label
        surface.blit(label_surf, (start_x, center_y - label_surf.get_height() // 2))

        # Toggle track
        track_x = start_x + label_surf.get_width() + 10
        track_y = center_y - toggle_h // 2
        track_rect = pygame.Rect(track_x, track_y, toggle_w, toggle_h)

        track_color = TOGGLE_ON_COLOR if enabled else TOGGLE_OFF_COLOR
        pygame.draw.rect(surface, track_color, track_rect, border_radius=toggle_h // 2)

        # Hover highlight
        full_rect = self._get_toggle_rect(label, center_y)
        if full_rect.collidepoint(mouse_pos):
            hover_surf = pygame.Surface(
                (track_rect.width, track_rect.height), pygame.SRCALPHA
            )
            hover_surf.fill((255, 255, 255, 30))
            surface.blit(hover_surf, track_rect.topleft)

        # Knob
        knob_r = (toggle_h - 4) // 2
        knob_cx = (track_x + toggle_w - knob_r - 2) if enabled else (track_x + knob_r + 2)
        pygame.draw.circle(surface, TOGGLE_KNOB_COLOR, (knob_cx, center_y), knob_r)

    def _draw_timer_input(
        self,
        surface: pygame.Surface,
        text: str,
        focused: bool,
        center_x: int,
        center_y: int,
        mouse_pos: tuple[int, int],
    ) -> None:
        """Draw the seconds input box to the right of the timer toggle."""
        rect = self.get_timer_input_rect()

        # Background
        pygame.draw.rect(surface, TIMER_INPUT_BG, rect, border_radius=4)

        # Border — highlighted when focused
        border_color = TIMER_INPUT_BORDER_FOCUSED if focused else TIMER_INPUT_BORDER
        if not focused and rect.collidepoint(mouse_pos):
            border_color = (160, 160, 160)
        pygame.draw.rect(surface, border_color, rect, 2, border_radius=4)

        # Value text
        display = text if text else "–"
        text_surf = self._font_toggle_label.render(display, True, TIMER_INPUT_TEXT_COLOR)
        text_rect = text_surf.get_rect(center=rect.center)
        surface.blit(text_surf, text_rect)

        # "s" suffix
        suffix_surf = self._font_toggle_label.render("s", True, (120, 120, 120))
        surface.blit(suffix_surf, (rect.right + 4, rect.centery - suffix_surf.get_height() // 2))
