"""Display modes shared by main.py (F11) and the Settings page: full screen or a square resizable window."""
from __future__ import annotations

import pygame

from . import config, view

fullscreen: bool = True          # the mode the window is currently in


def window_side() -> int:
    """Side of the square windowed mode: WINDOW_FRACTION of the desktop height."""
    dh = pygame.display.get_desktop_sizes()[0][1]
    return max(int(dh * config.WINDOW_FRACTION), 200)


def set_display(full: bool) -> pygame.Surface:
    """Switch to full screen (desktop size) or the square resizable window; updates `view`.

    The caller re-lays-out its scene afterwards (scene.on_resize()).
    """
    global fullscreen
    fullscreen = bool(full)
    if fullscreen:
        dw, dh = pygame.display.get_desktop_sizes()[0]
        screen = pygame.display.set_mode((dw, dh), pygame.FULLSCREEN)
    else:
        side = window_side()
        screen = pygame.display.set_mode((side, side), pygame.RESIZABLE)
    view.set_size(*screen.get_size())
    return screen


def toggle() -> pygame.Surface:
    """F11: flip the mode and remember it as the start mode (config.FULLSCREEN_START)."""
    screen = set_display(not fullscreen)
    config.FULLSCREEN_START = fullscreen
    return screen
