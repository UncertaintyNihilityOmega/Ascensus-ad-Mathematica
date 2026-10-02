"""Mutable viewport: window size and the math <-> screen mapping. Read `view.W` / `view.H` at call time."""
from __future__ import annotations

from ascensus import config

W: int = 1280
H: int = 720


def set_size(w: int, h: int) -> None:
    """Record a new window size (call before the scenes' on_resize)."""
    global W, H
    W, H = max(int(w), 1), max(int(h), 1)


def center() -> tuple[int, int]:
    """Screen position of the math origin / the player."""
    return W // 2, H // 2


def math_to_screen(x: float, y: float) -> tuple[float, float]:
    """Math coordinates relative to the player -> screen pixels (y up in math space)."""
    return W / 2 + x * config.UNIT_PX, H / 2 - y * config.UNIT_PX


def screen_to_math(sx: float, sy: float) -> tuple[float, float]:
    return (sx - W / 2) / config.UNIT_PX, (H / 2 - sy) / config.UNIT_PX
