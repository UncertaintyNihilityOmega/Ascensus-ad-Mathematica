"""P11: VariableStore semantics, dirty tracking, save round-trip, sidebar variable rows."""
import json
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import numpy as np  # noqa: E402
import pygame  # noqa: E402
import pytest  # noqa: E402

from ascensus import config, view  # noqa: E402
from ascensus.enemies import Swarm  # noqa: E402
from ascensus.formulas import FormulaManager  # noqa: E402
from ascensus.mathparse import FormulaError  # noqa: E402
from ascensus.ui import sidebar as sidebar_mod  # noqa: E402
from ascensus.ui import widgets  # noqa: E402
from ascensus.ui.inputbox import InputBox  # noqa: E402
from ascensus.ui.sidebar import Sidebar  # noqa: E402
from ascensus.variables import VariableStore  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _pg():
    pygame.init()
    pygame.display.set_mode((1280, 720))
    view.set_size(1280, 720)
    for mod in (widgets, sidebar_mod):                  # fonts cached before another module's pygame.quit() are dead
        for cache in ("_fonts", "_text_cache", "_bold_fonts", "_bold_cache"):
            getattr(mod, cache, {}).clear()
    yield
    pygame.quit()


def down(pos):
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1)


def up(pos):
    return pygame.event.Event(pygame.MOUSEBUTTONUP, pos=pos, button=1)


def move(pos):
    return pygame.event.Event(pygame.MOUSEMOTION, pos=pos, rel=(0, 0), buttons=(1, 0, 0))


def key(k):
    return pygame.event.Event(pygame.KEYDOWN, key=k, mod=0, unicode="")


def text(s):
    return pygame.event.Event(pygame.TEXTINPUT, text=s)


def tick(m, dt=0.016, t=0.0):
    m.update(dt, t, Swarm(np.random.default_rng(0)), np.zeros(2))


# --- store semantics -----------------------------------------------------
def test_create_remove_and_disabled_counts():
    m = FormulaManager()
    seen = []
    m.store.listener = lambda ev, **d: seen.append((ev, d["name"]))
    m.add("a*x")
    m.add("y = b + a")
    assert m.store.names() == ["a", "b"] and m.store.get("a").value == config.VAR_DEFAULT
    assert seen == [("var_created", "a"), ("var_created", "b")]
    m.toggle(0)                                    # a disabled equation still uses its variables
    assert m.store.names() == ["a", "b"]
    m.delete(1)                                    # b gone; a still used by the disabled row
    assert m.store.names() == ["a"]
    m.replace(0, "y = c x")                        # replace swaps the variable
    assert m.store.names() == ["c"]
    m.delete(0)
    assert len(m.store) == 0


def test_value_survives_while_used_and_dies_with_it():
    m = FormulaManager()
    m.add("a*x")
    m.store.set_value("a", 3.5)
    m.add("y = a")
    m.delete(1)
    assert m.store.get("a").value == 3.5
    m.delete(0)
    m.add("a*x")
    assert m.store.get("a").value == config.VAR_DEFAULT


def test_too_many_variables(monkeypatch):
    monkeypatch.setattr(config, "MAX_VARIABLES", 3)
    m = FormulaManager()
    m.add("y = a+b+c")
    with pytest.raises(FormulaError, match=r"Too many variables \(3\)"):
        m.add("y = d")
    assert len(m.entries) == 1 and m.store.names() == ["a", "b", "c"]
    m.add("y = a")                                 # existing names are fine
    with pytest.raises(FormulaError, match="Too many variables"):
        m.replace(1, "y = d")                      # a is still used by row 0, d would be a 4th
    m.replace(0, "y = d + a")                      # frees b and c
    assert m.store.names() == ["a", "d"]


def test_set_value_is_free_and_tracks_changed():
    s = VariableStore()
    s.sync(["a"])
    s.set_value("a", 123.456)                      # outside +-5 is allowed
    assert s.get("a").value == 123.456 and s.values["a"] == 123.456
    assert s.drain_changed() == {"a"} and s.drain_changed() == set()
    s.set_value("a", 123.456)                      # same value: not a change
    assert s.drain_changed() == set()
    s.set_value("a", float("nan"))
    assert s.get("a").value == 123.456


