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
