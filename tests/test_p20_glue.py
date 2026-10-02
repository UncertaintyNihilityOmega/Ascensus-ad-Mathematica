"""P20 glue: menu / pause lists, Continue, autosave rules, Saves from pause, undo toast and Ctrl+Z, speed."""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402
import pytest  # noqa: E402

from ascensus import config, view  # noqa: E402
from ascensus.main import autosave_live, track_game  # noqa: E402
from ascensus.profile import Profile, set_profile  # noqa: E402
from ascensus.saves_scene import SavesScene  # noqa: E402
from ascensus.savegame import SlotStore, restore, snapshot  # noqa: E402
from ascensus.scenes import GameOverScene, GameScene, MenuScene, button_stack, open_page  # noqa: E402
from ascensus.settings_scene import SettingsScene  # noqa: E402
from ascensus.ui import widgets  # noqa: E402


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
    view.set_size(1280, 720)
    widgets._fonts.clear()
    widgets._text_cache.clear()


def make(t: float = 83.0) -> GameScene:
    g = GameScene(seed=1, profile=Profile.in_memory())
    g.equations.add("eq1: y = a*x")
    g.equations.add("y = sin(x)")
    g.game_t = t
    return g


def click(scene, pos):
    scene.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1))


def key(scene, k, mod=0):
    scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=k, mod=mod, unicode=""))


def take(scene):
    nxt, scene.next_scene = scene.next_scene, None
    return nxt


# --- layout ------------------------------------------------------------------------------------------
@pytest.mark.parametrize("w,h", [(800, 600), (800, 800), (1280, 720), (1920, 1080)])
def test_menu_and_pause_buttons_fit_every_size(w, h):
    view.set_size(w, h)
    pygame.display.set_mode((w, h))
    SlotStore().save_game(1, make())
    SlotStore().autosave(make(125.0))                      # the Continue button is there too
    menu = MenuScene()
    assert list(menu.buttons)[:2] == ["Continue", "Play"] and len(menu.buttons) == 7
    screen = pygame.Surface((w, h))
    widgets.reset_overflow()
    menu.draw(screen)
    rects = [b.rect for b in menu.buttons.values()]
    assert all(pygame.Rect(0, 0, w, h).contains(r) for r in rects)
    assert all(a.bottom <= b.top for a, b in zip(rects, rects[1:])) and min(r.h for r in rects) >= 30
    game = make()
    game.paused = True
    game.on_resize()
    game.draw(screen)
    pr = [b.rect for b in (game.resume_btn, game.stats_btn, game.saves_btn, game.settings_btn,
                           game.library_btn, game.menu_btn)]
    assert all(pygame.Rect(0, 0, w, h).contains(r) for r in pr)
    assert all(a.bottom <= b.top for a, b in zip(pr, pr[1:])) and game.pause_top >= 0
    assert widgets.overflow_count == 0, widgets.overflow_log


def test_button_stack_shrinks_in_short_windows():
    view.set_size(800, 400)
    top, rects = button_stack(7, 130, 44)
    assert rects[-1].bottom + 44 <= 400 and rects[0].h < config.BUTTON_SIZE[1]
    view.set_size(1280, 720)
    assert button_stack(7, 130, 44)[1][0].h == config.BUTTON_SIZE[1]


def test_menu_lists():
    menu = MenuScene()
    assert list(menu.buttons) == ["Play", "Saves", "Settings", "Library", "Achievements", "Quit"]
    assert menu.buttons["Play"].label == "Play"
    g = make()
    g.paused = True
    assert [b.label for b in (g.resume_btn, g.stats_btn, g.saves_btn, g.settings_btn, g.library_btn,
                              g.menu_btn)] == ["Resume", "Stats", "Saves", "Settings", "Library", "Main Menu"]


# --- Continue ------------------------------------------------------------------------------------------
def test_continue_shows_the_run_time_above_play_and_loads_the_autosave():
    SlotStore().autosave(make(125.0))
    menu = MenuScene()
    cont = menu.buttons["Continue"]
    assert cont.label == "Continue (02:05)" and cont.rect.bottom <= menu.play.rect.top
    click(menu, cont.rect.center)
    loaded = take(menu)
    assert isinstance(loaded, GameScene) and loaded.game_t == 125.0
    assert [e.text for e in loaded.equations.entries][:2] == ["eq1: y = a*x", "y = sin(x)"]


def test_corrupt_autosave_is_dropped_by_continue():
    SlotStore().autosave(make())
    menu = MenuScene()
    (config.SLOTS_PATH / "autosave.json").write_text("{broken", encoding="utf-8")
    click(menu, menu.buttons["Continue"].rect.center)
    assert menu.next_scene is None and "Continue" not in menu.buttons
    assert not SlotStore().has_autosave()


def test_menu_saves_button_opens_the_page_and_back_returns_to_a_menu():
    menu = MenuScene()
    click(menu, menu.buttons["Saves"].rect.center)
    page = take(menu)
    assert isinstance(page, SavesScene) and page.game is None
    key(page, pygame.K_ESCAPE)
    assert isinstance(take(page), MenuScene)


def test_open_page_saves():
    g = make()
    page = open_page("saves", lambda: g, game=g)
    assert isinstance(page, SavesScene) and page.game is g and open_page("nope", lambda: g) is None


# --- pause ---------------------------------------------------------------------------------------------
def test_pause_saves_opens_the_page_and_back_returns_the_same_paused_game():
    g = make()
    g.paused = True
    click(g, g.saves_btn.rect.center)
    page = take(g)
    assert isinstance(page, SavesScene) and page.game is g
    page.draw(pygame.display.get_surface())
    click(page, page.back_btn.rect.center)
    assert take(page) is g and g.paused


