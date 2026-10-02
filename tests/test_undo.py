"""EquationManager undo stack (10 deletions) and the UndoToast widget."""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402
import pytest  # noqa: E402

from ascensus import config, view  # noqa: E402
from ascensus.equations import EquationManager  # noqa: E402
from ascensus.ui import widgets  # noqa: E402
from ascensus.ui.undo_toast import UndoToast  # noqa: E402


@pytest.fixture(autouse=True)
def _pg():
    pygame.init()
    pygame.display.set_mode((1280, 720))
    view.set_size(1280, 720)
    widgets._fonts.clear()
    widgets._text_cache.clear()
    yield
    widgets._fonts.clear()
    widgets._text_cache.clear()


def mgr(*texts: str) -> EquationManager:
    m = EquationManager(None)
    for t in texts:
        m.add(t)
    return m


def test_nothing_to_undo():
    m = mgr("y = x")
    assert not m.can_undo and m.undo_delete() is None


def test_delete_then_undo_restores_the_entry_in_place():
    m = mgr("y = x", "y = sin(x)", "y = cos(x)")
    m.set_color(1, (1, 2, 3))
    m.toggle(1)
    gone = m.entries[1]
    m.delete(1)
    assert [e.text for e in m.entries] == ["y = x", "y = cos(x)"] and m.can_undo
    back = m.undo_delete()
    assert back is gone and not m.can_undo
    assert [e.text for e in m.entries] == ["y = x", "y = sin(x)", "y = cos(x)"]
    assert back.color == (1, 2, 3) and back.enabled is False


def test_undo_is_last_in_first_out_and_clamps_the_index():
    m = mgr("y = 1", "y = 2", "y = 3")
    m.delete(2)
    m.delete(0)
    m.delete(0)                                              # list is empty now
    assert [m.undo_delete().text for _ in range(3)] == ["y = 2", "y = 1", "y = 3"]
    assert [e.text for e in m.entries] == ["y = 1", "y = 2", "y = 3"]


def test_stack_keeps_only_ten():
    m = mgr(*[f"y = {i}" for i in range(12)])
    for _ in range(12):
        m.delete(0)
    assert config.UNDO_MAX == 10
    restored = []
    while m.can_undo:
        restored.append(m.undo_delete().text)
    assert len(restored) == 10 and restored[0] == "y = 11" and restored[-1] == "y = 2"


def test_undo_re_adds_variables_with_their_values():
    m = mgr("y = a*x", "y = b + x")
    m.store.set_value("a", 3.5)
    m.store.vars["a"].playing = True
    m.delete(0)
    assert "a" not in m.store and "b" in m.store
    m.undo_delete()
    assert "a" in m.store and m.store.get("a").value == 3.5 and m.store.get("a").playing
    assert m.store.values["a"] == 3.5 and m.store.names() == ["b", "a"]


def test_shared_variable_stays_when_another_equation_uses_it():
    m = mgr("y = a*x", "y = a + 1")
    m.store.set_value("a", 4.0)
    m.delete(0)
    assert m.store.get("a").value == 4.0
    m.undo_delete()
    assert m.store.get("a").value == 4.0


def test_undone_curve_is_rebuilt():
    m = mgr("y = x", "y = 2")
    m.delete(0)
    e = m.undo_delete()
    assert e.curve is None                                   # rebuilt by update()
    import numpy as np
    from ascensus.enemies import Swarm
    m.update(0.016, 0.0, Swarm(np.random.default_rng(0)), np.zeros(2))
    assert e.curve is not None and len(e.curve.points) > 0


def test_name_clash_drops_the_entry():
    m = mgr("eq1: y = x")
    m.delete(0)
    m.add("eq1: y = 5")
    assert m.undo_delete() is None and not m.can_undo
    assert [e.text for e in m.entries] == ["eq1: y = 5"]


def test_full_list_keeps_the_entry_on_the_stack(monkeypatch):
    m = mgr("y = 1", "y = 2")
    m.delete(0)
    monkeypatch.setattr(config, "MAX_ROWS", 1)
    assert m.undo_delete() is None and m.can_undo
    m.delete(0)                                              # make room (this also stacks)
    monkeypatch.setattr(config, "MAX_ROWS", 5)
    assert m.undo_delete().text == "y = 2"


def test_loading_or_replacing_the_list_clears_the_stack():
    m = mgr("y = 1", "y = 2")
    m.delete(0)
    m.apply_data({"equations": [{"text": "y = 9", "enabled": True, "color": [1, 2, 3]}], "variables": {}})
    assert not m.can_undo and [e.text for e in m.entries] == ["y = 9"]


def test_undo_saves_to_disk(tmp_path):
    p = tmp_path / "eq.json"
    m = EquationManager(p)
    m.add("y = 1")
    m.add("y = 2")
    m.delete(0)
    m.undo_delete()
    m2 = EquationManager(p)
    m2.load()
    assert [e.text for e in m2.entries] == ["y = 1", "y = 2"]


# --- the toast ------------------------------------------------------------------------------------
def click(pos):
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1)


def test_toast_shows_for_five_seconds():
    t = UndoToast()
    assert not t.active
    t.show("eq4")
    assert t.active and config.UNDO_TOAST_TIME == 5.0
    t.update(4.9)
    assert t.active
    t.update(0.2)
    assert not t.active


def test_toast_click_on_undo_returns_true_and_hides():
    t = UndoToast()
    t.show("eq4")
    assert not t.handle_event(click((0, 0)))                 # elsewhere: ignored
    assert not t.handle_event(click((t.box.left + 4, t.box.centery)))      # the 'Deleted eq4 -' text
    assert t.active
    assert t.handle_event(click(t.undo_rect.center)) and not t.active


def test_toast_ignores_clicks_when_hidden_and_other_buttons():
    t = UndoToast()
    assert not t.handle_event(click(t.undo_rect.center))
    t.show("eq4")
    assert not t.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=t.undo_rect.center, button=3))
    assert t.active


def test_toast_draws_and_survives_resize_and_long_names():
    screen = pygame.display.get_surface()
    t = UndoToast()
    t.show("a_really_long_equation_name_that_must_be_cut_with_dots")
    t.draw(screen)
    assert t.box.width < 700
    view.set_size(800, 600)
    t.on_resize()
    assert t.box.centerx == 400 and t.box.right <= 800 and t.box.left >= 0
    t.draw(pygame.Surface((800, 600)))
    assert t.undo_rect.right <= t.box.right + 12
    view.set_size(1280, 720)
