"""F(x, y, t) = 0 -> screen-space curve points, hit mask and rendering (ARCHITECTURE section 3).

build_curve is numpy-only (headless); pygame is imported lazily by render_curve.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

import numpy as np

from ascensus import config, view

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
    """Sign-change edges on a grid, bisected, with the pole filter; then the two crossings of every grid
    cell are joined (marching squares) and filled in about every CURVE_FILL_SPACING px, so the curve is a
    continuous line at any grid step. Returns screen (N, 2)."""
    W, H = size
    sx = np.arange(0, W + step, step)
    sy = np.arange(0, H + step, step)
    xs = (sx - W / 2 + 0.5) / unit
    ys = -(sy - H / 2 + 0.5) / unit
    X, Y = np.meshgrid(xs, ys)
    ny, nx = X.shape
    found: list[np.ndarray] = []
    # crossing per grid edge / node in math units (NaN = none); used to join each cell's crossings
    h_root = np.full((ny, nx - 1, 2), np.nan, dtype=np.float32)   # horizontal edges (between columns)
    v_root = np.full((ny - 1, nx, 2), np.nan, dtype=np.float32)   # vertical edges (between rows)
    node = None                                                    # exact-zero grid nodes, when any
    with np.errstate(all="ignore"):
        V = np.broadcast_to(np.asarray(f(X, Y, t), dtype=float), X.shape)
        zero = V == 0                                   # exact-zero nodes are root points themselves
        if zero.any():
            node = np.full((ny, nx, 2), np.nan, dtype=np.float32)
            node[zero] = np.column_stack((X[zero], Y[zero]))
            found.append(np.column_stack((X[zero], Y[zero])))
        edges = [
            (h_root, X[:, :-1], Y[:, :-1], X[:, 1:], Y[:, 1:], V[:, :-1], V[:, 1:]),
            (v_root, X[:-1], Y[:-1], X[1:], Y[1:], V[:-1], V[1:]),
        ]
        for store, ax, ay, bx, by, va, vb in edges:
            m = (np.isfinite(va) & np.isfinite(vb) & (np.sign(va) != np.sign(vb))
                 & (va != 0) & (vb != 0))               # zero endpoints are handled above
            ax, ay, bx, by, va, vb = (a[m] for a in (ax, ay, bx, by, va, vb))
            if ax.size == 0:
                continue
            f0 = np.minimum(np.abs(va), np.abs(vb))
            g0 = np.maximum(np.abs(va), np.abs(vb))
            for _ in range(config.BISECT_ITERS):
                mx, my = (ax + bx) / 2, (ay + by) / 2
                vm = np.asarray(f(mx, my, t), dtype=float)
                left = np.sign(vm) == np.sign(va)
                ax, ay, va = np.where(left, mx, ax), np.where(left, my, ay), np.where(left, vm, va)
                bx, by, vb = np.where(left, bx, mx), np.where(left, by, my), np.where(left, vb, vm)
            fr = np.minimum(np.abs(va), np.abs(vb))
            gr = np.maximum(np.abs(va), np.abs(vb))
            # POLE FILTER: around a real root the bracket values shrink, around a pole they grow. Compare
            # both the smaller and the larger end: a root right next to a grid node has a tiny smaller end,
            # but its larger end still shrinks, while a pole's larger end never does.
            ok = np.isfinite(fr) & ((fr < config.POLE_FILTER * f0) | (gr < config.POLE_FILTER * g0))
            roots = np.column_stack(((ax + bx) / 2, (ay + by) / 2))
            idx = np.flatnonzero(m)[ok]
            store.reshape(-1, 2)[idx] = roots[ok]
            found.append(roots[ok])
    if not found:
        return np.zeros((0, 2), dtype=np.float32)
    pts = np.vstack(found + [_join_cells(h_root, v_root, node, unit)])
    return np.column_stack((pts[:, 0] * unit + W / 2 - 0.5, H / 2 - 0.5 - pts[:, 1] * unit)).astype(np.float32)


def _join_cells(h_root: np.ndarray, v_root: np.ndarray, node: np.ndarray | None, unit: float) -> np.ndarray:
    """Points filling the segment between the two crossings of every cell that has exactly two (its four
    edges and four corners); cells with 1, 3 or 4 crossings (poles, saddles) keep only their crossings."""
    h, v = ~np.isnan(h_root[..., 0]), ~np.isnan(v_root[..., 0])
    count = h[:-1].astype(np.int8) + h[1:] + v[:, :-1] + v[:, 1:]
    if node is not None:
        z = ~np.isnan(node[..., 0])
        count += z[:-1, :-1].astype(np.int8) + z[:-1, 1:] + z[1:, :-1] + z[1:, 1:]   # int: bool + bool is OR
    ci, cj = np.nonzero(count == 2)                      # only the cells a curve passes through once
    if ci.size == 0:
        return np.zeros((0, 2))
    parts = [h_root[ci, cj], h_root[ci + 1, cj], v_root[ci, cj], v_root[ci, cj + 1]]
    if node is not None:
        parts += [node[ci, cj], node[ci, cj + 1], node[ci + 1, cj], node[ci + 1, cj + 1]]
    c = np.stack(parts, axis=1)                          # (n, 4 or 8, 2)
    ok = ~np.isnan(c[..., 0])
    rows = np.arange(len(c))
    first = ok.argmax(axis=1)
    ok[rows, first] = False
    a, b = c[rows, first].astype(np.float64), c[rows, ok.argmax(axis=1)].astype(np.float64)
    n_fill = np.maximum(np.ceil(np.hypot(*(b - a).T) * unit / config.CURVE_FILL_SPACING), 1).astype(int)
    out = [a + (b - a) * (k / n_fill)[:, None] for k in range(1, int(n_fill.max(initial=1)))]
    out = [o[k < n_fill] for k, o in enumerate(out, start=1)]
    return np.vstack(out) if out else np.zeros((0, 2))


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


_PAD = 8                                        # transparent margin around the alpha buffer (px)
_kernels: dict[tuple, list[tuple[int, int, int]]] = {}


def relative_luminance(color: tuple[int, int, int]) -> float:
    """WCAG relative luminance of an sRGB colour: 0 (black) to 1 (white)."""
    lin = [((c / 255 + 0.055) / 1.055) ** 2.4 if c / 255 > 0.04045 else c / 255 / 12.92 for c in color[:3]]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def stamp_kernel(full_r: float, end_r: float, peak: int, power: float) -> list[tuple[int, int, int]]:
    """Radial stamp as (dx, dy, value) offsets sorted by ascending value, zero entries left out.

    value = peak for r <= full_r, then falls as (1 - (r - full_r) / (end_r - full_r)) ** power to 0 at end_r.
    Cached by its arguments (the config can change at runtime).
    """
    key = (full_r, end_r, peak, power)
    if key not in _kernels:
        n = int(math.ceil(end_r)) - 1
        out = []
        for dx in range(-n, n + 1):
            for dy in range(-n, n + 1):
                r = math.hypot(dx, dy)
                k = 1.0 if r <= full_r else max(0.0, 1.0 - (r - full_r) / (end_r - full_r)) ** power
                v = int(round(peak * k))
                if v > 0:
                    out.append((dx, dy, v))
        _kernels[key] = sorted(out, key=lambda o: o[2])
    return _kernels[key]


def _stamp(points: np.ndarray, w: int, h: int, kernel: list[tuple[int, int, int]]) -> np.ndarray:
    """Max-stamp `kernel` at every point; returns uint8 (w + 2*_PAD, h + 2*_PAD), indexed [x, y].

    Writing the offsets in ascending value order with plain assignment equals one np.maximum.at per
    offset (a later, larger value always wins) but is several times faster. The padding removes every
    per-offset bounds check; points more than 4 px outside the window are dropped.
    """
    stride = h + 2 * _PAD
    alpha = np.zeros((w + 2 * _PAD) * stride, dtype=np.uint8)
    ix = np.rint(points[:, 0]).astype(np.int64)
    iy = np.rint(points[:, 1]).astype(np.int64)
    ok = (ix >= -4) & (ix < w + 4) & (iy >= -4) & (iy < h + 4)
    base = (ix[ok] + _PAD) * stride + (iy[ok] + _PAD)
    for dx, dy, v in kernel:
        alpha[base + (dx * stride + dy)] = v
    return alpha.reshape(w + 2 * _PAD, stride)


def render_curve(points: np.ndarray, color: tuple[int, int, int],
                 size: tuple[int, int] | None = None):
    """Smooth neon line: a soft radial kernel stamped at every point (see config CURVE_KERNEL_*).

    Colours darker than DARK_LUMINANCE also get a light halo so black stays visible.
    Use surf.set_alpha(a) when drawing.
    """
    import pygame

    w, h = size if size is not None else (view.W, view.H)
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    surf.fill(color)
    if len(points) == 0:
        surf.fill((*color[:3], 0))
        return surf
    k = stamp_kernel(config.CURVE_KERNEL_FULL_R, config.CURVE_KERNEL_END_R, 255, config.CURVE_KERNEL_POWER)
    core = _stamp(points, w, h, k)[_PAD:_PAD + w, _PAD:_PAD + h]
    alpha, halo = core, None
    if relative_luminance(color) < config.DARK_LUMINANCE:
        k = stamp_kernel(config.HALO_FULL_R, config.HALO_END_R, config.HALO_ALPHA, config.CURVE_KERNEL_POWER)
        halo = _stamp(points, w, h, k)[_PAD:_PAD + w, _PAD:_PAD + h]
        alpha = np.maximum(core, halo)
    buf = pygame.surfarray.pixels_alpha(surf)            # indexed [x, y]
    buf[:] = alpha
    del buf
    if halo is not None:                                 # light fringe: blend the colour toward the halo colour
        m = (halo > 0) & (core < 255)
        t = (core[m].astype(np.float32) / 255)[:, None]
        rgb = np.array(color[:3], np.float32) * t + np.array(config.HALO_COLOR, np.float32) * (1 - t)
        pix = pygame.surfarray.pixels3d(surf)
        pix[m] = rgb.astype(np.uint8)
        del pix
    return surf
