"""SavesScene: layout, Save / Delete / load flows with their confirmations, resize and text fitting."""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402
import pytest  # noqa: E402

from ascensus import config, view  # noqa: E402
from ascensus.game.profile import Profile  # noqa: E402
from ascensus.game.savegame import SlotStore  # noqa: E402
from ascensus.scenes.game import GameScene  # noqa: E402
from ascensus.scenes.saves_page import SavesScene, grid_shape  # noqa: E402
from ascensus.ui import widgets  # noqa: E402


@pytest.fixture(autouse=True)
def _pg():
    pygame.init()
    pygame.display.set_mode((1280, 720))
    view.set_size(1280, 720)
    widgets._fonts.clear()
    widgets._text_cache.clear()
    yield
    view.set_size(1280, 720)
    widgets._fonts.clear()
    widgets._text_cache.clear()


@pytest.fixture
def store(tmp_path):
    return SlotStore(tmp_path / "slots")


def game(t: float = 75.0, kills: int = 9) -> GameScene:
    g = GameScene(seed=1, profile=Profile.in_memory())
    g.equations.add("y = sin(x)")
    g.game_t, g.kills = t, kills
    g.paused = True
    return g


class Back:
    """A `back` callable that remembers it was used."""
    def __init__(self):
        self.scene = object()
        self.calls = 0

    def __call__(self):
        self.calls += 1
        return self.scene


def page(store, g=None, tmp_path=None):
    return SavesScene(g, Back(), store=store)


def click(sc, pos):
    sc.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1))


def key(sc, k):
    sc.handle_event(pygame.event.Event(pygame.KEYDOWN, key=k, mod=0, unicode=""))


def test_grid_shape_switches_at_1000px():
    assert grid_shape(1280) == (3, 2) and grid_shape(1000) == (3, 2)
    assert grid_shape(999) == (2, 3) and grid_shape(800) == (2, 3)


def test_cards_are_in_a_3x2_grid_and_inside_the_window(store):
    sc = page(store)
    assert len(sc.cards) == 6
    assert len({c.y for c in sc.cards}) == 2 and len({c.x for c in sc.cards}) == 3
    for c in sc.cards:
        assert pygame.Rect(0, 0, view.W, view.H).contains(c)
    for i, c in enumerate(sc.cards):
        parts = sc.card_parts(i)
        assert c.contains(parts["thumb"]) and c.contains(parts["save"]) and c.contains(parts["delete"])
        assert not parts["thumb"].colliderect(parts["save"]) and not parts["save"].colliderect(parts["delete"])


def test_narrow_window_uses_2x3_and_survives_resize(store):
    sc = page(store)
    for w, h in ((800, 600), (1920, 1080), (900, 900), (1280, 720)):
        view.set_size(w, h)
        sc.on_resize()
        cols = len({c.x for c in sc.cards})
        assert cols == grid_shape(w)[0]
        assert all(pygame.Rect(0, 0, w, h).contains(c) for c in sc.cards)
        sc.draw(pygame.Surface((w, h)))


def test_empty_page_draws_and_has_no_overflow_at_800x600(store):
    store.save_game(1, game(3599.0, 123456))
    view.set_size(800, 600)
    sc = page(store, game())
    sc.on_resize()
    widgets.reset_overflow()
    sc.draw(pygame.Surface((800, 600)))
    assert widgets.overflow_count == 0, widgets.overflow_log


def test_from_menu_save_is_disabled_and_empty_thumb_click_does_nothing(store):
    sc = page(store)
    click(sc, sc.card_parts(0)["save"].center)
    assert store.list() == [None] * 6 and sc.dialog is None
    click(sc, sc.card_parts(0)["thumb"].center)
    assert sc.next_scene is None


def test_save_into_an_empty_slot(store):
    sc = page(store, game(61.0, 5))
    click(sc, sc.card_parts(2)["save"].center)
    assert sc.dialog is None and sc.infos[2] is not None and sc.infos[2].game_t == 61.0
    assert store.list()[2].kills == 5 and sc.note is not None and "slot 3" in sc.note[0]
    sc.draw(pygame.display.get_surface())


def test_overwrite_asks_first_and_cancel_keeps_the_old_save(store):
    store.save_game(1, game(10.0, 1))
    sc = page(store, game(99.0, 2))
    click(sc, sc.card_parts(0)["save"].center)
    assert sc.dialog == ("overwrite", 1) and store.list()[0].game_t == 10.0
    sc.draw(pygame.display.get_surface())
    click(sc, sc.dialog_rects["cancel"].center)
    assert sc.dialog is None and store.list()[0].game_t == 10.0
    click(sc, sc.card_parts(0)["save"].center)
    click(sc, sc.dialog_rects["ok"].center)
    assert sc.dialog is None and store.list()[0].game_t == 99.0 and sc.infos[0].game_t == 99.0


