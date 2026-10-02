"""Achievements page: a scrolling grid of cards (medal or grey padlock), name, description, date and n/40."""
from __future__ import annotations

from typing import Callable

import pygame

from . import config, view
from .achievements import ACHIEVEMENTS, TOTAL
from .library import line_height, wrap_text
from .profile import Profile
from .scenes import Scene
from .ui import icons
from .ui.widgets import Button, ScrollArea, draw_text, get_font


def card_model(profile: Profile) -> list[dict]:
    """One dict per achievement: id, name, desc, unlocked, date ('' when locked)."""
    return [{"id": a.id, "name": a.name, "desc": a.desc, "unlocked": profile.is_unlocked(a.id),
             "date": profile.achievements.get(a.id, "")} for a in ACHIEVEMENTS]


def counter_text(profile: Profile) -> str:
    """'n/40' unlocked counter."""
    return f"{sum(1 for a in ACHIEVEMENTS if profile.is_unlocked(a.id))}/{TOTAL}"


def grid_layout(width: int, height: int, n: int = TOTAL) -> tuple[list[pygame.Rect], int]:
    """Card rects (content space) in ACH_COLS columns and as many rows as needed, and the content height.

    Cards share the available height equally, but never get shorter than ACH_CARD_MIN_H: when the
    window is too small the grid is taller than `height` and the page scrolls."""
    cols, gap = (config.ACH_COLS if width >= config.ACH_WIDE_W else config.ACH_NARROW_COLS), config.ACH_GAP
    rows = -(-n // cols)
    w = max((width - (cols - 1) * gap) // cols, 60)
    h = max((height - (rows - 1) * gap) // rows, config.ACH_CARD_MIN_H)
    rects = [pygame.Rect((i % cols) * (w + gap), (i // cols) * (h + gap), w, h) for i in range(n)]
    return rects, rows * h + (rows - 1) * gap


class AchievementsScene(Scene):
    """Read-only trophy page. `back()` returns the scene to go to on Esc / Back."""

    def __init__(self, back: Callable[[], object], profile: Profile | None = None) -> None:
        super().__init__()
        from .profile import get_profile
        self.back = back
        self.profile = profile if profile is not None else get_profile()
        m = config.PAGE_MARGIN
        self.back_btn = Button(pygame.Rect(m, m // 2, *config.PAGE_BACK_SIZE), "Back", size=28)
        self.area = ScrollArea(pygame.Rect(0, 0, 100, 100))
        self.rects: list[pygame.Rect] = []
        self.on_resize()

    def on_resize(self) -> None:
        m, top = config.PAGE_MARGIN, config.PAGE_HEADER_H
        self.area.set_rect(pygame.Rect(m, top, max(view.W - 2 * m, 100), max(view.H - top - m, 50)))
        self.rects, h = grid_layout(self.area.rect.w - self._bar_room(), self.area.rect.h)
        self.area.set_content_height(h)

    def _bar_room(self) -> int:
        """Width kept free for the scrollbar (only when the grid scrolls)."""
        _, h = grid_layout(self.area.rect.w, self.area.rect.h)
        return config.SCROLLBAR_W + 8 if h > self.area.rect.h else 0

    def handle_event(self, e: pygame.event.Event) -> None:
        if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
            self.next_scene = self.back()
        elif self.back_btn.handle_event(e):
            self.next_scene = self.back()
        else:
            self.area.handle_event(e)

    def draw(self, screen: pygame.Surface) -> None:
        screen.fill(config.BG_COLOR)
        self.back_btn.draw(screen)
        draw_text(screen, "Achievements", config.PAGE_TITLE_FONT, config.ACCENT_COLOR,
                  (config.PAGE_MARGIN * 2 + config.PAGE_BACK_SIZE[0], config.PAGE_MARGIN // 2 + 20), "midleft")
        draw_text(screen, counter_text(self.profile), config.ACH_COUNT_FONT, config.TOAST_BORDER,
                  (view.W - config.PAGE_MARGIN, config.PAGE_MARGIN // 2 + 20), "midright")
        model = card_model(self.profile)
        old = self.area.begin_clip(screen)
        for rect, m in zip(self.rects, model):
            if self.area.visible(rect.y, rect.h):
                self._draw_card(screen, self.area.offset_rect(rect), m)
        self.area.end_clip(screen, old)
        self.area.draw_scrollbar(screen)

    @staticmethod
    def _draw_card(screen: pygame.Surface, r: pygame.Rect, m: dict) -> None:
        pad, icon = config.ACH_PAD, config.ACH_ICON
        on = m["unlocked"]
        pygame.draw.rect(screen, config.LIB_CARD_FILL if on else config.ACH_LOCKED_FILL, r, border_radius=8)
        pygame.draw.rect(screen, config.ACH_UNLOCKED_BORDER if on else config.LIB_CARD_BORDER, r,
                         width=2 if on else 1, border_radius=8)
        screen.blit(icons.medal(icon) if on else icons.padlock(icon), (r.x + pad, r.y + pad))
        x = r.x + pad + icon + pad
        name_color = config.TEXT_COLOR if on else config.DIM_TEXT_COLOR
        room = r.right - pad - x
        draw_text(screen, m["name"], config.ACH_NAME_FONT, name_color, (x, r.y + pad), max_w=room, min_size=14)
        date = f"Unlocked {m['date']}" if on else "Locked"
        draw_text(screen, date, config.ACH_DATE_FONT, config.ACH_UNLOCKED_BORDER if on else config.DIM_TEXT_COLOR,
                  (x, r.y + pad + line_height(config.ACH_NAME_FONT) + 2), max_w=room, min_size=12)
        y = r.y + pad + icon + 6
        for line in wrap_text(m["desc"], config.ACH_DESC_FONT, r.w - 2 * pad):
            draw_text(screen, line, config.ACH_DESC_FONT, config.TEXT_COLOR if on else config.DIM_TEXT_COLOR, (r.x + pad, y))
            y += line_height(config.ACH_DESC_FONT)
