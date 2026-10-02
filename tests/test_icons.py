"""Icons render headlessly, at the requested size, with transparency, and are cached."""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402
import pytest  # noqa: E402

from ascensus.ui import icons  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _pg():
    pygame.init()
    pygame.display.set_mode((64, 64))
    yield
    pygame.quit()


@pytest.mark.parametrize("fn", [icons.skull, icons.medal, icons.padlock])
@pytest.mark.parametrize("h", [16, 24, 96, 200])
def test_size_and_content(fn, h):
    img = fn(h)
    assert img.get_size() == (h, h)
    assert pygame.mask.from_surface(img, 10).count() > h * h * 0.1     # something is drawn
    assert img.get_at((0, 0)).a == 0                                   # transparent corner


def test_cached_and_colored():
    assert icons.skull(20) is icons.skull(20)
    assert icons.skull(20) is not icons.skull(21)
    assert icons.skull(20, (0, 255, 0)) is not icons.skull(20)


def test_skull_fallback_drawer_has_cutout_features():
    """The in-code skull (used only when assets/icons/skull.png is missing) keeps its punched-out eyes."""
    img = icons._draw_skull()
    assert img.get_at((48, 30)).a > 0 and img.get_at((33, 34)).a == 0   # eye bar punched out


def test_skull_png_is_used_when_present():
    assert icons.has_png("skull") and icons.skull(96).get_at((0, 0)).a == 0
