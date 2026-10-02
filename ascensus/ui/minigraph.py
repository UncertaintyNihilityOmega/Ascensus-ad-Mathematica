"""Small cached graph thumbnails for the Library (equation text -> pygame Surface)."""
from __future__ import annotations

import pygame

from ascensus import config
from ascensus.core import curvefield
from ascensus.core.mathparse import EquationError, parse_equation

MINIGRAPH_CACHE_MAX = 200
_cache: dict[tuple, pygame.Surface] = {}


def render_minigraph(equation_text: str, size: tuple[int, int] = (200, 120), unit: float = 20,
                     color: tuple[int, int, int] = config.ACCENT_COLOR) -> pygame.Surface:
    """Surface of `size` with faint axes and the curve of `equation_text` (x/y in units of `unit` px).

    Variables take config.VAR_DEFAULT and t is 0. Results are cached by (text, size, unit, color), so
    the returned surface is shared: blit it, never draw on it. An equation that does not parse
    gives the axes only.
    """
    key = (equation_text, tuple(size), unit, tuple(color))
    surf = _cache.get(key)
    if surf is None:
        if len(_cache) >= MINIGRAPH_CACHE_MAX:
            _cache.clear()
        surf = _cache[key] = _build(equation_text, tuple(size), unit, color)
    return surf


def _build(text: str, size: tuple[int, int], unit: float, color: tuple[int, int, int]) -> pygame.Surface:
    w, h = size
    surf = pygame.Surface(size, pygame.SRCALPHA)
    surf.fill((*config.BG_COLOR, 255))
    cx, cy = w // 2, h // 2
    axis = (*config.GRID_COLOR, config.AXES_ALPHA)
    pygame.draw.line(surf, axis, (0, cy), (w, cy))
    pygame.draw.line(surf, axis, (cx, 0), (cx, h))
    try:
        parsed = parse_equation(text)
    except EquationError:
        return surf
    curve = curvefield.build_curve(parsed.func, 0.0, size=size, unit=unit)
    surf.blit(curvefield.render_curve(curve.points, color, size), (0, 0))
    return surf
