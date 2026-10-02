"""KeyField: a key-binding box. Click it, press a key to bind it, Esc (or a click elsewhere) cancels."""
from __future__ import annotations

import pygame

from ascensus import config
from ascensus.game import controls
from ascensus.ui.widgets import draw_text


class KeyField:
    """Shows the bound key name; `handle_event` returns the new pygame key name when one was bound."""

    def __init__(self, rect: pygame.Rect, name: str) -> None:
        self.rect = pygame.Rect(rect)
        self.name = name
        self.listening = False
        self.message = ""            # shown while listening after a rejected key

    def set_rect(self, rect: pygame.Rect) -> None:
        self.rect = pygame.Rect(rect)

    def cancel(self) -> None:
        self.listening = False
        self.message = ""

    def handle_event(self, e: pygame.event.Event) -> str | None:
        """Click toggles listening; while listening a key press binds (Esc cancels). Returns the bound name."""
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            if self.rect.collidepoint(e.pos):
                self.listening, self.message = not self.listening, ""
            else:
                self.cancel()
            return None
        if self.listening and e.type == pygame.KEYDOWN:
            if e.key == pygame.K_ESCAPE:
                self.cancel()
                return None
            name = pygame.key.name(e.key)
            if not name or name.startswith("unknown") or controls.is_reserved(name):
                self.message = "Key in use"
                return None
            self.name = name
            self.cancel()
            return name
        return None

    def draw(self, screen: pygame.Surface) -> None:
        r = self.rect
        pygame.draw.rect(screen, config.INPUT_FILL, r, border_radius=6)
        border = config.INPUT_BORDER_FOCUS if self.listening else config.INPUT_BORDER
        pygame.draw.rect(screen, border, r, width=2, border_radius=6)
        if self.listening:
            text, color = self.message or "Press a key...", config.ACCENT_COLOR
        else:
            text, color = self.name.upper(), config.TEXT_COLOR
        draw_text(screen, text, config.KEYFIELD_FONT, color, r.center, "center", max_w=r.w - 12, min_size=14)
