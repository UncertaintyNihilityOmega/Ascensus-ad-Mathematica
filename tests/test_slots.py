"""SlotStore: slot files, thumbnails, autosave, corrupt-file tolerance, the ASCENSUS_SLOTS path."""
import json
import os
import subprocess
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402
import pytest  # noqa: E402

from ascensus import config, view  # noqa: E402
from ascensus.profile import Profile  # noqa: E402
from ascensus.savegame import AUTO, SlotStore, restore, snapshot  # noqa: E402
from ascensus.scenes import GameScene  # noqa: E402
from ascensus.ui import widgets  # noqa: E402


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


@pytest.fixture
def store(tmp_path):
    return SlotStore(tmp_path / "slots")


def game(t: float = 75.0, kills: int = 9) -> GameScene:
    g = GameScene(seed=1, save_path=None, profile=Profile.in_memory())
    g.equations.add("y = sin(x)")
    g.game_t, g.kills = t, kills
    return g


def test_empty_store_lists_six_empty_slots(store):
    assert store.list() == [None] * config.SAVE_SLOTS == [None] * 6
    assert not store.has_autosave() and store.load(1) is None and store.autosave_info() is None


def test_save_and_load_a_slot_with_thumbnail(store):
    assert store.save_game(2, game())
    assert (store.dir / "slot2.json").exists() and (store.dir / "slot2.png").exists()
    info = store.list()[1]
    assert info.slot == 2 and info.game_t == 75.0 and info.kills == 9 and info.thumb is not None
    assert store.list()[0] is None and len(info.date_text()) == 16
    img = pygame.image.load(str(info.thumb))
    assert img.get_size() == (320, 180)
    g2 = restore(store.load(2), save_path=None, profile=Profile.in_memory())
    assert g2.game_t == 75.0 and [e.text for e in g2.equations.entries] == ["y = sin(x)"]


def test_save_overwrites_and_delete_removes_files(store):
    store.save_game(1, game(10.0, 1))
    store.save_game(1, game(20.0, 2))
    assert store.list()[0].game_t == 20.0
    store.delete(1)
    assert store.list()[0] is None
    assert not (store.dir / "slot1.json").exists() and not (store.dir / "slot1.png").exists()
    store.delete(1)                                          # deleting an empty slot is fine


def test_save_without_thumbnail_removes_a_stale_png(store):
    store.save_game(3, game())
    assert store.save(3, snapshot(game(5.0)))
    assert store.list()[2].thumb is None and not (store.dir / "slot3.png").exists()


def test_autosave_cycle(store):
    assert store.autosave(game(125.0, 4))
    assert (store.dir / "autosave.json").exists() and (store.dir / "autosave.png").exists()
    assert store.has_autosave() and store.autosave_info().game_t == 125.0
    assert store.load(AUTO)["game_t"] == 125.0 == store.load_autosave()["game_t"]
    assert store.list() == [None] * 6                        # the autosave is not one of the six
    store.delete_autosave()
    assert not store.has_autosave() and not (store.dir / "autosave.png").exists()


@pytest.mark.parametrize("text", ["", "{not json", "[]", '{"version": 1}', '{"version": 2, "game_t": 1}', "null"])
def test_corrupt_files_read_as_empty(store, text):
    store.dir.mkdir(parents=True)
    (store.dir / "slot4.json").write_text(text, encoding="utf-8")
    (store.dir / "autosave.json").write_text(text, encoding="utf-8")
    assert store.load(4) is None and store.info(4) is None and store.list()[3] is None
    assert not store.has_autosave()
    store.save_game(4, game())                               # a corrupt slot can be overwritten
    assert store.list()[3] is not None


def test_wrong_typed_fields_read_as_empty(store):
    data = snapshot(game())
    data["game_t"] = "soon"
    store.dir.mkdir(parents=True)
    (store.dir / "slot1.json").write_text(json.dumps(data), encoding="utf-8")
    assert store.list()[0] is None


def test_bad_slot_number_is_rejected(store):
    for bad in (0, 7, -1, "x"):
        with pytest.raises(ValueError):
            store.json_path(bad)


def test_unwritable_folder_returns_false(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    s = SlotStore(blocker / "slots")                         # a "folder" below a regular file
    assert s.save_game(1, game()) is False
    assert s.list() == [None] * 6 and not s.has_autosave()


def test_unreadable_png_is_ignored_by_info(store):
    store.save_game(1, game())
    (store.dir / "slot1.png").write_bytes(b"not a png")
    assert store.list()[0].game_t == 75.0                    # the page loads the png lazily and tolerates this


def test_env_variable_sets_the_default_slots_folder(tmp_path):
    env = {**os.environ, "ASCENSUS_SLOTS": str(tmp_path / "elsewhere")}
    out = subprocess.run([sys.executable, "-c", "from ascensus import config; print(config.SLOTS_PATH)"],
                         capture_output=True, text=True, env=env, cwd=str(config.ROOT), check=True)
    assert out.stdout.strip() == str(tmp_path / "elsewhere")
    assert config.SLOTS_PATH.name == "slots" or "ASCENSUS_SLOTS" in os.environ
