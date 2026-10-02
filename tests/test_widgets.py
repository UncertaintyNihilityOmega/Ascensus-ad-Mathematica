"""Page widgets (Tabs, Slider, NumberField, ScrollArea, IconButton) driven by synthetic events."""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402
import pytest  # noqa: E402

from ascensus.ui import widgets  # noqa: E402
from ascensus.ui.widgets import IconButton, NumberField, ScrollArea, Slider, Tabs, fmt_number  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _pg():
    pygame.init()
    pygame.display.set_mode((400, 300))
    widgets._fonts.clear()                  # fonts cached before another module's pygame.quit() are dead
    widgets._text_cache.clear()
    yield
    widgets._fonts.clear()
    widgets._text_cache.clear()
    pygame.quit()


def down(pos, button=1):
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=button)


def up(pos):
    return pygame.event.Event(pygame.MOUSEBUTTONUP, pos=pos, button=1)


def move(pos):
    return pygame.event.Event(pygame.MOUSEMOTION, pos=pos, rel=(0, 0), buttons=(1, 0, 0))


def key(k):
    return pygame.event.Event(pygame.KEYDOWN, key=k, mod=0, unicode="")


def text(s):
    return pygame.event.Event(pygame.TEXTINPUT, text=s)


def test_fmt_number():
    assert fmt_number(3.0) == "3" and fmt_number(0.5) == "0.5" and fmt_number(0.05) == "0.05"
    assert fmt_number(7.6, is_int=True) == "8" and fmt_number(-0.0) == "0"


@pytest.mark.parametrize("vertical", [True, False])
def test_tabs_select_and_layout(vertical):
    t = Tabs(pygame.Rect(10, 10, 160 if vertical else 400, 40), ["Alpha", "Beta", "Gamma"], vertical=vertical)
    rects = t.item_rects()
    assert len(rects) == 3 and not rects[0].colliderect(rects[1])
    assert t.handle_event(down(rects[1].center)) and t.selected == 1
    assert not t.handle_event(down(rects[1].center)) and t.selected == 1      # same tab: no change
    assert not t.handle_event(down((399, 299))) and t.selected == 1           # miss
    assert not t.handle_event(down(rects[2].center, button=3)) and t.selected == 1
    t.draw(pygame.display.get_surface())
    t.set_rect(pygame.Rect(50, 50, 160, 40))
    assert t.item_rects()[0].topleft == (50, 50)


def test_slider_click_drag_snap_clamp():
    s = Slider(pygame.Rect(0, 0, 216, 20), -5, 5, 0, step=0.01)
    assert s.value == 0.0
    assert s.handle_event(down((s.knob_x() + 50, 10))) and s.dragging
    v = s.value
    assert 0.0 < v <= 5.0 and abs(v * 100 - round(v * 100)) < 1e-6              # snapped to 0.01
    s.handle_event(move((10_000, 10)))
    assert s.value == 5.0                                                       # clamped at the right
    s.handle_event(move((-10_000, 10)))
    assert s.value == -5.0
    s.handle_event(up((0, 0)))
    assert not s.dragging
    assert not s.handle_event(move((100, 10)))                                  # no drag, no change
    s.value = 123
    assert s.value == 5.0
    s.draw(pygame.display.get_surface())
    s2 = Slider(pygame.Rect(0, 0, 100, 20), 0, 10, 3, step=2)
    assert s2.value == 4.0                                                      # snapped to the step grid
    flat = Slider(pygame.Rect(0, 0, 100, 20), 1, 1, 1)                          # lo == hi must not divide by 0
    flat.handle_event(down((50, 10)))
    assert flat.value == 1.0


def test_number_field_edit_apply_cancel():
    f = NumberField(pygame.Rect(0, 0, 100, 30), 2.5, lo=-10, hi=100)
    assert not f.focused and f.display_text() == "2.5"
    assert not f.handle_event(down((5, 5))) and f.focused and f.text == "2.5"
    f.handle_event(text("1"))                       # first character replaces the old text
    f.handle_event(text("2.5x"))                    # junk is filtered
    assert f.text == "12.5"
    f.handle_event(key(pygame.K_BACKSPACE))
    assert f.text == "12."
    assert f.handle_event(key(pygame.K_RETURN)) and f.value == 12.0 and not f.focused
    # Esc cancels
    f.handle_event(down((5, 5)))
    f.handle_event(text("99"))
    assert not f.handle_event(key(pygame.K_ESCAPE)) and not f.focused and f.value == 12.0
    # clamp
    f.handle_event(down((5, 5)))
    f.handle_event(text("1e9"))
    assert f.handle_event(key(pygame.K_RETURN)) and f.value == 100.0
    f.handle_event(down((5, 5)))
    f.handle_event(text("-500"))
    f.handle_event(key(pygame.K_RETURN))
    assert f.value == -10.0
    # invalid text stays focused with the error flag
    f.handle_event(down((5, 5)))
    f.handle_event(text("--"))
    assert not f.handle_event(key(pygame.K_RETURN)) and f.focused and f.invalid
    f.handle_event(key(pygame.K_BACKSPACE))
    assert not f.invalid
    # click outside cancels; typing while unfocused is ignored
    f.handle_event(down((300, 200)))
    assert not f.focused
    f.handle_event(text("7"))
    assert f.value == -10.0
    f.update(0.3)
    f.handle_event(down((5, 5)))
    f.draw(pygame.display.get_surface())


