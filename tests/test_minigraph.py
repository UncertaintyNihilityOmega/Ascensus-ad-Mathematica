"""Library mini graphs: right size, curve pixels drawn, cached, bad text tolerated."""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import numpy as np  # noqa: E402
import pygame  # noqa: E402
import pytest  # noqa: E402

from ascensus import config  # noqa: E402
from ascensus.ui.minigraph import render_minigraph  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _pg():
    pygame.init()
    pygame.display.set_mode((64, 64))
    yield
    pygame.quit()


def _curve_pixels(surf, color):
    arr = pygame.surfarray.pixels3d(surf)
    n = int((np.all(arr == color, axis=2)).sum())
    del arr
    return n


def test_size_cache_and_curve_pixels():
    a = render_minigraph("y = sin(x)", (200, 120), 20)
    assert a.get_size() == (200, 120)
    assert render_minigraph("y = sin(x)", (200, 120), 20) is a                  # cached
    assert render_minigraph("y = sin(x)", (160, 90), 20).get_size() == (160, 90)
    assert _curve_pixels(a, config.ACCENT_COLOR) > 200
    red = render_minigraph("y = sin(x)", color=(255, 0, 0))
    assert _curve_pixels(red, (255, 0, 0)) > 200


def test_bad_text_gives_axes_only():
    s = render_minigraph("sin x ???", (200, 120), 20)
    assert s.get_size() == (200, 120) and _curve_pixels(s, config.ACCENT_COLOR) == 0
    assert tuple(s.get_at((100, 5)))[:3] != config.BG_COLOR                    # the y axis is drawn
