"""P18: the 20-colour palette, the picker grid / tooltip / Custom row, hex and hue parsing, save of custom colours."""
import json
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402
import pytest  # noqa: E402

from ascensus import config, view  # noqa: E402
from ascensus.core.equations import EquationManager  # noqa: E402
from ascensus.ui.colorpicker import CustomRow, hsv_to_rgb, parse_hex, rgb_to_hsv, to_hex  # noqa: E402
from ascensus.ui.inputbox import InputBox  # noqa: E402
from ascensus.ui.sidebar import Sidebar  # noqa: E402


@pytest.fixture(autouse=True)
def _pg():
    pygame.init()
    pygame.display.set_mode((1280, 720))
    view.set_size(1280, 720)
    yield


def down(pos, button=1):
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=button)


def up(pos):
    return pygame.event.Event(pygame.MOUSEBUTTONUP, pos=pos, button=1)


def move(pos):
    return pygame.event.Event(pygame.MOUSEMOTION, pos=pos, rel=(0, 0), buttons=(1, 0, 0))


def key(k):
    return pygame.event.Event(pygame.KEYDOWN, key=k, mod=0, unicode="")


def text(t):
    return pygame.event.Event(pygame.TEXTINPUT, text=t)


def make(tmp_path, n=3):
    m = EquationManager()
    for k in range(n):
        m._append(f"y = x + {k}", build=False)
    return m, Sidebar(m, InputBox())


# --- the palette ---------------------------------------------------------------------------------------
def test_palette_is_the_w4_list_in_row_order():
    pal, names = config.CURVE_PALETTE_20, config.CURVE_PALETTE_NAMES
    assert len(pal) == 20 and len(set(pal)) == 20 and len(names) == 20 and len(set(names)) == 20
    assert names[:5] == ["White", "Silver", "Gray", "Graphite", "Black"]
    assert names[5:10] == ["Red", "Orange", "Yellow", "Lime", "Green"]
    assert names[10:15] == ["Teal", "Cyan", "Sky", "Blue", "Indigo"]
    assert names[15:] == ["Violet", "Purple", "Magenta", "Pink", "Brown"]
    assert pal[0] == (255, 255, 255) and pal[4] == (0, 0, 0) and pal[5] == (255, 59, 48)
    assert pal[12] == (90, 170, 255) and pal[19] == (165, 110, 60) and pal[3] == (70, 74, 88)
    assert all(len(c) == 3 and all(0 <= v <= 255 for v in c) for c in pal)


def test_auto_palette_skips_black_and_graphite():
    auto = config.CURVE_PALETTE_AUTO
    assert len(auto) == 18 and (0, 0, 0) not in auto and (70, 74, 88) not in auto
    assert auto[0] == config.CURVE_PALETTE_20[0] and set(auto) <= set(config.CURVE_PALETTE_20)


# --- picker grid and tooltip ------------------------------------------------------------------------------
def test_picker_grid_is_5x4_with_hover_names(tmp_path):
    m, sb = make(tmp_path)
    sb.open_picker(0)
    cells = [sb._picker_cell(k) for k in range(20)]
    assert len({tuple(c.topleft) for c in cells}) == 20
    assert all(sb.picker_rect.contains(c) for c in cells)
    for k, c in enumerate(cells):
        assert (c.x == cells[0].x) == (k % 5 == 0) and (c.y == cells[0].y) == (k < 5)
        assert sb.picker_tooltip(c.center) == config.CURVE_PALETTE_NAMES[k]
    assert sb.picker_tooltip((0, view.H - 1)) is None
    gap = (cells[0].right + cells[1].left) // 2, cells[0].centery
    assert sb.picker_tooltip(gap) is None
    screen = pygame.display.get_surface()
    sb.draw(screen)
    sb.draw_popups(screen)
    pygame.mouse.set_pos(cells[7].center)
    sb.draw_popups(screen)                                       # with a tooltip showing


def test_picker_has_custom_row_below_the_grid_and_fits_the_window(tmp_path):
    for size in ((800, 600), (1280, 720), (1920, 1080)):
        view.set_size(*size)
        m, sb = make(tmp_path, 8)
        for i in (0, 7):
            sb.open_picker(i)
            assert pygame.Rect(0, 0, *size).contains(sb.picker_rect)
            c = sb.custom
            parts = (c.hue_strip.rect, c.val_strip.rect, c.preview, c.hex.rect)
            assert all(sb.picker_rect.contains(r) for r in parts)
            assert min(r.top for r in parts) > sb._picker_cell(19).bottom
            assert c.hue_strip.rect.bottom <= c.val_strip.rect.top
            sb.close_picker()
    view.set_size(1280, 720)


def test_palette_pick_sets_and_saves_color_and_closes(tmp_path):
    m, sb = make(tmp_path)
    sb.open_picker(1)
    assert sb.handle_event(down(sb._picker_cell(9).center))
    assert m.entries[1].color == config.CURVE_PALETTE_20[9] and sb.picker_idx is None
    assert m.to_data()["equations"][1]["color"] == list(config.CURVE_PALETTE_20[9])


# --- parsing helpers ------------------------------------------------------------------------------------
@pytest.mark.parametrize("txt,col", [("#FF8000", (255, 128, 0)), ("ff8000", (255, 128, 0)), (" #0a0B0c ", (10, 11, 12)),
                                     ("#f80", (255, 136, 0)), ("#000000", (0, 0, 0))])
def test_parse_hex_valid(txt, col):
    assert parse_hex(txt) == col


@pytest.mark.parametrize("txt", ["", "#", "#12345", "#1234567", "#GGGGGG", "12 456", "#ff80", "red"])
def test_parse_hex_invalid(txt):
    assert parse_hex(txt) is None