def test_number_field_int_rounds_and_no_clamp():
    f = NumberField(pygame.Rect(0, 0, 100, 30), 4, is_int=True)
    f.handle_event(down((5, 5)))
    f.handle_event(text("7.6"))
    f.handle_event(key(pygame.K_RETURN))
    assert f.value == 8 and f.display_text() == "8"
    f.handle_event(down((5, 5)))
    f.handle_event(text("-123456"))
    f.handle_event(key(pygame.K_RETURN))
    assert f.value == -123456                           # no limits given: outside any slider range is fine
    f.handle_event(down((5, 5)))
    f.handle_event(text("1" * 40))
    assert len(f.text) <= 14


def test_scroll_area_wheel_hover_clamp_and_helpers():
    a = ScrollArea(pygame.Rect(100, 50, 200, 120), content_h=400)
    wheel = pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=-1)
    assert not a.handle_event(wheel, mouse_pos=(5, 5)) and a.scroll == 0           # not hovered
    assert a.handle_event(wheel, mouse_pos=(150, 100))
    assert a.scroll == 3 * 40                                                      # 3 rows per notch
    for _ in range(10):
        a.handle_event(wheel, mouse_pos=(150, 100))
    assert a.scroll == a.max_scroll == 280
    a.handle_event(pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=2), mouse_pos=(150, 100))
    assert a.scroll == 280 - 240
    # coordinate helpers
    a.set_scroll(40)
    assert a.to_content((110, 60)) == (10, 50) and a.to_screen_y(90) == 100
    assert a.origin() == (100, 10) and a.offset_rect(pygame.Rect(0, 100, 10, 10)).topleft == (100, 110)
    assert a.visible(40, 10) and not a.visible(0, 30) and not a.visible(200, 10)
    a.scroll_to(300, 20)
    assert a.scroll == 200
    a.set_content_height(50)                                                       # fits: no scroll
    assert a.scroll == 0 and a._thumb() is None
    a.set_content_height(400)
    a.set_rect(pygame.Rect(0, 0, 200, 500))                                        # resize re-clamps
    assert a.scroll == 0 and a.max_scroll == 0


def test_scroll_area_clip_and_scrollbar_drag():
    surf = pygame.display.get_surface()
    a = ScrollArea(pygame.Rect(100, 50, 200, 100), content_h=300)
    old = a.begin_clip(surf)
    assert surf.get_clip() == a.rect
    a.end_clip(surf, old)
    assert surf.get_clip() == old
    thumb = a._thumb()
    assert thumb.right == a.rect.right and thumb.w == 4
    a.handle_event(down(thumb.center))
    a.handle_event(move((thumb.centerx, a.rect.bottom + 500)))
    assert a.scroll == a.max_scroll
    a.handle_event(up((0, 0)))
    a.handle_event(move((thumb.centerx, 0)))
    assert a.scroll == a.max_scroll                                                # drag ended
    a.draw_scrollbar(surf)


def test_icon_button_and_icons_draw():
    surf = pygame.display.get_surface()
    b = IconButton(pygame.Rect(10, 10, 24, 24), "plus")
    assert b.handle_event(down((20, 20))) and not b.handle_event(down((100, 100)))
    b.enabled = False
    assert not b.handle_event(down((20, 20)))
    for kind in ("plus", "minus", "reset", "play", "pause", "cross"):
        surf.fill((0, 0, 0))
        widgets.draw_icon(surf, kind, pygame.Rect(10, 10, 24, 24), (255, 255, 255))
        assert surf.get_bounding_rect().w > 0, kind
        IconButton(pygame.Rect(0, 0, 24, 24), kind).draw(surf)
