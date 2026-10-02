"""P10: scrolling sidebar, drag in a scrolled list, colour picker, save v2, queued layer, input clipboard."""
import json
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import numpy as np  # noqa: E402
import pygame  # noqa: E402
import pytest  # noqa: E402

from ascensus import config, view  # noqa: E402
from ascensus.enemies import Swarm  # noqa: E402
from ascensus.equations import EquationManager  # noqa: E402
from ascensus.ui import inputbox  # noqa: E402
from ascensus.ui.inputbox import InputBox  # noqa: E402
from ascensus.ui.sidebar import Sidebar  # noqa: E402

ROW = config.SIDEBAR_ROW_H


@pytest.fixture(scope="module", autouse=True)
def _pg():
    pygame.init()
    pygame.display.set_mode((1280, 720))
    view.set_size(1280, 720)
    yield
    pygame.quit()


def lazy_manager(n, path=None):
    """n rows with no curves built (cheap): enough for sidebar geometry tests."""
    m = EquationManager(path)
    for k in range(n):
        m._append(f"y = x + {k}", build=False)
    return m


def down(pos):
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1)


def up(pos):
    return pygame.event.Event(pygame.MOUSEBUTTONUP, pos=pos, button=1)


def move(pos):
    return pygame.event.Event(pygame.MOUSEMOTION, pos=pos, rel=(0, 0), buttons=(1, 0, 0))


def wheel(pos, y):
    return pygame.event.Event(pygame.MOUSEWHEEL, pos=pos, x=0, y=y)


def keydown(k, mod=0):
    return pygame.event.Event(pygame.KEYDOWN, key=k, mod=mod, unicode="")


# --- scrolling -----------------------------------------------------------
def test_scroll_math_and_wheel():
    sb = Sidebar(lazy_manager(40), InputBox())
    viewport = view.H - config.SIDEBAR_HEADER_H
    assert sb.max_scroll() == 40 * ROW - viewport
    inside = (50, config.SIDEBAR_HEADER_H + 100)
    assert sb.handle_event(wheel(inside, -1))                  # one notch down = 3 rows
    assert sb.scroll == config.SIDEBAR_SCROLL_ROWS * ROW == 132
    sb.handle_event(wheel(inside, 1))
    assert sb.scroll == 0
    sb.handle_event(wheel(inside, 1))                          # clamped at the top
    assert sb.scroll == 0
    for _ in range(50):
        sb.handle_event(wheel(inside, -1))
    assert sb.scroll == sb.max_scroll()                        # clamped at the bottom
    assert sb.row_rect(39).bottom == sb.eq_rect().bottom       # last row ends at the viewport edge
    assert not sb.handle_event(wheel((900, 300), -1))          # not hovered: ignored


def test_short_list_does_not_scroll_and_resize_follows_view():
    sb = Sidebar(lazy_manager(3), InputBox())
    assert sb.max_scroll() == 0
    sb.handle_event(wheel((50, 100), -1))
    assert sb.scroll == 0
    sb2 = Sidebar(lazy_manager(40), InputBox())
    before = sb2.max_scroll()
    view.set_size(1000, 500)
    try:
        sb2.on_resize()
        assert sb2.panel_rect.height == 500 and sb2.max_scroll() == before + 220
    finally:
        view.set_size(1280, 720)


def test_row_hit_testing_follows_scroll():
    sb = Sidebar(lazy_manager(40), InputBox())
    sb.scroll_rows(10)
    top = sb.eq_rect().top
    assert sb._row_at((50, top + 2)) == 10
    assert sb._row_at((50, top + ROW + 2)) == 11
    assert sb._row_at((50, top - 5)) is None                   # header area is not a row
    sb.scroll = 10 * ROW + 20                                  # mid-row offset
    assert sb._row_at((50, top + 10)) == 10 and sb._row_at((50, top + 30)) == 11