def test_ping_pong_bounds_direction_and_steps():
    s = VariableStore()
    s.sync(["a"])
    s.set_value("a", config.VAR_MAX - 2 * config.VAR_STEP)
    s.toggle_play("a")
    seen = []
    for _ in range(6):
        s.update(1.0 / config.VAR_PLAY_HZ + 1e-9)   # exactly one tick per update
        seen.append(round(s.get("a").value, 2))
    assert seen == [4.99, 5.0, 4.99, 4.98, 4.97, 4.96]
    assert s.get("a").dir == -1
    lo = config.VAR_MIN
    s.set_value("a", lo + config.VAR_STEP)
    s.get("a").dir = -1
    s.update(2.5 / config.VAR_PLAY_HZ)             # two whole ticks: lo, then back up one
    assert round(s.get("a").value, 2) == round(lo + config.VAR_STEP, 2) and s.get("a").dir == 1


def test_play_dt_spike_and_bounds():
    s = VariableStore()
    s.sync(["a"])
    s.toggle_play("a")
    for dt in (0.0, 0.016, 5.0, 123.456, 1e4):
        s.update(dt)
        v = s.get("a").value
        assert config.VAR_MIN - 1e-9 <= v <= config.VAR_MAX + 1e-9
        k = (v - config.VAR_MIN) / config.VAR_STEP
        assert abs(k - round(k)) < 1e-6                 # always on a step
    s.set_value("a", 40.0)                              # typed far outside: next tick snaps into range
    s.update(1.0 / config.VAR_PLAY_HZ)
    assert s.get("a").value <= config.VAR_MAX


def test_play_accumulates_fractional_ticks_and_slow_mo():
    s = VariableStore()
    s.sync(["a"])
    s.set_value("a", 0.0)
    s.toggle_play("a")
    for _ in range(60):                                 # 60 frames of 1/120 s = 30 ticks
        s.update(1 / 120)
    assert abs(s.get("a").value - 0.30) < 1e-6


def test_play_event_only_when_starting():
    s = VariableStore()
    ev = []
    s.listener = lambda e, **d: ev.append((e, d))
    s.sync(["a"], quiet=True)
    s.toggle_play("a")
    s.toggle_play("a")
    s.set_playing("a", False)
    s.set_playing("a", True)
    assert ev == [("var_play", {"name": "a"})] * 2


# --- dirty tracking ----------------------------------------------------------
def test_dirty_only_for_equations_using_the_variable():
    m = FormulaManager()
    m.add("y = a x")
    m.add("y = b x")
    m.add("y = x")
    tick(m)
    ea, eb, ec = m.entries
    m.store.set_value("a", 2.0)
    tick(m)
    assert ea.var_dirty and not eb.var_dirty and not ec.var_dirty
    assert m._is_dirty(ea) and not m._is_dirty(eb) and not m._is_dirty(ec)
    before = (ea.curve, eb.curve, ec.curve)
    tick(m, dt=1.0 / config.T_REBUILD_HZ + 0.01)
    assert ea.curve is not before[0] and eb.curve is before[1] and ec.curve is before[2]
    assert not ea.var_dirty
    tick(m, dt=1.0)                                    # nothing changed: nothing rebuilds
    assert ea.curve is not before[0] and m.entries[0].curve is ea.curve


def test_curve_uses_variable_values_and_rate_limit():
    m = FormulaManager()
    m.add("y = a")                                     # horizontal line at y = a
    e = m.entries[0]
    ys0 = e.curve.points[:, 1].mean()
    m.store.set_value("a", 3.0)
    builds = []
    orig = m._rebuild
    m._rebuild = lambda *a, **k: (builds.append(1), orig(*a, **k))[1]
    for _ in range(30):                                # 30 frames of 10 ms: 0.3 s -> at most ~3 rebuilds
        m.store.set_value("a", m.store.get("a").value + 0.01)
        tick(m, dt=0.01)
    assert 1 <= len(builds) <= 4
    assert e.curve.points[:, 1].mean() < ys0 - 2.0 * config.UNIT_PX      # moved up on screen


