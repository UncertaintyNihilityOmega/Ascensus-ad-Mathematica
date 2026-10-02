"""P18: Kenney PNG icons are present, CC0-licensed, tinted, cached; code-drawn ones work; draw_icon uses them."""
import os
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402
import pytest  # noqa: E402

from ascensus.ui import icons, widgets  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module", autouse=True)
def _pg():
    pygame.init()
    pygame.display.set_mode((64, 64))
    yield
    pygame.quit()


def test_every_icon_name_has_a_png_except_play():
    missing = [n for n in icons.ICON_NAMES if n != "play" and not icons.has_png(n)]
    assert not missing, missing
    assert not icons.has_png("play")                     # drawn in code
    assert (ROOT / "ascensus" / "assets" / "icons" / "License.txt").read_text(encoding="utf-8").count("CC0") >= 2


def test_no_stray_files_in_icons_dir():
    names = {p.name for p in (ROOT / "ascensus" / "assets" / "icons").iterdir()}
    assert names == {f"{n}.png" for n in icons.ICON_NAMES if n != "play"} | {"License.txt"}


@pytest.mark.parametrize("name", icons.ICON_NAMES)
@pytest.mark.parametrize("size", [12, 16, 32, 96])
def test_icon_size_and_content(name, size):
    img = icons.icon(name, size, (255, 255, 255))
    assert img.get_size() == (size, size)
    assert pygame.mask.from_surface(img, 10).count() >= size * size * 0.08


def test_tint_multiplies_white_png():
    img = icons.icon("trash", 48, (255, 0, 0))
    solid = [img.get_at((x, y)) for x in range(48) for y in range(48) if img.get_at((x, y)).a >= 240]
    assert solid and all(c.g == 0 and c.b == 0 and c.r >= 250 for c in solid)       # smoothscale may lose 2 levels
    half = icons.icon("trash", 48, (100, 150, 200, 128))
    c = next(half.get_at((x, y)) for x in range(48) for y in range(48) if half.get_at((x, y)).a > 60)
    assert max(abs(a - b) for a, b in zip((c.r, c.g, c.b), (100, 150, 200))) <= 3 and c.a <= 128


def test_icon_cache_key_is_name_size_color():
    a = icons.icon("gear", 24, (10, 20, 30))
    assert icons.icon("gear", 24, (10, 20, 30)) is a
    assert icons.icon("gear", 24, [10, 20, 30]) is a             # list and tuple colours share an entry
    assert icons.icon("gear", 25, (10, 20, 30)) is not a
    assert icons.icon("gear", 24, (10, 20, 31)) is not a


def test_source_png_is_not_modified_by_tinting():
    icons.icon("home", 30, (255, 0, 0))
    src = icons._white["home"]
    assert src.get_at(src.get_rect().center)[:3] == (255, 255, 255)


def test_aliases_and_unknown_name():
    assert icons.icon("lock", 20) is icons.icon("padlock", 20)
    assert icons.icon("edit", 20) is icons.icon("pencil", 20)
    with pytest.raises(KeyError):
        icons.icon("nope", 20)


def test_play_is_drawn_in_code_pointing_right():
    img = icons.icon("play", 48)
    assert img.get_at((14, 24)).a > 0 and img.get_at((44, 5)).a == 0     # triangle: wide left, narrow right


def test_missing_png_falls_back_to_a_drawing(monkeypatch, tmp_path):
    monkeypatch.setattr(icons, "ICON_DIR", tmp_path)
    monkeypatch.setattr(icons, "_white", {})
    monkeypatch.setattr(icons, "_cache", {})
    for name in icons.ICON_NAMES:
        img = icons.icon(name, 24)
        assert pygame.mask.from_surface(img, 10).count() > 20, name


def test_legacy_helpers_default_colors():
    for fn, col in ((icons.skull, icons.SKULL_COLOR), (icons.medal, icons.MEDAL_COLOR),
                    (icons.padlock, icons.LOCK_COLOR)):
        img = fn(40)
        assert img.get_size() == (40, 40) and fn(40) is img
        c = next(img.get_at((x, y)) for x in range(40) for y in range(40) if img.get_at((x, y)).a >= 240)
        assert max(abs(a - b) for a, b in zip(tuple(c)[:3], col)) <= 4
    assert icons.get_icon("lock", 20) is icons.padlock(20)


def test_draw_icon_blits_inside_its_rect():
    surf = pygame.Surface((60, 60))
    for kind in icons.ICON_NAMES:
        surf.fill((0, 0, 0))
        widgets.draw_icon(surf, kind, pygame.Rect(10, 10, 40, 40), (255, 255, 255))
        lit = pygame.mask.from_threshold(surf, (0, 0, 0), (1, 1, 1, 255))      # pixels still black
        lit.invert()
        box = lit.get_bounding_rects()
        assert box and pygame.Rect(10, 10, 40, 40).contains(box[0].unionall(box)), kind


def test_icon_button_enabled_and_disabled_draw():
    surf = pygame.Surface((60, 60))
    b = widgets.IconButton(pygame.Rect(5, 5, 24, 24), "pause")
    b.draw(surf)
    b.enabled = False
    b.draw(surf)
