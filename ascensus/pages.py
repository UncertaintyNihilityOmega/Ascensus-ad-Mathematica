"""Stats page (opened from the pause menu): Run / Player / Enemies now / Equations column groups."""
from __future__ import annotations

from typing import Callable

import pygame

from . import config, view
from .scenes import Scene
from .stats import build_stats
from .ui.widgets import Button, draw_text


def column_layout(n_groups: int, width: int) -> tuple[int, int]:
    """(columns, column width) for the stats groups: four across when wide, otherwise two by two."""
    m = config.PAGE_MARGIN
    cols = n_groups if width >= config.STATS_WIDE_W else min(2, n_groups)
    return cols, (width - 2 * m - (cols - 1) * m) // cols


class StatsScene(Scene):
    """Live stats of a (paused) game. `back` is a zero-argument callable returning the Scene to go to."""

    def __init__(self, game, back: Callable[[], Scene]) -> None:
        super().__init__()
        self.game = game
        self.back = back
        self.back_btn = Button(pygame.Rect(0, 0, *config.PAGE_BACK_SIZE), "Back", size=config.BODY_FONT + 2)
        self.groups = build_stats(game)
        self.on_resize()

    def on_resize(self) -> None:
        self.back_btn.rect.topright = (view.W - config.PAGE_MARGIN, config.PAGE_MARGIN)

    def update(self, dt: float) -> None:
        self.groups = build_stats(self.game)

    def handle_event(self, e: pygame.event.Event) -> None:
        if self.back_btn.handle_event(e) or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
            self.next_scene = self.back()

    def draw(self, screen: pygame.Surface) -> None:
        screen.fill(config.BG_COLOR)
        m = config.PAGE_MARGIN
        draw_text(screen, "Stats", config.PAGE_TITLE_FONT, config.ACCENT_COLOR, (m, m))
        self.back_btn.draw(screen)
        cols, cw = column_layout(len(self.groups), view.W)
        y0 = config.PAGE_HEADER_H + m
        row_y = y0
        font, lh = config.STATS_FONT, config.STATS_LINE_H
        for i, (title, rows) in enumerate(self.groups):
            col = i % cols
            if col == 0 and i:
                row_y = y0 + self._group_h(self.groups[i - cols:i]) + m
            x = m + col * (cw + m)
            draw_text(screen, title, config.STATS_HEAD_FONT, config.ACCENT_COLOR, (x, row_y), max_w=cw)
            pygame.draw.line(screen, config.BUTTON_BORDER, (x, row_y + 30), (x + cw, row_y + 30))
            for j, (label, value) in enumerate(rows):
                y = row_y + 40 + j * lh
                draw_text(screen, label, font, config.DIM_TEXT_COLOR, (x, y), max_w=int(cw * 0.58), min_size=14)
                draw_text(screen, value, font, config.TEXT_COLOR, (x + cw, y), "topright",
                          max_w=int(cw * 0.4), min_size=14)

    @staticmethod
    def _group_h(groups) -> int:
        """Height of one row of groups (the tallest one)."""
        return 40 + max(len(rows) for _, rows in groups) * config.STATS_LINE_H