def test_queued_curves_are_not_animated():
    m = FormulaManager()
    for k in range(config.MAX_ACTIVE):
        m.add(f"y = x + {k}")
    m.add("y = a x")
    q = m.entries[-1]
    assert m.status(q) == "queued"
    old = q.curve
    m.store.set_value("a", 2.0)
    for _ in range(40):
        tick(m, dt=0.05)
    assert q.curve is old and q.var_dirty


def test_rebuilds_per_frame_budget():
    m = FormulaManager()
    for k in range(config.MAX_ACTIVE):
        m.add(f"y = a x + {k}")
    m.store.set_value("a", 2.0)
    tick(m, dt=0.0)
    counts = []
    orig = m._rebuild
    m._rebuild = lambda *a, **k: (counts.append(1), orig(*a, **k))[1]
    tick(m, dt=1.0)
    assert len(counts) <= config.REBUILDS_PER_FRAME


# --- save round trip ---------------------------------------------------------
def test_save_round_trip_values_and_playing(tmp_path):
    path = tmp_path / "f.json"
    m = FormulaManager(path)
    m.add("y = a x + b")
    m.store.set_value("a", -2.25)
    m.store.set_value("b", 17.5)
    m.store.set_playing("b", True)
    m.save()
    data = json.loads(path.read_text())
    assert data["variables"] == {"a": {"value": -2.25, "playing": False},
                                 "b": {"value": 17.5, "playing": True}}
    seen = []
    m2 = FormulaManager(path)
    m2.store.listener = lambda ev, **d: seen.append(ev)
    m2.load()
    assert m2.store.names() == ["a", "b"]
    assert m2.store.get("a").value == -2.25 and not m2.store.get("a").playing
    assert m2.store.get("b").value == 17.5 and m2.store.get("b").playing
    assert m2.entries[0].curve is not None and seen == []         # loading is silent
    # v1 file: variables get the default
    path.write_text('{"version":1,"formulas":[{"text":"a x","enabled":true}]}')
    m2.load()
    assert m2.store.get("a").value == config.VAR_DEFAULT
    # junk: saved variables nobody uses vanish, malformed values are ignored
    path.write_text(json.dumps({"version": 2, "formulas": [{"text": "a x"}],
                                "variables": {"zz": {"value": 3}, "a": {"value": "oops"}}}))
    m2.load()
    assert m2.store.names() == ["a"] and m2.store.get("a").value == config.VAR_DEFAULT


# --- sidebar rows ------------------------------------------------------------
def make_sidebar(*texts):
    m = FormulaManager()
    for t in texts:
        m.add(t)
    return m, Sidebar(m, InputBox())


def test_sections_split_and_names():
    m, sb = make_sidebar("y = a x", "y = b")
    assert sb.variable_names() == ["a", "b"]
    full = view.H - config.SIDEBAR_HEADER_H
    assert sb.eq_rect().height == int(full * (1 - config.SIDEBAR_VARS_FRACTION))
    vr = sb.var_rect()
    assert vr.top == sb.eq_rect().bottom + config.SIDEBAR_SECTION_H and vr.bottom == view.H
    m.delete(1)
    m.delete(0)
    assert sb.var_rect() is None and sb.eq_rect().height == full


