"""Mouse editing in the equation box: click to place the cursor, drag / Shift+click to select, double-click
selects a word; keyboard editing and the clipboard keep working on the mouse selection."""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402
import pytest  # noqa: E402

from ascensus import config, view  # noqa: E402
from ascensus.ui import inputbox as ib  # noqa: E402
from ascensus.ui.inputbox import InputBox  # noqa: E402
from ascensus.ui.widgets import get_font  # noqa: E402


@pytest.fixture(autouse=True)
def _pg(monkeypatch):
    pygame.init()
    pygame.display.set_mode((1280, 720))
    view.set_size(1280, 720)
    clock = {"t": 0}
    monkeypatch.setattr(pygame.time, "get_ticks", lambda: clock["t"])
    monkeypatch.setattr(pygame.key, "get_mods", lambda: 0)
    yield clock


def x_of(box: InputBox, i: int) -> int:
    """Screen x of the boundary before character i (no scroll for short text)."""
    return box._inner().left + get_font(config.INPUT_FONT).size(box.text[:i])[0]


def down(box, x, clock, dt=1000):
    clock["t"] += dt
    box.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(x, box.rect.centery), button=1))


def move(box, x):
    box.handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=(x, box.rect.centery), rel=(0, 0), buttons=(1, 0, 0)))


def up(box, x):
    box.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=(x, box.rect.centery), button=1))


def make(text="y = sin(x) + abc"):
    box = InputBox()
    box.set_text(text)
    return box


def test_click_places_the_cursor_at_the_nearest_boundary(_pg):
    box = make()
    for i in (0, 4, 7, len(box.text)):
        down(box, x_of(box, i) + 1, _pg)
        up(box, x_of(box, i) + 1)
        assert box.cursor == i and box.selection() is None
    down(box, box.rect.right - 2, _pg)                       # past the end: the end
    assert box.cursor == len(box.text)


def test_click_focuses_an_unfocused_box(_pg):
    box = InputBox()
    assert not box.focused
    down(box, box.rect.centerx, _pg)
    assert box.focused


def test_drag_selects_and_typing_replaces_it(_pg):
    box = make()
    down(box, x_of(box, 4), _pg)
    move(box, x_of(box, 10))
    up(box, x_of(box, 10))
    assert box.selection() == (4, 10) and box.text[4:10] == "sin(x)"
    box.handle_event(pygame.event.Event(pygame.TEXTINPUT, text="cos(y)"))
    assert box.text == "y = cos(y) + abc"


def test_drag_backwards_and_a_plain_click_clears_the_selection(_pg):
    box = make()
    down(box, x_of(box, 10), _pg)
    move(box, x_of(box, 4))
    up(box, x_of(box, 4))
    assert box.selection() == (4, 10) and box.cursor == 4
    down(box, x_of(box, 2), _pg)
    up(box, x_of(box, 2))
    assert box.selection() is None and box.cursor == 2


def test_shift_click_extends_from_the_cursor(_pg, monkeypatch):
    box = make()
    down(box, x_of(box, 4), _pg)
    up(box, x_of(box, 4))
    monkeypatch.setattr(pygame.key, "get_mods", lambda: pygame.KMOD_SHIFT)
    down(box, x_of(box, 10), _pg)
    up(box, x_of(box, 10))
    assert box.selection() == (4, 10)


def test_double_click_selects_a_word(_pg):
    box = make()
    i = box.text.index("abc") + 1
    down(box, x_of(box, i), _pg)
    up(box, x_of(box, i))
    down(box, x_of(box, i), _pg, dt=config.DOUBLE_CLICK_MS - 50)
    up(box, x_of(box, i))
    assert box.selection() == (box.text.index("abc"), len(box.text))
    # slow second click: just a click
    down(box, x_of(box, 1), _pg, dt=config.DOUBLE_CLICK_MS + 200)
    assert box.selection() is None


def test_copy_cut_work_on_a_mouse_selection(_pg, monkeypatch):
    clip = {}
    monkeypatch.setattr(ib, "set_clipboard", lambda t: clip.update(t=t))
    box = make()
    down(box, x_of(box, 4), _pg)
    move(box, x_of(box, 10))
    up(box, x_of(box, 10))
    box.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_x, mod=pygame.KMOD_CTRL, unicode=""))
    assert clip["t"] == "sin(x)" and box.text == "y =  + abc"


def test_click_maps_correctly_when_long_text_is_scrolled(_pg):
    box = make("y = " + "+".join(f"sin({k}x)" for k in range(12)))
    assert box._scroll() > 0                                  # the cursor is at the end: text scrolled
    end_x = box._inner().left + get_font(config.INPUT_FONT).size(box.text)[0] - box._scroll()
    down(box, end_x, _pg)
    assert box.cursor == len(box.text)