def test_escape_closes_a_dialog_before_leaving(store):
    store.save_game(1, game())
    sc = page(store, game())
    click(sc, sc.card_parts(0)["save"].center)
    key(sc, pygame.K_ESCAPE)
    assert sc.dialog is None and sc.next_scene is None
    key(sc, pygame.K_ESCAPE)
    assert sc.next_scene is sc.back.scene


def test_delete_needs_a_second_click_within_three_seconds(store):
    store.save_game(4, game())
    sc = page(store)
    pos = sc.card_parts(3)["delete"].center
    click(sc, pos)
    assert sc.armed == (4, config.DELETE_CONFIRM_TIME) and store.list()[3] is not None
    sc.draw(pygame.display.get_surface())
    click(sc, pos)
    assert store.list()[3] is None and sc.infos[3] is None and sc.armed is None


def test_delete_confirmation_times_out_and_is_cancelled_by_other_clicks(store):
    store.save_game(1, game())
    store.save_game(2, game())
    sc = page(store)
    click(sc, sc.card_parts(0)["delete"].center)
    sc.update(2.9)
    assert sc.armed is not None
    sc.update(0.2)
    assert sc.armed is None
    click(sc, sc.card_parts(0)["delete"].center)                 # arm, then click elsewhere
    click(sc, sc.card_parts(5)["delete"].center)                 # empty slot's Delete: disabled
    click(sc, sc.card_parts(0)["delete"].center)                 # arms again, does not delete
    assert store.list()[0] is not None
    click(sc, sc.card_parts(1)["delete"].center)                 # a different slot: arms that one only
    assert sc.armed[0] == 2 and store.list()[1] is not None


def test_delete_on_an_empty_slot_does_nothing(store):
    sc = page(store)
    click(sc, sc.card_parts(0)["delete"].center)
    assert sc.armed is None


def test_clicking_a_thumbnail_from_the_menu_loads_it(store):
    store.save_game(2, game(88.0, 3))
    sc = page(store)
    click(sc, sc.card_parts(1)["thumb"].center)
    assert isinstance(sc.next_scene, GameScene) and sc.next_scene.game_t == 88.0
    assert [e.text for e in sc.next_scene.equations.entries] == ["y = sin(x)"]


def test_loading_from_pause_confirms_first(store):
    store.save_game(1, game(88.0, 3))
    current = game(5.0, 0)
    sc = page(store, current)
    click(sc, sc.card_parts(0)["thumb"].center)
    assert sc.next_scene is None and sc.dialog == ("load", 1)
    sc.draw(pygame.display.get_surface())
    click(sc, sc.dialog_rects["cancel"].center)
    assert sc.next_scene is None and sc.dialog is None
    click(sc, sc.card_parts(0)["thumb"].center)
    click(sc, sc.dialog_rects["ok"].center)
    assert isinstance(sc.next_scene, GameScene) and sc.next_scene is not current
    assert sc.next_scene.game_t == 88.0


def test_loading_a_corrupt_slot_shows_a_note_and_stays(store):
    store.save_game(1, game())
    sc = page(store)
    (store.dir / "slot1.json").write_text("{broken", encoding="utf-8")
    assert sc.infos[0] is not None                               # the page still has the old listing
    click(sc, sc.card_parts(0)["thumb"].center)
    assert sc.next_scene is None and sc.note is not None and sc.note[1] is True
    sc.draw(pygame.display.get_surface())


def test_a_slot_that_restores_badly_is_reported(store):
    store.save_game(1, game())
    data = store.load(1)
    data["swarm"]["hp"] = [1.0, 2.0]
    store.save(1, data)
    sc = page(store)
    assert not sc.load_slot(1) and sc.next_scene is None and sc.note[1]


def test_back_button_and_escape_return_to_the_caller(store):
    sc = page(store)
    click(sc, sc.back_btn.rect.center)
    assert sc.next_scene is sc.back.scene
    sc.next_scene = None
    key(sc, pygame.K_ESCAPE)
    assert sc.next_scene is sc.back.scene and sc.back.calls == 2


def test_note_expires(store):
    sc = page(store, game())
    sc.save_slot(1)
    assert sc.note is not None
    sc.update(config.SAVES_NOTE_TIME + 0.1)
    assert sc.note is None


def test_thumbnails_are_drawn_scaled_and_cached(store):
    store.save_game(1, game())
    sc = page(store)
    sc.draw(pygame.display.get_surface())
    size = sc.card_parts(0)["thumb"].size
    assert (1, *size) in sc._scaled
    view.set_size(1920, 1080)
    sc.on_resize()
    assert not sc._scaled
    sc.draw(pygame.Surface((1920, 1080)))
    assert (1, *sc.card_parts(0)["thumb"].size) in sc._scaled
