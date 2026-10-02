"""Player controls as testable logic: movement input, the dash key / right-click, "mouse over UI".

Movement modes (config.MOVE_MODE): "WASD" (keys, unchanged) and "Mouse" (walk toward the cursor).
The scene reads the OS through `mouse_pos()` and `window_active()`, which tests replace.
"""
from __future__ import annotations

import math

import pygame

from . import config, view

MODES = ("WASD", "Mouse")
DEFAULT_DASH_KEY = "j"
# keys the dash cannot be bound to: they already do something else in the game
RESERVED_KEYS = frozenset({"return", "enter", "tab", "g", "w", "a", "s", "d", "up", "down", "left", "right",
                           "f3", "f11", "escape"})


def mouse_pos() -> tuple[int, int]:
    return pygame.mouse.get_pos()


def window_active() -> bool:
    """True while the window has keyboard focus and the cursor is inside it."""
    return bool(pygame.key.get_focused() and pygame.mouse.get_focused())


# -- dash key -------------------------------------------------------------------------------------------
def key_code(name: str) -> int | None:
    """pygame key code for a key name ('j', 'space', 'left shift'), or None if the name is unknown."""
    try:
        return pygame.key.key_code(name)
    except (ValueError, TypeError):
        return None


def dash_key_code() -> int:
    """The configured dash key; falls back to J when the stored name is not a key."""
    code = key_code(str(config.DASH_KEY))
    return code if code is not None else pygame.key.key_code(DEFAULT_DASH_KEY)


def dash_key_label() -> str:
    """The dash key as text for the UI ('J', 'SPACE')."""
    return str(config.DASH_KEY).upper() if key_code(str(config.DASH_KEY)) is not None else DEFAULT_DASH_KEY.upper()


def is_reserved(name: str) -> bool:
    return name.lower() in RESERVED_KEYS


def is_dash_event(e: pygame.event.Event) -> bool:
    """The dash key was pressed, or (Mouse mode only) the right mouse button."""
    if e.type == pygame.KEYDOWN:
        return e.key == dash_key_code()
    return e.type == pygame.MOUSEBUTTONDOWN and e.button == 3 and config.MOVE_MODE == "Mouse"


# -- movement -------------------------------------------------------------------------------------------
def keys_direction(pressed) -> tuple[float, float]:
    """WASD / arrow keys -> (dx, dy), y down. `pressed` is pygame.key.get_pressed() (or anything indexable)."""
    k = pressed
    dx = (k[pygame.K_d] or k[pygame.K_RIGHT]) - (k[pygame.K_a] or k[pygame.K_LEFT])
    dy = (k[pygame.K_s] or k[pygame.K_DOWN]) - (k[pygame.K_w] or k[pygame.K_UP])
    return float(dx), float(dy)


def aim(cursor: tuple[float, float], center: tuple[float, float] | None = None) -> tuple[float, float]:
    """Unit vector from the player (screen centre) to the cursor; (0, 0) exactly on the player."""
    cx, cy = view.center() if center is None else center
    dx, dy = cursor[0] - cx, cursor[1] - cy
    n = math.hypot(dx, dy)
    return (dx / n, dy / n) if n > 0 else (0.0, 0.0)


def mouse_direction(cursor: tuple[float, float], dead_zone: float | None = None,
                    center: tuple[float, float] | None = None) -> tuple[float, float]:
    """Walk direction toward the cursor: a unit vector, or (0, 0) inside the dead zone."""
    cx, cy = view.center() if center is None else center
    dz = config.MOUSE_DEAD_ZONE if dead_zone is None else dead_zone
    if math.hypot(cursor[0] - cx, cursor[1] - cy) <= dz:
        return 0.0, 0.0
    return aim(cursor, (cx, cy))


def ui_rects(game) -> list[pygame.Rect]:
    """Screen rects of the HUD widgets that block mouse steering (sidebar or its tab, upgrades, input, speed)."""
    sb = game.sidebar
    rects = [sb.tab_rect if sb.collapsed else sb.panel_rect, game.upgrade_panel.panel_rect,
             game.input.rect, game.speed_button.rect]
    return rects


def mouse_over_ui(game, pos: tuple[int, int]) -> bool:
    """True when `pos` is on a HUD widget (or a modal popup is open)."""
    if game.sidebar.picker_idx is not None:
        return True
    return any(r.collidepoint(pos) for r in ui_rects(game))


def read_movement(game, pressed=None) -> tuple[tuple[float, float], tuple[float, float] | None]:
    """(walk direction, facing) for this frame.

    Typing disables movement. WASD mode: keys, facing follows the walk. Mouse mode: walk toward the cursor
    (stand still inside the dead zone, over the UI, or while the window is unfocused); facing is toward the
    cursor whenever it is off the player and not over the UI.
    """
    if game.input.focused or game.sidebar.value_focused:
        return (0.0, 0.0), None
    if config.MOVE_MODE != "Mouse":
        return keys_direction(pygame.key.get_pressed() if pressed is None else pressed), None
    if not window_active():
        return (0.0, 0.0), None
    cursor = mouse_pos()
    if mouse_over_ui(game, cursor):
        return (0.0, 0.0), None
    facing = aim(cursor)
    return mouse_direction(cursor), (facing if facing != (0.0, 0.0) else None)
