"""Curve engine tests (headless): points, pole filter, hit mask, length, render."""
import os

import numpy as np

from ascensus import config, view
from ascensus.config import UNIT_PX
from ascensus.curvefield import build_curve, render_curve
from ascensus.mathparse import parse_equation

W, H = view.W, view.H


def curve(text, t=0.0, step=config.GRID_STEP):
    return build_curve(parse_equation(text).func, t, step)


def math_pts(c):
    return (c.points[:, 0] - W / 2) / UNIT_PX, -(c.points[:, 1] - H / 2) / UNIT_PX


def test_unit_circle_points_on_circle():
    c = curve("1 = x^2 + y^2")
    x, y = math_pts(c)
    assert 100 < len(c.points) < 400
    assert np.allclose(np.hypot(x, y), 1.0, atol=0.06)
    assert 5.0 < c.length_units < 9.0


def test_vertical_line_length():
    c = curve("x = 2")
    x, _ = math_pts(c)
    assert np.allclose(x, 2.0, atol=0.05)
    assert abs(c.length_units - 14.4) < 0.5


def test_diagonal_line_is_drawn():
    """y = x hits exact-zero grid nodes; those used to be rejected by the pole filter."""
    c = curve("y = x")
    x, y = math_pts(c)
    assert len(c.points) >= 200                      # one point per exact-zero node
    assert np.allclose(x, y, atol=0.05)
    gaps = np.diff(np.sort(c.points[:, 1]))          # no hole bigger than a glow stamp
    assert gaps.max() <= 2 * (config.CORE_DILATE + config.GLOW_DILATE)
    assert c.length_units > 10


def test_anti_diagonal_line_is_drawn():
    c = curve("y = -x")
    x, y = math_pts(c)
    assert len(c.points) >= 400
    assert np.allclose(x, -y, atol=0.05)


def test_line_just_below_axis_is_visible():
    c = curve("y = -0.01")
    _, y = math_pts(c)
    assert len(c.points) >= 400
    assert np.allclose(y, -0.01, atol=0.05)


def test_exact_zero_node_is_a_root_point():
    c = curve("y = x")
    assert c.hit_mask.any()


def test_tan_has_no_asymptote_points():
    c = curve("y = tan(x)")
    x, y = math_pts(c)
    assert len(c.points) > 1000
    base = np.arctan(y)                              # x error is small even where tan is steep
    off = x - base - np.round((x - base) / np.pi) * np.pi
    assert np.abs(off).max() < 0.03
    bad = (np.abs(np.cos(x)) < 0.02) & (np.abs(y) < 5)
    assert int(bad.sum()) == 0


def test_reciprocal_pole_filtered():
    c = curve("y = 1/x")
    x, y = math_pts(c)
    assert len(c.points) > 100
    assert int(((np.abs(x) < 0.05) & (np.abs(y) < 5)).sum()) == 0


def test_tan_monster_is_long():
    c = curve("tan(sqrt(x^2 + y^2)) = y / x")
    assert len(c.points) > 1500
    assert c.length_units > 60


def test_offscreen_curve_is_empty():
    c = curve("x = 100")
    assert len(c.points) == 0
    assert c.length_units == 0.0
    assert not c.hit_mask.any()
    assert c.points.shape == (0, 2)


def test_t_equation_changes_with_t():
    f = parse_equation("y = 2sin(x + t)").func
    a = build_curve(f, 0.0, config.GRID_STEP_T)
    b = build_curve(f, 1.5, config.GRID_STEP_T)
    assert len(a.points) > 0 and not np.array_equal(a.hit_mask, b.hit_mask)