# --- drag in a scrolled list ----------------------------------------------
def test_drag_reorder_in_scrolled_list():
    m = lazy_manager(40)
    names = [e.text for e in m.entries]
    sb = Sidebar(m, InputBox())
    sb.scroll_rows(12)
    src = sb.row_rect(14).move(20, 0).center                   # visible on screen
    dst = sb.row_rect(12).move(20, 0).center
    sb.handle_event(down(src))
    for k in range(1, 7):
        sb.handle_event(move((src[0], src[1] + (dst[1] - src[1]) * k // 6)))
    assert sb.dragging and sb.drag_idx == 14 and sb.drag_target == 12
    sb.handle_event(up(dst))
    assert [e.text for e in m.entries][12:15] == [names[14], names[12], names[13]]
    assert not sb.dragging


def test_drag_autoscrolls_near_edge():
    m = lazy_manager(60)
    sb = Sidebar(m, InputBox())
    src = sb.row_rect(2).move(20, 0).center
    sb.handle_event(down(src))
    bottom = sb.eq_rect().bottom - 10                          # within the 30 px zone
    sb.handle_event(move((src[0], bottom)))
    assert sb.dragging and sb.scroll == 0
    t0 = sb.drag_target
    sb.update(0.5)
    assert sb.scroll > 0 and sb.drag_target > t0
    s1 = sb.scroll
    for _ in range(100):
        sb.update(0.5)
    assert sb.scroll == sb.max_scroll() > s1 and sb.drag_target == 59
    sb.handle_event(move((src[0], sb.eq_rect().top + 5)))      # now the top zone scrolls back up
    sb.update(0.5)
    assert sb.scroll < sb.max_scroll()
    sb.handle_event(up((src[0], sb.eq_rect().top + 5)))
    assert not sb.dragging


def test_drag_not_started_in_middle_zone_does_not_scroll():
    sb = Sidebar(lazy_manager(60), InputBox())
    src = sb.row_rect(3).move(20, 0).center
    sb.handle_event(down(src))
    sb.handle_event(move((src[0], src[1] + 40)))
    sb.update(1.0)
    assert sb.scroll == 0
    sb.handle_event(up((src[0], src[1] + 40)))


# --- colour picker -------------------------------------------------------
def test_picker_pick_close_and_save(tmp_path):
    path = tmp_path / "f.json"
    m = EquationManager(path)
    for t in ("x^2", "sin(x)", "x = 2"):
        m.add(t)
    sb = Sidebar(m, InputBox())
    sw = sb.rects(1)["swatch"]
    assert sb.handle_event(down(sw.center)) and sb.picker_idx == 1
    assert pygame.Rect(0, 0, view.W, view.H).contains(sb.picker_rect)
    cell = sb._picker_cell(13)
    assert cell.size == (22, 22) and sb._picker_cell(5).y > sb._picker_cell(0).y    # 5 per row
    assert sb._picker_cell(5).x == sb._picker_cell(0).x
    assert len({tuple(sb._picker_cell(k).topleft) for k in range(20)}) == 20
    assert sb.handle_event(down(cell.center))
    assert m.entries[1].color == config.CURVE_PALETTE_20[13] and sb.picker_idx is None
    assert json.loads(path.read_text())["equations"][1]["color"] == list(config.CURVE_PALETTE_20[13])
    # click outside closes without changing anything
    old = m.entries[2].color
    sb.handle_event(down(sb.rects(2)["swatch"].center))
    assert sb.picker_idx == 2
    assert sb.handle_event(down((900, 400))) and sb.picker_idx is None
    assert m.entries[2].color == old
    # Esc closes
    sb.handle_event(down(sb.rects(0)["swatch"].center))
    assert sb.handle_event(keydown(pygame.K_ESCAPE)) and sb.picker_idx is None
    sb.draw(pygame.display.get_surface())                      # popup + rows draw without error
    sb.open_picker(0)
    sb.draw(pygame.display.get_surface())


def test_new_equations_take_first_unused_color_then_cycle():
    pal = config.CURVE_PALETTE_20
    assert len(pal) == 20 and len(set(pal)) == 20
    m = lazy_manager(0)
    for k in range(20):
        assert m._append(f"y = x + {k}", build=False).color == pal[k]
    assert m._append("y = x + 20", build=False).color == pal[0]           # all used: cycle
    assert m._append("y = x + 21", build=False).color == pal[1]           # ...and keeps cycling evenly


# --- save format ---------------------------------------------------------
def test_save_v2_and_load_v1_v2(tmp_path):
    path = tmp_path / "f.json"
    m = EquationManager(path)
    m.add("x^2")
    m.add("sin(x)")
    m.set_color(1, (1, 2, 3))
    m.toggle(0)
    m.add("a x")
    m.store.set_value("a", 2.5)
    m.save()
    data = json.loads(path.read_text())
    assert data["version"] == 2 and data["variables"] == {"a": {"value": 2.5, "playing": False}}
    assert data["equations"][1] == {"text": "sin(x)", "enabled": True, "color": [1, 2, 3]}
    m2 = EquationManager(path)
    m2.load()
    assert [(e.text, e.enabled, e.color) for e in m2.entries[:2]] == [
        ("x^2", False, m.entries[0].color), ("sin(x)", True, (1, 2, 3))]
    assert m2.variables == data["variables"]
    # v1 files (no colour, no variables) still load, with fresh palette colours
    path.write_text('{"version":1,"equations":[{"text":"x^2","enabled":true},{"text":"x = 2","enabled":false}]}')
    m2.load()
    assert [(e.text, e.enabled) for e in m2.entries] == [("x^2", True), ("x = 2", False)]
    assert [e.color for e in m2.entries] == config.CURVE_PALETTE_20[:2] and m2.variables == {}
    # bad colours fall back to the palette
    path.write_text('{"version":2,"equations":[{"text":"x^2","color":[1,2]},{"text":"x = 2","color":[999,0,0]}]}')
    m2.load()
    assert [e.color for e in m2.entries] == config.CURVE_PALETTE_20[:2]


# --- queued layer and progressive load -------------------------------------
def write_save(path, n):
    rows = [{"text": f"x = {k % 7 - 3}.{k % 9}", "enabled": True} for k in range(n)]
    path.write_text(json.dumps({"version": 2, "equations": rows, "variables": {}}))


def test_progressive_load(tmp_path):
    path = tmp_path / "f.json"
    write_save(path, 20)
    m = EquationManager(path)
    m.load()
    built = lambda: sum(e.curve is not None for e in m.entries)       # noqa: E731
    assert len(m.entries) == 20 and built() == config.MAX_ACTIVE      # only the active ones, at once
    assert all(e.curve is not None for e in m.active())
    sw = Swarm(np.random.default_rng(0))
    ORIGIN = np.zeros(2)
    m.update(1 / 60, 0.0, sw, ORIGIN)
    assert built() == config.MAX_ACTIVE + config.QUEUED_BUILD_PER_FRAME
    m.update(1 / 60, 0.0, sw, ORIGIN)
    assert built() == config.MAX_ACTIVE + 2 * config.QUEUED_BUILD_PER_FRAME
    for _ in range(10):
        m.update(1 / 60, 0.0, sw, ORIGIN)
    assert built() == 20


def test_only_active_entries_own_surfaces_and_queued_layer_is_shared(tmp_path):
    path = tmp_path / "f.json"
    write_save(path, config.MAX_ACTIVE + 4)
    m = EquationManager(path)
    m.load()
    sw = Swarm(np.random.default_rng(0))
    for _ in range(8):
        m.update(1 / 60, 0.0, sw, np.zeros(2))
    screen = pygame.Surface((view.W, view.H))
    screen.fill(config.BG_COLOR)
    m.draw(screen)
    active = m.active()
    assert all(e.surface is not None for e in active if len(e.curve.points))
    queued = [e for e in m.entries if not any(e is a for a in active)]
    assert len(queued) == 4 and all(e.surface is None for e in queued)
    layer = m._layer
    assert layer is not None and layer.get_size() == (view.W, view.H)
    # a queued vertical line is visible in the shared layer
    q = next(e for e in queued if len(e.curve.points))
    x, y = (int(v) for v in q.curve.points[len(q.curve.points) // 2])
    assert layer.get_at((x, y)).a == config.ALPHA_QUEUED
    # a change does not refresh the layer until QUEUED_LAYER_PERIOD has passed
    m.delete(len(m.entries) - 1)
    m.draw(screen)
    assert m._layer is layer and m._layer_age < config.QUEUED_LAYER_PERIOD
    sig = m._layer_sig
    m.draw(screen)
    assert m._layer_sig == sig
    for _ in range(int(config.QUEUED_LAYER_PERIOD * 60) + 2):
        m.update(1 / 60, 0.0, sw, np.zeros(2))
    m.draw(screen)
    assert m._layer_sig != sig                                 # refreshed after the period
    # a clean (unchanged) layer is never re-rendered
    sig = m._layer_sig
    for _ in range(130):
        m.update(1 / 60, 0.0, sw, np.zeros(2))
        m.draw(screen)
    assert m._layer_sig == sig


def test_queued_entry_moving_into_active_gets_its_own_surface():
    m = EquationManager()
    for k in range(config.MAX_ACTIVE + 1):
        m.add(f"x = {k - 3}.5")
    screen = pygame.Surface((view.W, view.H))
    m.draw(screen)
    last = m.entries[-1]
    assert m.status(last) == "queued" and last.surface is None
    m.toggle(0)                                                # one active row leaves; the queued one enters
    m.draw(screen)
    assert m.status(last) == "active" and last.surface is not None
    assert m.entries[0].surface is None


def test_rebuild_limits_two_per_frame_round_robin():
    m = EquationManager()
    texts = [f"y = sin(x + t) + {k}" for k in range(5)]
    for t in texts:
        m.add(t)
    calls = []
    orig = m._rebuild
    m._rebuild = lambda e, **kw: (calls.append(e.text), orig(e, **kw))
    sw = Swarm(np.random.default_rng(0))
    per_frame = []
    for i in range(61):
        n0 = len(calls)
        m.update(1 / 60, (i + 1) / 60, sw, np.zeros(2))
        per_frame.append(len(calls) - n0)
    assert max(per_frame) == config.REBUILDS_PER_FRAME == 2
    for t in texts:
        assert 6 <= calls.count(t) <= config.T_REBUILD_HZ + 1
    first_round = calls[:5]
    assert len(set(first_round)) == 5                          # round-robin: nobody twice before everybody once


def test_on_resize_rebuilds_active_now_and_queued_progressively(tmp_path):
    path = tmp_path / "f.json"
    write_save(path, config.MAX_ACTIVE + 3)
    m = EquationManager(path)
    m.load()
    sw = Swarm(np.random.default_rng(0))
    for _ in range(6):
        m.update(1 / 60, 0.0, sw, np.zeros(2))
    view.set_size(1000, 600)
    try:
        m.on_resize()
        assert [e.curve is not None for e in m.entries] == [True] * config.MAX_ACTIVE + [False] * 3
        assert all(e.curve.hit_mask.shape == (-(-600 // config.HIT_CELL), -(-1000 // config.HIT_CELL))
                   for e in m.active())
        m.update(1 / 60, 0.0, sw, np.zeros(2))
        assert sum(e.curve is not None for e in m.entries) == config.MAX_ACTIVE + 2
    finally:
        view.set_size(1280, 720)


# --- input box selection and clipboard -------------------------------------
class FakeScrap:
    """Stands in for pygame.scrap (which needs a real display)."""

    def __init__(self, text=""):
        self.text, self.puts = text, []

    def install(self, monkeypatch):
        monkeypatch.setattr(pygame.scrap, "get_init", lambda: True)
        monkeypatch.setattr(pygame.scrap, "get_text", lambda: self.text)
        monkeypatch.setattr(pygame.scrap, "put_text", lambda t: (self.puts.append(t), setattr(self, "text", t)))


def typed(box, text):
    box.handle_event(pygame.event.Event(pygame.TEXTINPUT, text=text))


CTRL, SHIFT = pygame.KMOD_CTRL, pygame.KMOD_SHIFT


def make_box(text=""):
    box = InputBox()
    box.focus()
    typed(box, text)
    return box


def test_shift_arrows_select_and_typing_replaces():
    box = make_box("hello world")
    box.handle_event(keydown(pygame.K_HOME))
    for _ in range(5):
        box.handle_event(keydown(pygame.K_RIGHT, SHIFT))
    assert box.selection() == (0, 5) and box.cursor == 5
    typed(box, "J")
    assert box.text == "J world" and box.cursor == 1 and box.selection() is None
    box.handle_event(keydown(pygame.K_END, SHIFT))
    assert box.selection() == (1, 7)
    box.handle_event(keydown(pygame.K_LEFT, SHIFT))
    assert box.selection() == (1, 6)
    box.handle_event(keydown(pygame.K_LEFT))                   # plain Left collapses to the selection start
    assert box.selection() is None and box.cursor == 1
    box.handle_event(keydown(pygame.K_END))
    box.handle_event(keydown(pygame.K_HOME, SHIFT))
    assert box.selection() == (0, 7)
    box.handle_event(keydown(pygame.K_BACKSPACE))              # deletes the selection, not one char
    assert box.text == "" and box.cursor == 0


def test_select_all_copy_cut_paste(monkeypatch):
    scrap = FakeScrap()
    scrap.install(monkeypatch)
    box = make_box("y = sin(x)")
    box.handle_event(keydown(pygame.K_c, CTRL))                # nothing selected: copies everything
    assert scrap.puts == ["y = sin(x)"] and box.text == "y = sin(x)"
    box.handle_event(keydown(pygame.K_a, CTRL))
    assert box.selection() == (0, 10)
    box.handle_event(keydown(pygame.K_x, CTRL))                # cut
    assert box.text == "" and scrap.puts[-1] == "y = sin(x)"
    box.handle_event(keydown(pygame.K_v, CTRL))
    assert box.text == "y = sin(x)" and box.cursor == 10
    box.cursor, box.anchor = 4, 7                              # select "sin"
    box.handle_event(keydown(pygame.K_c, CTRL))
    assert scrap.puts[-1] == "sin"
    box.handle_event(keydown(pygame.K_v, CTRL))                # paste over the selection
    assert box.text == "y = sin(x)" and box.cursor == 7


def test_paste_cleans_whitespace_and_respects_max_length(monkeypatch):
    scrap = FakeScrap("a\nb\r\nc\td")
    scrap.install(monkeypatch)
    box = make_box("")
    box.handle_event(keydown(pygame.K_v, CTRL))
    assert box.text == "a b c d"
    scrap.text = "x" * 500
    box.handle_event(keydown(pygame.K_v, CTRL))
    assert len(box.text) == config.MAX_EQUATION_LEN
    box.handle_event(keydown(pygame.K_a, CTRL))
    scrap.text = "z" * 500
    box.handle_event(keydown(pygame.K_v, CTRL))                # the selection is replaced; still capped
    assert box.text == "z" * config.MAX_EQUATION_LEN
    typed(box, "q")                                            # full: typing is ignored
    assert len(box.text) == config.MAX_EQUATION_LEN


def test_clipboard_failures_are_swallowed(monkeypatch):
    def boom(*a, **k):
        raise pygame.error("no clipboard")

    monkeypatch.setattr(pygame.scrap, "get_init", lambda: True)
    monkeypatch.setattr(pygame.scrap, "get_text", boom)
    monkeypatch.setattr(pygame.scrap, "put_text", boom)
    box = make_box("abc")
    box.handle_event(keydown(pygame.K_a, CTRL))
    box.handle_event(keydown(pygame.K_c, CTRL))                # put_text raises: ignored
    box.handle_event(keydown(pygame.K_v, CTRL))                # get_text raises: falls back to the app clipboard
    assert box.text == "abc"
    assert inputbox.clean_paste("x\ny") == "x y"


def test_selection_is_drawn_and_reset_on_clear():
    box = make_box("abcdef")
    box.cursor, box.anchor = 4, 1
    screen = pygame.Surface((1280, 720))
    box.draw(screen)
    px = screen.get_at((box.rect.left + config.INPUT_PAD + 3, box.rect.top + 10))
    assert px[:3] == config.INPUT_FILL                         # before the selection: plain fill
    from ascensus.ui.widgets import get_font
    font = get_font(config.INPUT_FONT)
    x = box.rect.left + config.INPUT_PAD + font.size("a")[0] + 4
    assert screen.get_at((x, box.rect.top + 8))[:3] == config.INPUT_SELECT_COLOR
    box.clear()
    assert box.anchor is None and box.selection() is None
