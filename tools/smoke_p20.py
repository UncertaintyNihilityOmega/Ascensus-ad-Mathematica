"""P20 smoke phase: saves, slots, autosave and undo (runnable standalone; smoke.py can call phase(screen))."""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
_TMP = Path(tempfile.gettempdir())
os.environ.setdefault("ASCENSUS_PROFILE", str(_TMP / f"ascensus_smoke_p20_profile_{os.getpid()}.json"))
os.environ.setdefault("ASCENSUS_SETTINGS", str(_TMP / f"ascensus_smoke_p20_settings_{os.getpid()}.json"))
os.environ.setdefault("ASCENSUS_SLOTS", str(_TMP / f"ascensus_smoke_p20_slots_{os.getpid()}"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import shutil  # noqa: E402

import numpy as np  # noqa: E402
import pygame  # noqa: E402

from ascensus import config, view  # noqa: E402
from ascensus.profile import Profile  # noqa: E402
from ascensus.saves_scene import SavesScene  # noqa: E402
from ascensus.savegame import SlotStore, restore, snapshot  # noqa: E402
from ascensus.scenes import GameScene  # noqa: E402
from ascensus.ui import widgets  # noqa: E402
from ascensus.ui.undo_toast import UndoToast  # noqa: E402

DT = 1 / 60


def _click(scene, pos) -> None:
    scene.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1))


def _step(scene, screen) -> None:
    scene.update(DT)
    scene.draw(screen)


def _same(a: dict, b: dict) -> None:
    """Snapshots equal apart from nothing at all (the RNG is not part of a save)."""
    assert a == b, [k for k in a if a[k] != b.get(k)]


def _play(screen) -> GameScene:
    """A game that has seen a few hundred frames: equations, a variable, enemies, a boss, XP."""
    game = GameScene(seed=11, profile=Profile.in_memory())
    for text in ("y = a*sin(x)", "y = x^2/8 - 3", "y = 2cos(x + t)"):
        game.equations.add(text)
    game.equations.set_color(1, (250, 120, 30))
    game.direction_override = (1.0, 0.4)
    game.game_t = config.BOSS_INTERVAL - 2.0                 # a boss spawns within the run
    for _ in range(400):
        _step(game, screen)
    assert len(game.swarm) > 5 and game.swarm.boss.any(), (len(game.swarm), game.swarm.boss.any())
    game.upgrades.add_xp(300)
    game.buy("max_hp")
    game.equations.store.set_value("a", 3.0)
    game.equations.store.vars["a"].playing = True
    for _ in range(20):
        _step(game, screen)
    return game


def _saves_page(screen, w: int, h: int, store: SlotStore, game) -> SavesScene:
    view.set_size(w, h)
    screen = pygame.display.set_mode((w, h))
    page = SavesScene(game, lambda: game, store=store)
    widgets.reset_overflow()
    for _ in range(5):
        _step(page, screen)
    assert widgets.overflow_count == 0, widgets.overflow_log
    assert all(pygame.Rect(0, 0, w, h).contains(c) for c in page.cards)
    return page


def phase(screen) -> None:
    """Play, save to a slot, restore and compare, the Saves page at three sizes, autosave and undo."""
    slots_dir = _TMP / f"ascensus_smoke_p20_run_{os.getpid()}"
    shutil.rmtree(slots_dir, ignore_errors=True)
    store = SlotStore(slots_dir)
    old_size = (view.W, view.H)
    view.set_size(1280, 720)
    screen = pygame.display.set_mode((1280, 720))
    print("--- P20 saves")

    game = _play(screen)
    game.paused = True

    # Save to a slot through the page, with the overwrite confirmation, then load it back
    page = _saves_page(screen, 1280, 720, store, game)
    _click(page, page.card_parts(1)["save"].center)
    assert store.list()[1] is not None and store.list()[1].thumb is not None
    _click(page, page.card_parts(1)["save"].center)           # filled: asks first
    assert page.dialog == ("overwrite", 2)
    _click(page, page.dialog_rects["cancel"].center)
    snap = snapshot(game)
    again = restore(store.load(2), profile=Profile.in_memory())
    saved = store.load(2)
    saved.pop("saved_at", None)
    _same(saved, snap)                                       # what the slot holds is the paused game
    _same(snapshot(again), snap)
    for _ in range(120):                                     # the restored run plays on
        _step(again, screen)
    assert again.game_t > game.game_t and again.equations.active()[0].curve is not None

    # Page at 1280x720, 1920x1080, 800x600 and after a resize back
    for w, h in ((1280, 720), (1920, 1080), (800, 600)):
        page = _saves_page(screen, w, h, store, game)
        _click(page, page.card_parts(0)["save"].center)
        assert store.list()[0] is not None
        _click(page, page.card_parts(0)["delete"].center)
        _click(page, page.card_parts(0)["delete"].center)
        assert store.list()[0] is None
    view.set_size(1280, 720)
    page.on_resize()
    _step(page, pygame.display.set_mode((1280, 720)))
    _click(page, page.card_parts(1)["thumb"].center)         # from "pause": confirm, then load
    _click(page, page.dialog_rects["ok"].center)
    loaded = page.next_scene
    assert isinstance(loaded, GameScene) and abs(loaded.game_t - game.game_t) < 1e-9
    print(f"  slots OK ({len(game.swarm)} enemies, {len(game.equations.entries)} equations)")

    # Autosave round trip (written to the slots folder, not one of the six slots)
    assert not store.has_autosave()
    assert store.autosave(game) and store.has_autosave()
    info = store.autosave_info()
    assert abs(info.game_t - game.game_t) < 1e-9 and info.thumb is not None
    cont = restore(store.load_autosave(), profile=Profile.in_memory())
    _same(snapshot(cont), snapshot(game))
    store.delete_autosave()
    assert not store.has_autosave() and not (slots_dir / "autosave.png").exists()
    print("  autosave OK")

    # Undo delete: manager stack and the toast
    fm = loaded.equations
    names = [e.text for e in fm.entries]
    fm.delete(0)
    toast = UndoToast()
    toast.show("eq1")
    for _ in range(10):
        toast.update(DT)
        toast.draw(screen)
    assert toast.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=toast.undo_rect.center, button=1))
    back = fm.undo_delete()
    assert back is not None and [e.text for e in fm.entries] == names
    assert "a" in fm.store and fm.store.get("a").value == game.equations.store.get("a").value
    for _ in range(30):
        _step(loaded, screen)
    assert fm.entries[0].curve is not None
    toast.show("eq1")
    toast.update(config.UNDO_TOAST_TIME + 0.1)
    assert not toast.active
    print("  undo OK")

    shutil.rmtree(slots_dir, ignore_errors=True)
    glue_phase(screen)
    view.set_size(*old_size)
    pygame.display.set_mode(old_size)