def test_slider_click_drag_snaps_and_stops_play():
    m, sb = make_sidebar("y = a x")
    m.store.set_playing("a", True)
    sl = sb.var_rects(0)["slider"]
    r = config.SLIDER_KNOB_R
    x0, x1 = sl.left + r, sl.right - r
    assert sb.handle_event(down((sl.centerx, sl.centery)))
    assert sb.var_drag == "a" and not m.store.get("a").playing
    v = m.store.get("a").value
    assert abs(v) < 0.1 and abs(v * 100 - round(v * 100)) < 1e-6
    sb.handle_event(move((x1 + 50, sl.centery)))                  # past the end: clamped to max
    assert m.store.get("a").value == config.VAR_MAX
    sb.handle_event(move((x0 + (x1 - x0) * 0.3337, sl.centery)))
    v = m.store.get("a").value
    assert abs(v - (config.VAR_MIN + 0.3337 * (config.VAR_MAX - config.VAR_MIN))) < 0.01
    assert abs(v * 100 - round(v * 100)) < 1e-6                   # snapped to 0.01
    sb.handle_event(up((x0, sl.centery)))
    assert sb.var_drag is None
    sb.handle_event(move((x1, sl.centery)))                       # no longer dragging
    assert m.store.get("a").value != config.VAR_MAX


def test_play_button_toggles():
    m, sb = make_sidebar("y = a x")
    seen = []
    m.store.listener = lambda ev, **d: seen.append(ev)
    p = sb.var_rects(0)["play"]
    assert sb.handle_event(down(p.center))
    assert m.store.get("a").playing and seen == ["var_play"]
    sb.handle_event(down(p.center))
    assert not m.store.get("a").playing


def test_value_box_type_enter_escape_and_focus():
    m, sb = make_sidebar("y = a x")
    box = sb.var_rects(0)["box"]
    assert not sb.value_focused
    assert sb.handle_event(down(box.center)) and sb.value_focused
    sb.handle_event(text("12.5"))                                 # outside +-5 is fine
    sb.handle_event(key(pygame.K_RETURN))
    assert m.store.get("a").value == 12.5 and not sb.value_focused
    sb.handle_event(down(box.center))
    sb.handle_event(text("3"))
    assert sb.handle_event(key(pygame.K_ESCAPE)) and m.store.get("a").value == 12.5
    assert not sb.value_focused
    sb.handle_event(down(box.center))                             # click elsewhere cancels, too
    sb.handle_event(text("9"))
    sb.handle_event(down((view.W - 10, 10)))
    assert not sb.value_focused and m.store.get("a").value == 12.5
    sb.handle_event(down(box.center))                             # bad text stays focused, no change
    sb.handle_event(text("-"))
    sb.handle_event(key(pygame.K_RETURN))
    assert sb.value_focused and m.store.get("a").value == 12.5
    sb.handle_event(key(pygame.K_ESCAPE))


def test_editing_variable_removed_mid_edit():
    m, sb = make_sidebar("y = a x")
    sb.handle_event(down(sb.var_rects(0)["box"].center))
    assert sb.value_focused
    m.delete(0)
    sb.update(0.016)
    assert not sb.value_focused and sb.var_edit is None


def test_variable_wheel_scroll_is_independent():
    m = FormulaManager()
    for i in range(30):
        m._append(f"y = a_{i} + x", build=False)
    sb = Sidebar(m, InputBox())
    vr = sb.var_rect()
    assert sb.var_max_scroll() == 30 * config.VAR_ROW_H - vr.height > 0
    ev = pygame.event.Event(pygame.MOUSEWHEEL, pos=vr.center, x=0, y=-1)
    assert sb.handle_event(ev)
    assert sb.var_scroll == config.SIDEBAR_SCROLL_ROWS * config.VAR_ROW_H and sb.scroll == 0
    ev = pygame.event.Event(pygame.MOUSEWHEEL, pos=sb.eq_rect().center, x=0, y=-1)
    sb.handle_event(ev)
    assert sb.scroll > 0 and sb.var_scroll == config.SIDEBAR_SCROLL_ROWS * config.VAR_ROW_H
    # hit-testing follows the scroll: the row under the pointer is offset by 3
    i = sb._var_row_at(vr.center)
    assert i == int((vr.height // 2 + sb.var_scroll) // config.VAR_ROW_H)
    surf = pygame.Surface((view.W, view.H))
    sb.draw(surf)                                                 # draws clipped rows without error
