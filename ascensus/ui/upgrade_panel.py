"""Bottom-right upgrades panel: Max HP / Base DMG / Cooldown buy buttons and the Auto toggle."""
from __future__ import annotations

from typing import Callable

import pygame

from .. import config, view
from ..upgrades import STATS, Upgrades
from .widgets import draw_text


class UpgradePanel:
    """Four stacked buttons. `on_buy(stat)` is called on a click of an affordable stat button."""

    def __init__(self, ups: Upgrades, on_buy: Callable[[str], None]) -> None:
        self.ups = ups
        self.on_buy = on_buy
        self.rects: dict[str, pygame.Rect] = {}
        self.on_resize()

    def on_resize(self) -> None:
        """Re-anchor to the bottom-right corner of the current view."""
        w, h, gap, m = config.UPG_PANEL_W, config.UPG_BTN_H, config.UPG_GAP, config.HUD_MARGIN
        names = (*STATS, "auto")
        top = view.H - m - len(names) * h - (len(names) - 1) * gap
        self.rects = {n: pygame.Rect(view.W - m - w, top + i * (h + gap), w, h)
                      for i, n in enumerate(names)}
        self.panel_rect = self.rects[names[0]].unionall(list(self.rects.values()))

    def handle_event(self, e: pygame.event.Event) -> bool:
        """Returns True when the event was inside the panel (so nothing underneath sees it)."""
        if e.type not in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
            return False
        if not self.panel_rect.collidepoint(e.pos):
            return False
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            if self.rects["auto"].collidepoint(e.pos):
                self.ups.auto = not self.ups.auto
            else:
                for stat in STATS:
                    if self.rects[stat].collidepoint(e.pos) and self.ups.affordable(stat):
                        self.on_buy(stat)
        return True

    def draw(self, screen: pygame.Surface) -> None:
        mouse = pygame.mouse.get_pos()
        for name, r in self.rects.items():
            if name == "auto":
                on = self.ups.auto
                label, enabled = f"Auto: {'ON' if on else 'OFF'}", True
                fill = config.UPG_AUTO_ON_FILL if on else config.BUTTON_FILL
            else:
                label, enabled = self.ups.label(name), self.ups.affordable(name)
                fill = config.BUTTON_FILL
            hover = enabled and r.collidepoint(mouse)
            if hover:
                fill = config.BUTTON_HOVER_FILL
            pygame.draw.rect(screen, fill, r, border_radius=8)
            border = config.ACCENT_COLOR if hover else config.BUTTON_BORDER
            if not enabled:
                border = config.UPG_DISABLED_COLOR
            pygame.draw.rect(screen, border, r, width=2, border_radius=8)
            color = config.TEXT_COLOR if enabled else config.UPG_DISABLED_COLOR
            draw_text(screen, label, config.UPG_FONT, color, r.center, "center")
