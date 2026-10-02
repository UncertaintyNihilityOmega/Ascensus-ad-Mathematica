"""The 'Deleted eq4 - Undo' toast shown for a few seconds after an equation is deleted."""
from __future__ import annotations

import pygame

from ascensus import config, view
from ascensus.ui.widgets import draw_text, get_font, truncate

NAME_MAX_W = 220                 # the equation name is cut with '...' beyond this many pixels


class UndoToast:
    """A small box with a clickable 'Undo'. The owner calls update(dt) / draw(screen) every frame and
    on_resize() when the window changes; handle_event() returns True when the Undo part was clicked
    (the toast then hides itself and the owner calls EquationManager.undo_delete())."""

    def __init__(self) -> None:
        self.name = ""
        self.left = 0.0                    # seconds still to show
        self.top = (config.HUD_MARGIN + config.HUD_TIMER_FONT + 2 * config.TOAST_GAP
                    + config.TOAST_FONT + 2 * config.TOAST_PAD)       # below the achievement toast
        self.box = pygame.Rect(0, 0, 10, 10)
        self.undo_rect = pygame.Rect(0, 0, 10, 10)
        self._lead = ""                    # the 'Deleted eq4 - ' part
        self._lead_w = 0
        self._undo_w = 0
        self.on_resize()

    @property
    def active(self) -> bool:
        return self.left > 0

    def show(self, name: str) -> None:
        """Show 'Deleted <name> - Undo' for UNDO_TOAST_TIME seconds (replacing any toast already up)."""
        self.name = name
        self.left = config.UNDO_TOAST_TIME
        self.on_resize()

    def hide(self) -> None:
        self.left = 0.0

    def on_resize(self) -> None:
        """Re-centre the box for the current window (also re-measures the text)."""
        font = get_font(config.UNDO_TOAST_FONT)
        name = truncate(self.name, config.UNDO_TOAST_FONT, NAME_MAX_W)
        self._lead = f"Deleted {name} - "
        self._lead_w = font.size(self._lead)[0]
        self._undo_w = font.size("Undo")[0]
        pad = config.TOAST_PAD
        w = self._lead_w + self._undo_w + 2 * pad
        h = font.get_height() + 2 * pad
        self.box = pygame.Rect(0, 0, min(w, max(view.W - 20, 50)), h)
        self.box.midtop = (view.W // 2, self.top)
        self.undo_rect = pygame.Rect(self.box.left + pad + self._lead_w - 4, self.box.top,
                                     self._undo_w + 8 + pad, self.box.h)

    def update(self, dt: float) -> None:
        if self.left > 0:
            self.left = max(self.left - dt, 0.0)

    def handle_event(self, e: pygame.event.Event) -> bool:
        """True when a left click hit 'Undo' (the toast hides); other events are ignored."""
        if (self.active and e.type == pygame.MOUSEBUTTONDOWN and e.button == 1
                and self.undo_rect.collidepoint(e.pos)):
            self.hide()
            return True
        return False

    def draw(self, screen: pygame.Surface) -> None:
        if not self.active:
            return
        pad = config.TOAST_PAD
        pygame.draw.rect(screen, config.TOAST_FILL, self.box, border_radius=8)
        pygame.draw.rect(screen, config.BUTTON_BORDER, self.box, width=2, border_radius=8)
        mid = self.box.centery
        left = draw_text(screen, self._lead, config.UNDO_TOAST_FONT, config.TEXT_COLOR,
                         (self.box.left + pad, mid), "midleft", max_w=self.box.w - 2 * pad - self._undo_w)
        hover = self.undo_rect.collidepoint(pygame.mouse.get_pos())
        color = config.TEXT_COLOR if hover else config.ACCENT_COLOR
        r = draw_text(screen, "Undo", config.UNDO_TOAST_FONT, color, (left.right, mid), "midleft")
        pygame.draw.line(screen, color, (r.left, r.bottom - 4), (r.right, r.bottom - 4))
