"""The game-speed button next to the timer: a semi-transparent pill showing 1x / 2x / 3x with a fast-forward icon."""
from __future__ import annotations

import pygame

from .. import config, view
from .widgets import draw_text, get_font


def next_speed(speed: int) -> int:
    """1 -> 2 -> 3 -> 1 (the steps in config.SPEED_STEPS; an unknown value restarts at the first)."""
    steps = list(config.SPEED_STEPS)
    return steps[(steps.index(speed) + 1) % len(steps)] if speed in steps else steps[0]


def draw_fast_forward(surf: pygame.Surface, rect: pygame.Rect, color: tuple[int, ...]) -> None:
    """Two right-pointing triangles filling `rect` (primitives only)."""
    half = rect.w // 2
    for x0 in (rect.left, rect.left + half):
        pygame.draw.polygon(surf, color, [(x0, rect.top), (x0 + half, rect.centery), (x0, rect.bottom)])


class SpeedButton:
    """Click cycles the speed. The scene owns the speed value; this widget only shows it and reports clicks."""

    def __init__(self) -> None:
        self.rect = pygame.Rect(0, 0, *config.SPEED_BTN_SIZE)
        self._bg: pygame.Surface | None = None
        self.on_resize()

    def on_resize(self) -> None:
        """Sit just right of the centred timer, vertically centred on its text."""
        w, h = config.SPEED_BTN_SIZE
        timer_w = get_font(config.HUD_TIMER_FONT).size("88:88")[0]
        timer_h = get_font(config.HUD_TIMER_FONT).size("88:88")[1]
        self.rect = pygame.Rect(view.W // 2 + timer_w // 2 + config.SPEED_BTN_GAP,
                                config.HUD_MARGIN + (timer_h - h) // 2, w, h)
        self._bg = None

    def handle_event(self, e: pygame.event.Event) -> bool:
        """True on a left click inside the button."""
        return e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and self.rect.collidepoint(e.pos)

    def _background(self, hover: bool) -> pygame.Surface:
        if self._bg is None or self._bg.get_size() != self.rect.size:
            self._bg = pygame.Surface(self.rect.size, pygame.SRCALPHA)
        fill = config.BUTTON_HOVER_FILL if hover else config.BUTTON_FILL
        self._bg.fill((0, 0, 0, 0))
        pygame.draw.rect(self._bg, (*fill, config.SPEED_BTN_ALPHA), self._bg.get_rect(), border_radius=8)
        border = config.ACCENT_COLOR if hover else config.BUTTON_BORDER
        pygame.draw.rect(self._bg, (*border, config.SPEED_BTN_ALPHA + 60), self._bg.get_rect(), width=2,
                         border_radius=8)
        return self._bg

    def draw(self, screen: pygame.Surface, speed: int) -> None:
        hover = self.rect.collidepoint(pygame.mouse.get_pos())
        screen.blit(self._background(hover), self.rect)
        icon_h = self.rect.h // 2 - 2
        icon = pygame.Rect(0, 0, icon_h + 4, icon_h)
        icon.midleft = (self.rect.left + 10, self.rect.centery)
        color = config.ACCENT_COLOR if speed > config.SPEED_STEPS[0] else config.TEXT_COLOR
        draw_fast_forward(screen, icon, color)
        draw_text(screen, f"{speed}x", config.SPEED_BTN_FONT, color, (self.rect.right - 10, self.rect.centery),
                  "midright", max_w=self.rect.right - icon.right - 14, min_size=14)
