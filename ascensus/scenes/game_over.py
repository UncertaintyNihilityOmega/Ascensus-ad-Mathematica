"""The game over screen: survival time, kills, Retry / Main Menu."""
from __future__ import annotations

import pygame

from ascensus import config, view
from ascensus.scenes import game as game_scene
from ascensus.scenes import menu as menu_scene
from ascensus.scenes.base import Scene, centered_button, fmt_time
from ascensus.ui.widgets import draw_text


class GameOverScene(Scene):
    """Survival time, kills, Retry / Main Menu."""

    def __init__(self, survived: float, kills: int) -> None:
        super().__init__()
        self.survived = survived
        self.kills = kills
        self.retry = self.menu = centered_button(0, 0, "")
        self.on_resize()

    def on_resize(self) -> None:
        cx, cy = view.W // 2, view.H // 2
        self.retry = centered_button(cx, cy + 40, "Retry")
        self.menu = centered_button(cx, cy + 110, "Main Menu")

    def handle_event(self, e: pygame.event.Event) -> None:
        if self.retry.handle_event(e):
            self.next_scene = game_scene.GameScene()
        elif self.menu.handle_event(e):
            self.next_scene = menu_scene.MenuScene()

    def draw(self, screen: pygame.Surface) -> None:
        screen.fill(config.BG_COLOR)
        cx, cy = view.W // 2, view.H // 2
        draw_text(screen, "You died", config.TITLE_FONT, config.DANGER_COLOR, (cx, cy - 190), "center")
        draw_text(screen, f"You survived {fmt_time(self.survived)}", config.SUBTITLE_FONT + 10,
                  config.TEXT_COLOR, (cx, cy - 90), "center")
        draw_text(screen, f"Kills: {self.kills}", config.SUBTITLE_FONT,
                  config.TEXT_COLOR, (cx, cy - 40), "center")
        self.retry.draw(screen)
        self.menu.draw(screen)