def test_hex_and_hsv_round_trips():
    assert to_hex((255, 0, 128)) == "#FF0080" and parse_hex(to_hex((1, 2, 3))) == (1, 2, 3)
    assert hsv_to_rgb(0.0, 1, 1) == (255, 0, 0) and hsv_to_rgb(1 / 3, 1, 1) == (0, 255, 0)
    assert hsv_to_rgb(2 / 3, 1, 1) == (0, 0, 255) and hsv_to_rgb(1.0, 1, 1) == (255, 0, 0)
    for col in ((255, 59, 48), (0, 199, 170), (165, 110, 60)):
        assert max(abs(a - b) for a, b in zip(hsv_to_rgb(*rgb_to_hsv(col)), col)) <= 1


# --- the Custom row ---------------------------------------------------------------------------------------
def test_hue_strip_click_and_drag(tmp_path):
    m, sb = make(tmp_path)
    sb.open_picker(0)
    hs = sb.custom.hue_strip.rect
    sb.handle_event(down((hs.left, hs.centery)))                      # far left: red, vivid
    assert m.entries[0].color == (255, 0, 0)
    sb.handle_event(down((hs.left + (hs.w - 1) // 3, hs.centery)))
    r, g, b = m.entries[0].color
    assert g > 240 and r < 20 and b < 20                              # green
    x = hs.left + 2 * (hs.w - 1) // 3
    sb.handle_event(move((x, hs.centery)))                            # drag: preview only
    assert sb.custom.color[2] > 240 and m.entries[0].color[2] < 20
    sb.handle_event(up((x, hs.centery)))
    assert m.entries[0].color[2] > 240 and sb.picker_idx == 0         # applied on release, popup stays open
    sb.handle_event(move((hs.right + 80, hs.centery)))                # not dragging: ignored
    assert sb.picker_idx == 0


def test_brightness_strip_dims_the_color(tmp_path):
    m, sb = make(tmp_path)
    sb.open_picker(0)
    hs, vs = sb.custom.hue_strip.rect, sb.custom.val_strip.rect
    sb.handle_event(down((hs.left, hs.centery)))                      # red
    sb.handle_event(down((vs.left + (vs.w - 1) // 2, vs.centery)))
    r, g, b = m.entries[0].color
    assert 120 <= r <= 135 and g == 0 and b == 0
    sb.handle_event(down((vs.left, vs.centery)))
    assert m.entries[0].color == (0, 0, 0)


def test_hex_box_enter_applies_and_saves(tmp_path):
    m, sb = make(tmp_path)
    sb.open_picker(2)
    hx = sb.custom.hex
    sb.handle_event(down(hx.rect.center))
    assert hx.focused
    sb.handle_event(text("#12ab9f"))
    assert hx.text == "#12ab9f" and m.entries[2].color != (0x12, 0xAB, 0x9F)
    sb.handle_event(key(pygame.K_RETURN))
    assert m.entries[2].color == (0x12, 0xAB, 0x9F) and not hx.focused and sb.picker_idx == 2
    assert m.to_data()["equations"][2]["color"] == [0x12, 0xAB, 0x9F]
    assert sb.custom.color == (0x12, 0xAB, 0x9F)


def test_hex_box_invalid_stays_open_and_flags_error(tmp_path):
    m, sb = make(tmp_path)
    old = m.entries[0].color
    sb.open_picker(0)
    hx = sb.custom.hex
    sb.handle_event(down(hx.rect.center))
    sb.handle_event(text("#12zz"))                                    # z is not a hex digit: dropped
    assert hx.text == "#12"
    sb.handle_event(key(pygame.K_RETURN))
    assert hx.invalid and hx.focused and m.entries[0].color == old
    sb.handle_event(key(pygame.K_BACKSPACE))
    assert not hx.invalid and hx.text == "#1"
    sb.handle_event(text("234567890"))
    assert len(hx.text) == config.PICKER_HEX_MAX
    sb.draw_popups(pygame.display.get_surface())


def test_esc_drops_hex_edit_first_then_closes_picker(tmp_path):
    m, sb = make(tmp_path)
    sb.open_picker(0)
    sb.handle_event(down(sb.custom.hex.rect.center))
    sb.handle_event(text("#000001"))
    assert sb.handle_event(key(pygame.K_ESCAPE))
    assert not sb.custom.hex.focused and sb.picker_idx == 0 and sb.custom.hex.text == to_hex(m.entries[0].color)
    assert sb.handle_event(key(pygame.K_ESCAPE)) and sb.picker_idx is None


def test_picker_is_modal_for_keys_and_clicks_outside_close_it(tmp_path):
    m, sb = make(tmp_path)
    sb.open_picker(0)
    assert sb.handle_event(key(pygame.K_a)) and sb.handle_event(text("x"))      # swallowed
    old = m.entries[0].color
    assert sb.handle_event(down((1000, 500))) and sb.picker_idx is None and m.entries[0].color == old


def test_custom_row_set_color_syncs_widgets():
    row = CustomRow()
    row.set_rect(pygame.Rect(0, 0, 126, CustomRow.height()))
    row.set_color((0, 0, 255))
    assert abs(row.hue_strip.pos - 2 / 3) < 0.01 and row.val_strip.pos == 1.0 and row.hex.text == "#0000FF"
    row.set_color((0, 0, 0))
    assert row.hex.text == "#000000" and row.color == (0, 0, 0)
    row.draw(pygame.Surface((200, 100)))


def test_opening_picker_shows_the_rows_color(tmp_path):
    m, sb = make(tmp_path)
    m.set_color(1, (12, 200, 99))
    sb.open_picker(1)
    assert parse_hex(sb.custom.hex.text) == (12, 200, 99)
