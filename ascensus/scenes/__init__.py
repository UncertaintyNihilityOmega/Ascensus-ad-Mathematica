"""Screens of the game: menu, game, game over and the pages (settings, library, achievements, saves,
stats). Each scene has handle_event / update / draw and sets `next_scene` to switch."""
from ascensus.scenes.base import QUIT, Scene, button_stack, fmt_time, open_page
from ascensus.scenes.game import GameScene, make_dot_surface, make_grid
from ascensus.scenes.game_over import GameOverScene
from ascensus.scenes.menu import MenuScene

__all__ = ["QUIT", "Scene", "button_stack", "fmt_time", "open_page", "GameScene", "make_dot_surface",
           "make_grid", "GameOverScene", "MenuScene"]
