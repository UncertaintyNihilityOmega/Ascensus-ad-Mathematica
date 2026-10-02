"""Icons drawn with primitives (no glyphs): skull, medal, padlock. Drawn at 96 px, smoothscaled and cached."""
from __future__ import annotations

import math
from typing import Callable

import pygame

BASE = 96
CLEAR = (0, 0, 0, 0)
Color = tuple[int, int, int]

SKULL_COLOR: Color = (230, 60, 60)
MEDAL_COLOR: Color = (255, 205, 60)
LOCK_COLOR: Color = (130, 135, 150)

_cache: dict[tuple, pygame.Surface] = {}


def _new() -> pygame.Surface:
    return pygame.Surface((BASE, BASE), pygame.SRCALPHA)


def _eye(s: pygame.Surface, cx: int) -> None:
    """A pi-shaped eye socket (bar on top, two legs) punched out of the skull."""
    pygame.draw.rect(s, CLEAR, (cx - 10, 32, 20, 5), border_radius=2)
    pygame.draw.rect(s, CLEAR, (cx - 7, 36, 5, 14), border_radius=2)
    pygame.draw.rect(s, CLEAR, (cx + 2, 36, 5, 14), border_radius=2)


def _draw_skull(color: Color) -> pygame.Surface:
    s = _new()
    pygame.draw.circle(s, color, (48, 38), 33)                                   # cranium
    pygame.draw.rect(s, color, (24, 56, 48, 34), border_radius=10)               # jaw
    _eye(s, 33)
    _eye(s, 63)
    pygame.draw.polygon(s, CLEAR, [(41, 52), (55, 52), (48, 64)])                # nabla nose
    for cx in (34, 48, 62):                                                      # '=' teeth marks
        pygame.draw.rect(s, CLEAR, (cx - 5, 71, 10, 3))
        pygame.draw.rect(s, CLEAR, (cx - 5, 79, 10, 3))
    return s


def _star(cx: float, cy: float, r_out: float, r_in: float, n: int = 5) -> list[tuple[float, float]]:
    pts = []
    for i in range(n * 2):
        r = r_out if i % 2 == 0 else r_in
        a = -math.pi / 2 + i * math.pi / n
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def _draw_medal(color: Color) -> pygame.Surface:
    s = _new()
    pygame.draw.polygon(s, (200, 50, 60), [(26, 4), (44, 4), (58, 46), (40, 46)])   # ribbon legs
    pygame.draw.polygon(s, (60, 100, 220), [(70, 4), (52, 4), (38, 46), (56, 46)])
    dark = tuple(int(c * 0.6) for c in color)
    pygame.draw.circle(s, dark, (48, 66), 28)
    pygame.draw.circle(s, color, (48, 66), 25)
    pygame.draw.circle(s, dark, (48, 66), 19, 2)
    pygame.draw.polygon(s, dark, _star(48, 67, 14, 6))
    return s


def _draw_lock(color: Color) -> pygame.Surface:
    s = _new()
    dark = tuple(int(c * 0.55) for c in color)
    pygame.draw.circle(s, color, (48, 34), 22, 7)                                # shackle
    pygame.draw.rect(s, CLEAR, (20, 34, 56, 24))                                 # open the arc's lower half
    pygame.draw.rect(s, color, (26, 34, 7, 24))
    pygame.draw.rect(s, color, (63, 34, 7, 24))
    pygame.draw.rect(s, color, (16, 52, 64, 40), border_radius=8)                # body
    pygame.draw.rect(s, dark, (16, 52, 64, 40), 2, border_radius=8)
    pygame.draw.circle(s, dark, (48, 67), 6)                                     # keyhole
    pygame.draw.rect(s, dark, (45, 70, 6, 12))
    return s


_DRAWERS: dict[str, tuple[Callable[[Color], pygame.Surface], Color]] = {
    "skull": (_draw_skull, SKULL_COLOR),
    "medal": (_draw_medal, MEDAL_COLOR),
    "lock": (_draw_lock, LOCK_COLOR),
}


def get_icon(name: str, height: int, color: Color | None = None) -> pygame.Surface:
    """Square icon `name` ('skull', 'medal', 'lock') of side `height` px, cached per (name, height, color)."""
    draw, default = _DRAWERS[name]
    color = tuple(color) if color is not None else default
    height = max(int(height), 1)
    key = (name, height, color)
    img = _cache.get(key)
    if img is None:
        big = draw(color)
        img = _cache[key] = big if height == BASE else pygame.transform.smoothscale(big, (height, height))
    return img


def skull(height: int, color: Color | None = None) -> pygame.Surface:
    """The red skull used in the HUD kill counter."""
    return get_icon("skull", height, color)


def medal(height: int, color: Color | None = None) -> pygame.Surface:
    """Gold medal for unlocked achievements."""
    return get_icon("medal", height, color)


def padlock(height: int, color: Color | None = None) -> pygame.Surface:
    """Grey padlock for locked achievements."""
    return get_icon("lock", height, color)
