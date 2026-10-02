"""The main menu: Continue / Play / Saves / Settings / Library / Achievements / Quit and the best run."""
from __future__ import annotations

import pygame

from ascensus import config, view
from ascensus.core.curvefield import build_curve, render_curve
from ascensus.core.mathparse import parse_equation
from ascensus.game.profile import get_profile
from ascensus.game.savegame import SlotStore
from ascensus.scenes import game as game_scene
from ascensus.scenes.base import QUIT, Scene, button_stack, centered_button, fmt_time, open_page
from ascensus.ui.widgets import Button, draw_text


class MenuScene(Scene):
    """Title, [Continue (mm:ss)] / Play / Saves / Settings / Library / Achievements / Quit and the best run."""

    LABELS = ("Play", "Saves", "Settings", "Library", "Achievements", "Quit")

    def __init__(self, store: SlotStore | None = None) -> None:
        super().__init__()
        self.store = store if store is not None else SlotStore()
        info = self.store.autosave_info()
        self.continue_time: float | None = info.game_t if info is not None else None
        self.play = self.quit = centered_button(0, 0, "")
        self.buttons: dict[str, Button] = {}
        self.top = 0
        self.on_resize()
        self.t = 0.0
        self.rebuild_timer = config.MENU_CURVE_REBUILD       # build on the first update
        self.curve_func = parse_equation(config.MENU_CURVE).func
        self.curve_surf: pygame.Surface | None = None

    def _names(self) -> list[str]:
        return (["Continue"] if self.continue_time is not None else []) + list(self.LABELS)

    def on_resize(self) -> None:
        names = self._names()
        self.top, rects = button_stack(len(names), 130, 44)
        self.buttons = {}
        for name, rect in zip(names, rects):
            label = f"Continue ({fmt_time(self.continue_time)})" if name == "Continue" else name
            self.buttons[name] = Button(rect, label)
        self.play, self.quit = self.buttons["Play"], self.buttons["Quit"]
        self.rebuild_timer = config.MENU_CURVE_REBUILD       # redraw the curve at the new size

    def update(self, dt: float) -> None:
        """Animate the background curve (rebuilt at ~10 Hz on the coarse grid)."""
        self.t += dt
        self.rebuild_timer += dt
        if self.rebuild_timer >= config.MENU_CURVE_REBUILD:
            self.rebuild_timer = 0.0
            curve = build_curve(self.curve_func, self.t, config.GRID_STEP)
            self.curve_surf = render_curve(curve.points, config.ACCENT_COLOR)
            self.curve_surf.set_alpha(config.MENU_CURVE_ALPHA)

    def continue_game(self) -> None:
        """Load the autosave into a GameScene; an unreadable autosave is deleted and the button disappears."""
        from ascensus.game.savegame import restore
        data = self.store.load_autosave()
        try:
            if data is None:
                raise ValueError("no autosave")
            self.next_scene = restore(data)
        except ValueError:
            self.store.delete_autosave()
            self.continue_time = None
            self.on_resize()

    def handle_event(self, e: pygame.event.Event) -> None:
        if self.play.handle_event(e) or (e.type == pygame.KEYDOWN and e.key == pygame.K_RETURN):
            self.next_scene = game_scene.GameScene()
        elif "Continue" in self.buttons and self.buttons["Continue"].handle_event(e):
            self.continue_game()
        elif self.quit.handle_event(e):
            self.next_scene = QUIT
        else:
            for name in ("Saves", "Settings", "Library", "Achievements"):
                if self.buttons[name].handle_event(e):
                    self.next_scene = open_page(name.lower(), lambda: MenuScene(self.store))
                    break

    def draw(self, screen: pygame.Surface) -> None:
        screen.fill(config.BG_COLOR)
        if self.curve_surf is not None:
            screen.blit(self.curve_surf, (0, 0))
        cx, wmax = view.W // 2, view.W - 40
        draw_text(screen, config.TITLE, config.TITLE_FONT, config.ACCENT_COLOR, (cx, self.top + 36), "center",
                  max_w=wmax, min_size=28)
        draw_text(screen, "Survive with equations", config.SUBTITLE_FONT,
                  config.TEXT_COLOR, (cx, self.top + 100), "center", max_w=wmax, min_size=18)
        for b in self.buttons.values():
            b.draw(screen)
        last = self.quit.rect.bottom
        draw_text(screen, get_profile().best_text(), config.BODY_FONT, config.DIM_TEXT_COLOR,
                  (cx, last + 24), "center", max_w=wmax, min_size=14)