def test_hit_mask_shape_and_dilation():
    c = curve("x = 0")
    cell = config.HIT_CELL
    assert c.hit_mask.shape == (-(-H // cell), -(-W // cell))
    col = int((W / 2 - 0.5) // cell)
    d = config.HIT_DILATE
    assert c.hit_mask[40, col] and c.hit_mask[40, col + d] and c.hit_mask[40, col - d]
    assert not c.hit_mask[40, col + d + 2]


def test_points_inside_window_roughly():
    c = curve("1 = x^2 + y^2")
    assert (c.points[:, 0] >= -2).all() and (c.points[:, 0] <= W + 2).all()


def test_render_curve_alpha_layout():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    c = curve("x = 0")
    surf = render_curve(c.points, (0, 255, 255), (W, H))
    assert surf.get_size() == (W, H)
    alpha = pygame.surfarray.array_alpha(surf)       # [x, y]
    cx = int(W / 2 - 0.5)
    assert alpha[cx, 300] == 255                     # core
    assert 0 < alpha[cx + 3, 300] < 255              # glow
    assert alpha[cx + 20, 300] == 0
    assert alpha[10, 300] == 0
    assert tuple(surf.get_at((cx, 300)))[:3] == (0, 255, 255)


def test_render_empty_points():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    surf = render_curve(np.zeros((0, 2), np.float32), (255, 0, 0), (100, 50))
    assert surf.get_size() == (100, 50)


# -- P19: smooth kernel and dark halo ---------------------------------------------------------------------
def _alpha(points, color, size):
    import pygame
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    return pygame.surfarray.array_alpha(render_curve(points, color, size))


def test_kernel_shape_full_core_and_zero_at_end_radius():
    from ascensus.curvefield import stamp_kernel
    k = stamp_kernel(1.5, 4.0, 255, 2.0)
    assert len({(dx, dy) for dx, dy, _ in k}) == len(k) and max(max(abs(dx), abs(dy)) for dx, dy, _ in k) == 3
    vals = {(dx, dy): v for dx, dy, v in k}
    assert all(vals[o] == 255 for o in vals if (o[0] ** 2 + o[1] ** 2) ** 0.5 <= 1.5)
    assert (3, 3) not in vals and (4, 0) not in vals                      # r >= 4 is zero
    assert [v for _, _, v in k] == sorted(v for _, _, v in k)             # ascending, so assignment == maximum
    assert vals[(2, 0)] > vals[(3, 0)] > 0


def test_stamp_equals_np_maximum_at():
    from ascensus.curvefield import _PAD, _stamp, stamp_kernel
    rng = np.random.default_rng(0)
    pts = rng.uniform(0, 60, (200, 2)).astype(np.float32)
    k = stamp_kernel(1.5, 4.0, 255, 2.0)
    got = _stamp(pts, 60, 60, k)[_PAD:_PAD + 60, _PAD:_PAD + 60]
    ref = np.zeros((60, 60), np.uint8)
    ix, iy = np.rint(pts[:, 0]).astype(int), np.rint(pts[:, 1]).astype(int)
    for dx, dy, v in k:
        x, y = ix + dx, iy + dy
        ok = (x >= 0) & (x < 60) & (y >= 0) & (y < 60)
        np.maximum.at(ref, (x[ok], y[ok]), v)
    assert np.array_equal(got, ref)


def test_diagonal_line_has_no_beading():
    c = curve("y = x")
    alpha = _alpha(c.points, (0, 255, 255), (W, H))
    off = (W + H) / 2 - 1                         # screen y = off - x for y = x
    xs = np.arange(W // 2 - 150, W // 2 + 150)
    vals = np.array([alpha[x, int(round(off - x))] for x in xs], dtype=float)
    assert vals.min() >= 230 and vals.std() < 8, (vals.min(), vals.std())


def test_horizontal_and_steep_lines_have_no_beading():
    for text in ("y = 0", "y = 0.3 x", "y = 3 x"):
        c = curve(text)
        alpha = _alpha(c.points, (0, 255, 255), (W, H))
        ys, xs = np.nonzero(alpha.T == 255)
        assert len(xs) > 200
        # every sampled root point sits on a full-alpha pixel; the neighbours along the line are covered too
        px = np.rint(c.points).astype(int)
        px = px[(px[:, 0] >= 0) & (px[:, 0] < W) & (px[:, 1] >= 0) & (px[:, 1] < H)]
        assert (alpha[px[:, 0], px[:, 1]] == 255).all(), text


def test_relative_luminance_values():
    from ascensus.curvefield import relative_luminance
    assert relative_luminance((0, 0, 0)) == 0 and abs(relative_luminance((255, 255, 255)) - 1) < 1e-6
    assert relative_luminance((70, 74, 88)) < config.DARK_LUMINANCE        # Graphite gets a halo
    assert relative_luminance((128, 134, 150)) > config.DARK_LUMINANCE     # Gray does not


def test_dark_curve_gets_light_halo_and_bright_curve_does_not():
    import pygame
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    c = curve("x = 0")
    cx = int(W / 2 - 0.5)
    black = render_curve(c.points, (0, 0, 0), (W, H))
    assert tuple(black.get_at((cx, 300)))[:3] == (0, 0, 0) and black.get_at((cx, 300)).a == 255   # core stays black
    halo = black.get_at((cx + 4, 300))
    assert halo.a > 0 and min(halo[:3]) > 120                              # light fringe right outside the core
    assert black.get_at((cx + 12, 300)).a == 0
    cyan = render_curve(c.points, (0, 255, 255), (W, H))
    assert tuple(cyan.get_at((cx + 3, 300)))[:3] == (0, 255, 255)           # no halo: still the curve colour
    assert black.get_at((cx + 4, 300)).a <= config.HALO_ALPHA
    # halo alpha never dims the core
    a_black = pygame.surfarray.array_alpha(black)
    a_cyan = pygame.surfarray.array_alpha(cyan)
    assert (a_black >= a_cyan).all()


def test_render_points_outside_the_surface_are_safe():
    pts = np.array([[-50, -50], [-2, 10], [1e4, 5], [5, 1e4], [3, 3]], np.float32)
    a = _alpha(pts, (255, 255, 255), (20, 20))
    assert a.shape == (20, 20) and a[3, 3] == 255 and a[0, 10] > 0
