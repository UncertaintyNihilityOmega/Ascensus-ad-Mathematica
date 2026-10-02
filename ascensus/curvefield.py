"""F(x, y, t) = 0 -> screen-space curve points, hit mask and rendering (ARCHITECTURE section 3).

build_curve is numpy-only (headless); pygame is imported lazily by render_curve.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

import numpy as np

from . import config, view

CurveFunc = Callable[[np.ndarray, np.ndarray, float], np.ndarray]


@dataclass
class CurveData:
    points: np.ndarray      # (N, 2) float32 screen px (sx, sy)
    hit_mask: np.ndarray    # bool (ceil(H/HIT_CELL), ceil(W/HIT_CELL)), dilated
    length_units: float     # occupied (undilated) coarse cells * HIT_CELL / UNIT_PX


def _dilate(mask: np.ndarray, r: int) -> np.ndarray:
    """Square dilation by r cells (separable shifted-OR, no scipy). Indexed [row, col]."""
    out = mask.copy()
    if r <= 0:
        return out
    h, w = mask.shape
    for axis, n in ((0, h), (1, w)):
        src = out
        out = src.copy()
        for d in range(1, r + 1):
            if d >= n:
                break
            for dst_sl, src_sl in ((slice(d, n), slice(0, n - d)), (slice(0, n - d), slice(d, n))):
                a, b = [slice(None), slice(None)], [slice(None), slice(None)]
                a[axis], b[axis] = dst_sl, src_sl
                out[tuple(a)] |= src[tuple(b)]
    return out


def _find_roots(f: CurveFunc, t: float, step: int, size: tuple[int, int], unit: float) -> np.ndarray:
    """Sign-change edges on a grid, bisected, with the pole filter. Returns screen (N, 2)."""
    W, H = size
    sx = np.arange(0, W + step, step)
    sy = np.arange(0, H + step, step)
    xs = (sx - W / 2 + 0.5) / unit
    ys = -(sy - H / 2 + 0.5) / unit
    X, Y = np.meshgrid(xs, ys)
    found: list[np.ndarray] = []
    with np.errstate(all="ignore"):
        V = np.broadcast_to(np.asarray(f(X, Y, t), dtype=float), X.shape)
        zero = V == 0                                   # exact-zero nodes are root points themselves
        if zero.any():
            found.append(np.column_stack((X[zero] * unit + W / 2 - 0.5, H / 2 - 0.5 - Y[zero] * unit)))
        edges = [
            (X[:, :-1], Y[:, :-1], X[:, 1:], Y[:, 1:], V[:, :-1], V[:, 1:]),
            (X[:-1], Y[:-1], X[1:], Y[1:], V[:-1], V[1:]),
        ]
        for ax, ay, bx, by, va, vb in edges:
            m = (np.isfinite(va) & np.isfinite(vb) & (np.sign(va) != np.sign(vb))
                 & (va != 0) & (vb != 0))               # zero endpoints are handled above
            ax, ay, bx, by, va, vb = (a[m] for a in (ax, ay, bx, by, va, vb))
            if ax.size == 0:
                continue
            f0 = np.minimum(np.abs(va), np.abs(vb))
            for _ in range(config.BISECT_ITERS):
                mx, my = (ax + bx) / 2, (ay + by) / 2
                vm = np.asarray(f(mx, my, t), dtype=float)
                left = np.sign(vm) == np.sign(va)
                ax, ay, va = np.where(left, mx, ax), np.where(left, my, ay), np.where(left, vm, va)
                bx, by, vb = np.where(left, bx, mx), np.where(left, by, my), np.where(left, vb, vm)
            fr = np.minimum(np.abs(va), np.abs(vb))
            ok = np.isfinite(fr) & (fr < config.POLE_FILTER * f0)  # real roots shrink, poles grow
            rx, ry = ((ax + bx) / 2)[ok], ((ay + by) / 2)[ok]
            found.append(np.column_stack((rx * unit + W / 2 - 0.5, H / 2 - 0.5 - ry * unit)))
    if not found:
        return np.zeros((0, 2), dtype=np.float32)
    return np.vstack(found).astype(np.float32)


def build_curve(f: CurveFunc, t: float = 0.0, step: int | None = None,
                size: tuple[int, int] | None = None, unit: float | None = None,
                vars: dict[str, float] | None = None) -> CurveData:
    """Evaluate the curve F=0 inside the window: points, dilated hit mask, length.

    `size` / `unit` default to the current view (an explicit size is for Library mini graphs).
    `vars` maps variable names to values; when given, f is called as f(x, y, t, vars).
    """
    if vars is not None:
        g = f
        f = lambda x, y, t: g(x, y, t, vars)        # noqa: E731
    W, H = size if size is not None else (view.W, view.H)
    unit = config.UNIT_PX if unit is None else unit
    step = config.GRID_STEP if step is None else step
    points = _find_roots(f, t, step, (W, H), unit)
    cell = config.HIT_CELL
    occ = np.zeros((math.ceil(H / cell), math.ceil(W / cell)), dtype=bool)
    if len(points):
        ix = points[:, 0].astype(np.int32)
        iy = points[:, 1].astype(np.int32)
        inside = (ix >= 0) & (ix < W) & (iy >= 0) & (iy < H)
        occ[iy[inside] // cell, ix[inside] // cell] = True
    length = float(occ.sum()) * cell / unit
    return CurveData(points, _dilate(occ, config.HIT_DILATE), length)


def render_curve(points: np.ndarray, color: tuple[int, int, int],
                 size: tuple[int, int] | None = None):
    """Neon line: 3 px core + soft glow as per-pixel alpha. Use surf.set_alpha(a) when drawing."""
    import pygame

    w, h = size if size is not None else (view.W, view.H)
    alpha = np.zeros((w, h), dtype=np.uint8)             # indexed [x, y] like surfarray
    if len(points):
        ix = np.rint(points[:, 0]).astype(np.int32)
        iy = np.rint(points[:, 1]).astype(np.int32)

        def stamp(r: int, value: int) -> None:
            """Square dilation done on the (few) points instead of the whole screen."""
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    x, y = ix + dx, iy + dy
                    ok = (x >= 0) & (x < w) & (y >= 0) & (y < h)
                    alpha[x[ok], y[ok]] = value

        stamp(config.CORE_DILATE + config.GLOW_DILATE, config.GLOW_ALPHA)
        stamp(config.CORE_DILATE, 255)
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    surf.fill(color)
    buf = pygame.surfarray.pixels_alpha(surf)            # indexed [x, y]
    buf[:] = alpha
    del buf
    return surf
