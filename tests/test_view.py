"""view.py mapping and build_curve size/unit arguments."""
import numpy as np

from ascensus import config, view
from ascensus.core.curvefield import build_curve
from ascensus.core.mathparse import parse_equation


def test_set_size_and_mapping_roundtrip():
    w, h = view.W, view.H
    try:
        view.set_size(1920, 1080)
        assert view.center() == (960, 540)
        sx, sy = view.math_to_screen(2.0, 1.0)
        assert (sx, sy) == (960 + 2 * config.UNIT_PX, 540 - config.UNIT_PX)
        assert view.screen_to_math(sx, sy) == (2.0, 1.0)
    finally:
        view.set_size(w, h)


def test_build_curve_follows_explicit_size_and_unit():
    f = parse_equation("x = 0").func
    c = build_curve(f, size=(400, 200), unit=20.0)
    assert c.hit_mask.shape == (-(-200 // config.HIT_CELL), -(-400 // config.HIT_CELL))
    assert np.allclose(c.points[:, 0], 199.5, atol=1.0)
    assert abs(c.length_units - 200 / 20.0) < 1.0


def test_build_curve_defaults_to_view_size():
    w, h = view.W, view.H
    try:
        view.set_size(800, 600)
        c = build_curve(parse_equation("y = x").func)
        assert c.hit_mask.shape == (-(-600 // config.HIT_CELL), -(-800 // config.HIT_CELL))
        assert c.points[:, 0].max() <= 800 and c.points[:, 1].max() <= 600
    finally:
        view.set_size(w, h)
