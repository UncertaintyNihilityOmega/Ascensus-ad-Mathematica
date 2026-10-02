"""Export / Import of save slots: portable .ascensus files, any slot to any slot, validation, page flow."""
import json
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402
import pytest  # noqa: E402

from ascensus import view  # noqa: E402
from ascensus.profile import Profile, set_profile  # noqa: E402
from ascensus.saves_scene import SavesScene  # noqa: E402
from ascensus.savegame import EXPORT_FORMAT, SlotStore, read_export, restore  # noqa: E402
from ascensus.scenes import GameScene  # noqa: E402
from ascensus.ui import filedialog, widgets  # noqa: E402


@pytest.fixture(autouse=True)
def _pg():
    pygame.init()
    pygame.display.set_mode((1280, 720))
    view.set_size(1280, 720)
    widgets._fonts.clear()
    widgets._text_cache.clear()
    set_profile(Profile.in_memory())
    yield
    set_profile(None)


@pytest.fixture
def store(tmp_path):
    return SlotStore(tmp_path / "slots")


def game(t: float = 3295.0) -> GameScene:
    g = GameScene(seed=1, profile=Profile.in_memory())
    g.equations.add("Sakuna: 0= sin(x*a)*sin(y*a)")
    g.equations.add("y = x")
    g.game_t, g.kills = t, 42
    return g


def click(scene, pos):
    scene.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1))


def test_export_slot6_import_into_slot1(store, tmp_path):
    assert store.save_game(6, game())
    out = tmp_path / "run.ascensus"
    assert store.export_slot(6, out)
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["format"] == EXPORT_FORMAT and payload["thumbnail"]
    assert store.import_into(1, out)
    assert store.load(1)["equations"] == store.load(6)["equations"]
    assert store.thumb_path(1).read_bytes() == store.thumb_path(6).read_bytes()
    g = restore(store.load(1), profile=Profile.in_memory())
    assert g.game_t == pytest.approx(3295.0) and [e.parsed.name for e in g.equations.entries] == ["Sakuna", None]


def test_export_of_an_empty_slot_fails(store, tmp_path):
    assert not store.export_slot(2, tmp_path / "x.ascensus")
    assert not (tmp_path / "x.ascensus").exists()


@pytest.mark.parametrize("content", ["not json", "[]", json.dumps({"format": "other", "save": {}}),
                                     json.dumps({"format": EXPORT_FORMAT, "version": 1, "save": {"version": 1}}),
                                     json.dumps({"format": EXPORT_FORMAT, "version": 99, "save": {}})])
def test_foreign_or_damaged_files_are_rejected(store, tmp_path, content):
    bad = tmp_path / "bad.ascensus"
    bad.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError):
        read_export(bad)
    with pytest.raises(ValueError):
        store.import_into(1, bad)
    assert store.load(1) is None


def test_a_broken_thumbnail_is_dropped_but_the_save_imports(store, tmp_path):
    store.save_game(3, game())
    out = tmp_path / "run.ascensus"
    store.export_slot(3, out)
    payload = json.loads(out.read_text(encoding="utf-8"))
    payload["thumbnail"] = "bm90IGEgcG5n"                       # "not a png"
    out.write_text(json.dumps(payload), encoding="utf-8")
    assert store.import_into(4, out) and store.load(4) is not None and not store.thumb_path(4).exists()


def test_page_export_and_import_with_confirmation(store, tmp_path, monkeypatch):
    store.save_game(6, game())
    out = tmp_path / "picked.ascensus"
    monkeypatch.setattr(filedialog, "ask_save_path", lambda name: out)
    monkeypatch.setattr(filedialog, "ask_open_path", lambda: out)
    page = SavesScene(None, lambda: None, store)
    page.draw(pygame.display.get_surface())
    click(page, page.card_parts(5)["export"].center)                # slot 6 -> file
    assert out.exists() and "Exported slot 6" in page.note[0]
    assert "Time Capsule" in page.note[0]
    click(page, page.card_parts(0)["import"].center)                # file -> empty slot 1: no question
    assert page.dialog is None and store.load(1) is not None and "Homecoming" in page.note[0]
    click(page, page.card_parts(5)["import"].center)                # into the filled slot 6: confirm first
    assert page.dialog == ("import", 6)
    click(page, page.dialog_rects["ok"].center)
    assert page.dialog is None and "Imported" in page.note[0]
    page.draw(pygame.display.get_surface())


def test_cancelled_or_unavailable_dialogs(store, monkeypatch):
    store.save_game(2, game())
    page = SavesScene(None, lambda: None, store)
    monkeypatch.setattr(filedialog, "ask_save_path", lambda name: None)
    monkeypatch.setattr(filedialog, "ask_open_path", lambda: None)
    assert not page.export_slot(2) and not page.pick_import(1) and page.note is None

    def unavailable(*a):
        raise filedialog.FileDialogError("No file dialog available")
    monkeypatch.setattr(filedialog, "ask_open_path", unavailable)
    assert not page.pick_import(1) and page.note[1] is True


def test_buttons_fit_on_every_card_size(store):
    store.save_game(1, game())
    for w, h in ((800, 600), (1366, 768), (1920, 1080)):
        view.set_size(w, h)
        pygame.display.set_mode((w, h))
        page = SavesScene(game(), lambda: None, store)
        for i in range(6):
            parts = page.card_parts(i)
            row = [parts[k] for k in ("save", "export", "import", "delete")]
            assert all(parts["card"].contains(r) for r in row)
            assert all(a.right <= b.left for a, b in zip(row, row[1:]))
        page.draw(pygame.display.get_surface())
    view.set_size(1280, 720)
