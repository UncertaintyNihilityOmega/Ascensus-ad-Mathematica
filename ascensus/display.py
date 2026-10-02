"""Display modes shared by main.py (F11) and the Settings page: full screen, or a resizable window that
always fits the screen (title bar included) and opens centred."""
from __future__ import annotations

import warnings

import pygame

from ascensus import config, view

fullscreen: bool = True          # the mode the window is currently in


def work_area() -> tuple[pygame.Rect, int, int]:
    """(usable desktop rect without the taskbar, title-bar height, frame thickness).

    Windows asks the OS (SPI_GETWORKAREA, SM_CYCAPTION, SM_CYFRAME); elsewhere the whole desktop is used
    with typical decoration sizes.
    """
    dw, dh = pygame.display.get_desktop_sizes()[0]
    try:
        import ctypes
        from ctypes import wintypes
        r = wintypes.RECT()
        if ctypes.windll.user32.SystemParametersInfoW(0x30, 0, ctypes.byref(r), 0):     # SPI_GETWORKAREA
            area = pygame.Rect(r.left, r.top, r.right - r.left, r.bottom - r.top)
            caption = int(ctypes.windll.user32.GetSystemMetrics(4))                        # SM_CYCAPTION
            frame = int(ctypes.windll.user32.GetSystemMetrics(33))                         # SM_CYFRAME
            if area.w > 0 and area.h > 0:
                return area, caption, frame
    except (AttributeError, OSError, ImportError):
        pass
    return pygame.Rect(0, 0, dw, dh), 30, 4


def window_geometry(area: pygame.Rect, caption: int, frame: int, fraction: float,
                    min_size: tuple[int, int]) -> tuple[tuple[int, int], tuple[int, int], tuple[int, int]]:
    """((w, h), (x, y), minimum (w, h)) of the windowed mode, so the whole window, title bar included,
    fits inside the work area `area`.

    The client area is a square of `fraction` x the usable height, widened to the minimum width when the
    screen is short (it never gets taller than the usable height), centred in the work area.
    """
    usable_w = max(area.w - 2 * frame, 1)
    usable_h = max(area.h - caption - 2 * frame, 1)
    min_w, min_h = min(min_size[0], usable_w), min(min_size[1], usable_h)
    side = int(usable_h * fraction)
    w = min(max(side, min_w), usable_w)
    h = min(max(side, min_h), usable_h)
    x = area.x + (area.w - w) // 2
    y = area.y + caption + frame + (usable_h - h) // 2
    return (w, h), (x, y), (min_w, min_h)


def window_size() -> tuple[int, int]:
    """Client size of the windowed mode on this screen (see window_geometry)."""
    area, caption, frame = work_area()
    return window_geometry(area, caption, frame, config.WINDOW_FRACTION, config.WINDOW_MIN_SIZE)[0]


def _place_window(pos: tuple[int, int], min_size: tuple[int, int]) -> bool:
    """Move the window to `pos` and set its minimum size. False if the platform does not support it."""
    try:
        with warnings.catch_warnings():         # pygame-ce 2.5 flags from_display_module; no replacement yet
            warnings.simplefilter("ignore", DeprecationWarning)
            win = pygame.Window.from_display_module()
        win.minimum_size = tuple(min_size)
        win.position = tuple(pos)
        return True
    except (AttributeError, pygame.error, TypeError):
        return False


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
        area, caption, frame = work_area()
        size, pos, min_size = window_geometry(area, caption, frame, config.WINDOW_FRACTION,
                                              config.WINDOW_MIN_SIZE)
        screen = pygame.display.set_mode(size, pygame.RESIZABLE)
        _place_window(pos, min_size)
    view.set_size(*screen.get_size())
    return screen


def toggle() -> pygame.Surface:
    """F11: flip the mode and remember it as the start mode (config.FULLSCREEN_START)."""
    screen = set_display(not fullscreen)
    config.FULLSCREEN_START = fullscreen
    return screen