def test_save_from_pause_then_load_it():
    g = make(40.0)
    g.paused = True
    click(g, g.saves_btn.rect.center)
    page = take(g)
    click(page, page.card_parts(0)["save"].center)
    assert SlotStore().list()[0].game_t == 40.0
    click(page, page.card_parts(0)["thumb"].center)           # asks first
    click(page, page.dialog_rects["ok"].center)
    assert isinstance(take(page), GameScene)


def test_pause_settings_still_returns_to_the_game():
    g = make()
    g.paused = True
    click(g, g.settings_btn.rect.center)
    page = take(g)
    assert isinstance(page, SettingsScene)
    assert page.back() is g


def test_main_menu_from_pause_autosaves_and_continue_appears():
    g = make(77.0)
    g.paused = True
    click(g, g.menu_btn.rect.center)
    menu = take(g)
    assert isinstance(menu, MenuScene) and menu.buttons["Continue"].label == "Continue (01:17)"
    assert SlotStore().autosave_info().game_t == 77.0


def test_autosave_every_sixty_seconds_of_play_not_while_paused():
    g = make(10.0)
    store = SlotStore()
    g.update(config.MAX_DT)
    assert not store.has_autosave()
    g.paused = True
    g.update(config.AUTOSAVE_PERIOD + 1)
    assert not store.has_autosave()
    g.paused = False
    g._autosave_t = config.AUTOSAVE_PERIOD - 0.01
    g.update(0.02)
    assert store.has_autosave() and g._autosave_t < 1.0
    assert store.autosave_info().game_t == pytest.approx(g.game_t, abs=0.1)


def test_new_run_does_not_autosave_and_game_over_deletes_it():
    g = GameScene(seed=1, profile=Profile.in_memory())
    assert not g.autosave() and not SlotStore().has_autosave()          # nothing to continue at 00:00
    g.game_t = 30.0
    assert g.autosave() and SlotStore().has_autosave()
    g.player.hp = 0.0
    g.update(0.016)
    assert isinstance(g.next_scene, GameOverScene) and not SlotStore().has_autosave()


def test_window_close_autosaves_the_live_run_only():
    g = make(55.0)
    assert track_game(None, g) is g
    assert track_game(g, SettingsScene(lambda: g)) is g                # a page opened from pause keeps it
    assert track_game(g, MenuScene()) is None and track_game(g, GameOverScene(1.0, 0)) is None
    assert autosave_live(None) is False and not SlotStore().has_autosave()
    assert autosave_live(g) and SlotStore().autosave_info().game_t == 55.0
    SlotStore().delete_autosave()
    g.player.hp = 0.0
    assert autosave_live(g) is False and not SlotStore().has_autosave()


# --- speed ---------------------------------------------------------------------------------------------
def test_speed_is_saved_and_restored():
    g = make()
    g.speed = 3
    data = snapshot(g)
    assert data["speed"] == 3
    g2 = restore(data, profile=Profile.in_memory())
    assert g2.speed == 3 and isinstance(g2.speed, int)


# --- undo toast and Ctrl+Z ---------------------------------------------------------------------------
def del_row(g, i):
    click(g, g.sidebar.rects(i)["delete"].center)


def test_del_shows_the_toast_with_the_name_and_clicking_undo_restores():
    g = make()
    del_row(g, 0)
    assert [e.text for e in g.equations.entries] == ["y = sin(x)"]
    assert g.undo_toast.active and g.undo_toast.name == "eq1"
    g.draw(pygame.display.get_surface())
    click(g, g.undo_toast.undo_rect.center)
    assert [e.text for e in g.equations.entries] == ["eq1: y = a*x", "y = sin(x)"]
    assert not g.undo_toast.active


def test_unnamed_equation_is_shown_by_its_text():
    g = make()
    del_row(g, 1)
    assert g.undo_toast.name == "y = sin(x)"


def test_toast_lasts_five_seconds():
    g = make()
    del_row(g, 0)
    g.update(4.9)
    assert g.undo_toast.active
    g.update(0.2)
    assert not g.undo_toast.active


def test_ctrl_z_restores_unless_a_text_field_is_focused():
    g = make()
    del_row(g, 0)
    g.input.focused = True
    key(g, pygame.K_z, pygame.KMOD_CTRL)
    assert len(g.equations.entries) == 1 and g.equations.can_undo
    g.input.focused = False
    key(g, pygame.K_z, 0)                                              # plain Z does nothing
    assert len(g.equations.entries) == 1
    key(g, pygame.K_z, pygame.KMOD_CTRL)
    assert [e.text for e in g.equations.entries][0] == "eq1: y = a*x" and not g.undo_toast.active


def test_ctrl_z_does_nothing_when_nothing_was_deleted():
    g = make()
    key(g, pygame.K_z, pygame.KMOD_CTRL)
    assert len(g.equations.entries) == 2 and not g.undo_toast.active


def test_undo_keeps_the_edit_index_on_its_equation():
    g = make()
    g.equations.add("y = cos(x)")
    g.input.set_text("y = cos(x)", 2)
    del_row(g, 0)
    g.input.edit_index = 1                                             # the row moved up when row 0 went
    assert g.undo()
    assert g.input.edit_index == 2 and g.equations.entries[2].text == "y = cos(x)"


def test_toast_survives_resize():
    g = make()
    del_row(g, 0)
    view.set_size(800, 600)
    pygame.display.set_mode((800, 600))
    g.on_resize()
    assert g.undo_toast.box.centerx == 400
    g.draw(pygame.display.get_surface())