def glue_phase(screen) -> None:
    """Menu / pause lists, Continue, autosave rules, Saves from pause, Del + undo toast and Ctrl+Z."""
    from ascensus.scenes import GameOverScene, MenuScene
    default = SlotStore()                                    # the folder games autosave to (ASCENSUS_SLOTS)
    shutil.rmtree(default.dir, ignore_errors=True)
    for w, h in ((800, 600), (1280, 720), (1920, 1080)):
        view.set_size(w, h)
        screen = pygame.display.set_mode((w, h))
        game = _play(screen)
        game.slots = default
        widgets.reset_overflow()
        game.paused = True
        game.on_resize()
        _step(game, screen)
        names = [b.label for b in (game.resume_btn, game.stats_btn, game.saves_btn, game.settings_btn,
                                   game.library_btn, game.menu_btn)]
        assert names == ["Resume", "Stats", "Saves", "Settings", "Library", "Main Menu"]
        # Pause -> Saves -> Back returns the same paused game
        _click(game, game.saves_btn.rect.center)
        page = game.next_scene
        game.next_scene = None
        assert isinstance(page, SavesScene) and page.game is game
        _step(page, screen)
        _click(page, page.back_btn.rect.center)
        assert page.next_scene is game and game.paused
        # Pause -> Main Menu writes the autosave; the menu then offers Continue (mm:ss) above Play
        default.delete_autosave()
        _click(game, game.menu_btn.rect.center)
        menu = game.next_scene
        game.next_scene = None
        assert isinstance(menu, MenuScene) and default.has_autosave()
        assert list(menu.buttons)[:2] == ["Continue", "Play"] and menu.buttons["Continue"].label.startswith("Continue (")
        for _ in range(3):
            _step(menu, screen)
        rects = [b.rect for b in menu.buttons.values()]
        assert all(pygame.Rect(0, 0, w, h).contains(r) for r in rects)
        assert all(a.bottom <= b.top for a, b in zip(rects, rects[1:]))
        _click(menu, menu.buttons["Continue"].rect.center)
        cont = menu.next_scene
        assert isinstance(cont, GameScene) and abs(cont.game_t - game.game_t) < 1e-9
        assert widgets.overflow_count == 0, widgets.overflow_log

        # Autosave on the 60 s timer, deleted on game over
        cont.slots = default
        default.delete_autosave()
        cont._autosave_t = config.AUTOSAVE_PERIOD - 0.01
        for _ in range(3):
            _step(cont, screen)
        assert default.has_autosave()

        # Del -> toast -> Undo click, then Del -> Ctrl+Z
        fm, names0 = cont.equations, [e.text for e in cont.equations.entries]
        _click(cont, cont.sidebar.rects(0)["delete"].center)
        assert cont.undo_toast.active and len(fm.entries) == len(names0) - 1
        _step(cont, screen)
        _click(cont, cont.undo_toast.undo_rect.center)
        assert [e.text for e in fm.entries] == names0
        _click(cont, cont.sidebar.rects(1)["delete"].center)
        cont.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_z, mod=pygame.KMOD_CTRL, unicode=""))
        assert [e.text for e in fm.entries] == names0 and not cont.undo_toast.active

        cont.player.hp = 0.0
        _step(cont, screen)
        assert isinstance(cont.next_scene, GameOverScene) and not default.has_autosave()
    print("  menu / pause / continue / autosave / undo glue OK at 800x600, 1280x720, 1920x1080")
    shutil.rmtree(default.dir, ignore_errors=True)


def main() -> None:
    pygame.init()
    phase(pygame.display.set_mode((1280, 720)))
    print("smoke_p20 OK")


if __name__ == "__main__":
    main()
