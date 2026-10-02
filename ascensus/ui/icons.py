"""Icons: white Kenney CC0 PNGs from assets/icons/ tinted on demand, plus a few drawn in code.

`icon(name, size, color)` returns a square surface, cached by (name, size, color). "play" is not in the
Kenney packs and is drawn with primitives; the other drawers below are fallbacks used only when a PNG is
missing (assets/icons is fetched by tools/fetch_icons.py). No Unicode glyphs anywhere.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Callable

import pygame

from .. import config

BASE = 96                                       # drawn-in-code icons are painted at this size, then scaled
ICON_DIR = Path(__file__).resolve().parent.parent.parent / "assets" / "icons"
Color = tuple[int, ...]
WHITE = (255, 255, 255)
CLEAR = (0, 0, 0, 0)

ICON_NAMES = ("skull", "reset", "undo", "play", "pause", "fast_forward", "trash", "pencil", "plus", "minus",
              "cross", "save", "gear", "book", "trophy", "medal", "padlock", "arrow_left", "arrow_right", "home")
_ALIASES = {"lock": "padlock", "trashcan": "trash", "delete": "trash", "edit": "pencil", "refresh": "reset",
            "ff": "fast_forward", "left": "arrow_left", "right": "arrow_right"}

SKULL_COLOR: Color = (230, 60, 60)
MEDAL_COLOR: Color = (255, 205, 60)
LOCK_COLOR: Color = (130, 135, 150)
_DEFAULTS: dict[str, Color] = {"skull": SKULL_COLOR, "medal": MEDAL_COLOR, "padlock": LOCK_COLOR}

_cache: dict[tuple, pygame.Surface] = {}        # (name, size, color) -> tinted icon
_white: dict[str, pygame.Surface] = {}          # name -> white source image (PNG or drawn)


# --- drawn in code (play always; the rest only when a PNG is missing) -------------------------------
def _new() -> pygame.Surface:
    return pygame.Surface((BASE, BASE), pygame.SRCALPHA)


def _draw_play() -> pygame.Surface:
    s = _new()
    pygame.draw.polygon(s, WHITE, [(26, 10), (26, 86), (84, 48)])
    return s


def _draw_pause() -> pygame.Surface:
    s = _new()
    pygame.draw.rect(s, WHITE, (22, 12, 18, 72), border_radius=3)
    pygame.draw.rect(s, WHITE, (56, 12, 18, 72), border_radius=3)
    return s


def _draw_plus() -> pygame.Surface:
    s = _new()
    pygame.draw.rect(s, WHITE, (10, 38, 76, 20), border_radius=4)
    pygame.draw.rect(s, WHITE, (38, 10, 20, 76), border_radius=4)
    return s


def _draw_minus() -> pygame.Surface:
    s = _new()
    pygame.draw.rect(s, WHITE, (10, 38, 76, 20), border_radius=4)
    return s


def _draw_cross() -> pygame.Surface:
    s = _new()
    pygame.draw.line(s, WHITE, (14, 14), (82, 82), 16)
    pygame.draw.line(s, WHITE, (14, 82), (82, 14), 16)
    return s


def _draw_reset() -> pygame.Surface:
    s = _new()
    pygame.draw.arc(s, WHITE, pygame.Rect(14, 14, 68, 68), 0.7, 6.0, 12)     # open circle, arrowhead at its start
    pygame.draw.polygon(s, WHITE, [(48, 4), (48, 36), (22, 20)])
    return s


def _star(cx: float, cy: float, r_out: float, r_in: float, n: int = 5) -> list[tuple[float, float]]:
    pts = []
    for i in range(n * 2):
        r = r_out if i % 2 == 0 else r_in
        a = -math.pi / 2 + i * math.pi / n
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def _draw_skull() -> pygame.Surface:
    s = _new()
    pygame.draw.circle(s, WHITE, (48, 38), 33)                                   # cranium
    pygame.draw.rect(s, WHITE, (24, 56, 48, 34), border_radius=10)               # jaw
    for cx in (33, 63):                                                          # pi-shaped eye sockets
        pygame.draw.rect(s, CLEAR, (cx - 10, 32, 20, 5), border_radius=2)
        pygame.draw.rect(s, CLEAR, (cx - 7, 36, 5, 14), border_radius=2)
        pygame.draw.rect(s, CLEAR, (cx + 2, 36, 5, 14), border_radius=2)
    pygame.draw.polygon(s, CLEAR, [(41, 52), (55, 52), (48, 64)])                # nabla nose
    for cx in (34, 48, 62):                                                      # '=' teeth marks
        pygame.draw.rect(s, CLEAR, (cx - 5, 71, 10, 3))
        pygame.draw.rect(s, CLEAR, (cx - 5, 79, 10, 3))
    return s


def _draw_medal() -> pygame.Surface:
    s = _new()
    pygame.draw.polygon(s, WHITE, [(26, 4), (44, 4), (58, 46), (40, 46)])        # ribbon legs
    pygame.draw.polygon(s, WHITE, [(70, 4), (52, 4), (38, 46), (56, 46)])
    pygame.draw.circle(s, WHITE, (48, 66), 28)
    pygame.draw.polygon(s, CLEAR, _star(48, 67, 14, 6))
    return s


def _draw_padlock() -> pygame.Surface:
    s = _new()
    pygame.draw.circle(s, WHITE, (48, 34), 22, 7)                                # shackle
    pygame.draw.rect(s, CLEAR, (20, 34, 56, 24))
    pygame.draw.rect(s, WHITE, (26, 34, 7, 24))
    pygame.draw.rect(s, WHITE, (63, 34, 7, 24))
    pygame.draw.rect(s, WHITE, (16, 52, 64, 40), border_radius=8)                # body
    pygame.draw.circle(s, CLEAR, (48, 67), 6)                                    # keyhole
    pygame.draw.rect(s, CLEAR, (45, 70, 6, 12))
    return s


def _draw_missing() -> pygame.Surface:
    """Placeholder for a known icon whose PNG is absent: a rounded outline."""
    s = _new()
    pygame.draw.rect(s, WHITE, (10, 10, 76, 76), 10, border_radius=14)
    return s


_DRAWERS: dict[str, Callable[[], pygame.Surface]] = {
    "play": _draw_play, "pause": _draw_pause, "plus": _draw_plus, "minus": _draw_minus,
    "cross": _draw_cross, "reset": _draw_reset, "skull": _draw_skull, "medal": _draw_medal,
    "padlock": _draw_padlock,
}


# --- loading, tinting, caching ------------------------------------------------------------------------
def _source(name: str) -> pygame.Surface:
    """The white source image of `name`: the PNG when present (except for code-only icons), else drawn."""
    img = _white.get(name)
    if img is not None:
        return img
    path = ICON_DIR / f"{name}.png"
    if name != "play" and path.is_file():
        raw = pygame.image.load(str(path))
        img = pygame.Surface(raw.get_size(), pygame.SRCALPHA)
        img.blit(raw, (0, 0))
    else:
        img = _DRAWERS.get(name, _draw_missing)()
    _white[name] = img
    return img


def has_png(name: str) -> bool:
    """True when `name` is backed by a PNG in assets/icons (False for play and for missing files)."""
    return name != "play" and (ICON_DIR / f"{_ALIASES.get(name, name)}.png").is_file()


def icon(name: str, size: int, color: Color = WHITE) -> pygame.Surface:
    """Square icon `name` of side `size` px tinted `color` (RGB or RGBA); cached per (name, size, color)."""
    name = _ALIASES.get(name, name)
    if name not in ICON_NAMES:
        raise KeyError(f"unknown icon {name!r}")
    size = max(int(size), 1)
    color = tuple(int(c) for c in color)
    key = (name, size, color)
    img = _cache.get(key)
    if img is None:
        src = _source(name)
        img = src.copy() if src.get_size() == (size, size) else pygame.transform.smoothscale(src, (size, size))
        img.fill(color if len(color) == 4 else (*color[:3], 255), special_flags=pygame.BLEND_RGBA_MULT)
        _cache[key] = img
    return img


def get_icon(name: str, height: int, color: Color | None = None) -> pygame.Surface:
    """Like icon(), with a default tint per icon (red skull, gold medal, grey padlock, else config.ICON_COLOR)."""
    name = _ALIASES.get(name, name)
    return icon(name, height, color if color is not None else _DEFAULTS.get(name, config.ICON_COLOR))


def skull(height: int, color: Color | None = None) -> pygame.Surface:
    """The red skull used in the HUD kill counter."""
    return get_icon("skull", height, color)


def medal(height: int, color: Color | None = None) -> pygame.Surface:
    """Gold medal for unlocked achievements."""
    return get_icon("medal", height, color)


def padlock(height: int, color: Color | None = None) -> pygame.Surface:
    """Grey padlock for locked achievements."""
    return get_icon("padlock", height, color)
