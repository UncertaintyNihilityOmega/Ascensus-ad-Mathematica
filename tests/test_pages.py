"""Stats data, the Settings page (synthetic events), and the menu / pause wiring."""
import json
import os
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402
import pytest  # noqa: E402

from ascensus import config, display, settings, view  # noqa: E402
from ascensus.pages import StatsScene, column_layout  # noqa: E402
from ascensus.profile import Profile, set_profile  # noqa: E402
from ascensus.scenes import QUIT, GameScene, MenuScene, open_page  # noqa: E402
from ascensus.settings_scene import SettingsScene, note_text  # noqa: E402
from ascensus.stats import build_stats, mmss, next_boss_in  # noqa: E402
from ascensus.ui import widgets  # noqa: E402


@pytest.fixture(autouse=True)
def _env():
    pygame.init()
    pygame.display.set_mode((1280, 720))
    view.set_size(1280, 720)
    widgets._fonts.clear()
    widgets._text_cache.clear()
    settings.reset_all()
    set_profile(Profile.in_memory())
    display.fullscreen = False
    yield
    settings.reset_all()
    set_profile(None)
    config.SETTINGS_PATH.unlink(missing_ok=True)


def click(scene, pos):
    scene.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1))


def key(scene, k):
    scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=k, mod=0, unicode=""))


def make_game():
    return GameScene(seed=1, save_path=None, profile=Profile.in_memory())


# -- stats -----------------------------------------------------------------------------------------------
def test_mmss_and_next_boss():
    assert mmss(0) == "00:00" and mmss(452.9) == "07:32" and mmss(3725) == "62:05"
    assert next_boss_in(0, 100.0) == config.BOSS_INTERVAL - 100.0
    assert next_boss_in(1, 100.0) == 2 * config.BOSS_INTERVAL - 100.0
    assert next_boss_in(0, 1e9) == 0.0


def fake_game(**over):
    from ascensus.upgrades import Upgrades
    up = Upgrades()
    up.add_xp(100)
    up.buy("max_hp")
    base = dict(game_t=125.0, kills=12, bosses_killed=1, damage_dealt=1234.7, equations_cast=3,
                upgrades=up, player=SimpleNamespace(hp=73.4, max_hp=110.0, dash_count=4),
                swarm=[0] * 7, spawner=SimpleNamespace(bosses_spawned=0),
                equations=SimpleNamespace(active=lambda: [1, 2], entries=[1, 2, 3, 4], variables={"a": 1}))
    base.update(over)
    return SimpleNamespace(**base)


def test_build_stats_groups_and_values():
    groups = dict(build_stats(fake_game()))
    assert list(groups) == ["Run", "Player", "Enemies now", "Equations"]
    run, player, enemies, eq = (dict(groups[k]) for k in groups)
    assert run["Time"] == "02:05" and run["Kills"] == "12" and run["Bosses killed"] == "1"
    assert run["XP now"] == "80" and run["XP earned"] == "100" and run["XP spent"] == "20"
    assert run["Dashes"] == "4" and run["Damage dealt"] == "1,234" and run["Equations cast"] == "3"
    assert player["HP"] == "73 / 110" and player["Base DMG"] == f"{config.BASE_DMG:.0f}"
    assert player["Max HP level"].startswith("1  (next ") and "Cooldown level" in player and "Speed" in player
    assert enemies["Alive"] == "7" and enemies["Next boss in"] == mmss(config.BOSS_INTERVAL - 125.0)
    assert set(enemies) >= {"HP", "Damage", "Speed", "Spawn every"}
    assert eq == {"Active": f"2 / {config.MAX_ACTIVE}", "Total": "4", "Variables": "1"}


def test_stats_on_a_real_game_and_counters():
    game = make_game()
    game.equations.add("x = 0")
    game.input.text = "y = x"
    game._submit()
    assert game.equations_cast == 1
    game.swarm.spawn_boss(game.player.pos, 0.0)
    game.swarm.pos[0] = game.player.pos
    game.swarm.hp[0] = 5.0
    mask = game.equations.entries[0].curve.hit_mask
    mask[:] = True
    game.swarm.damage_where(mask, 100.0, game.player.pos)
    assert game.swarm.remove_dead() == 1
    assert game.bosses_killed == 1 and game.damage_dealt == 5.0         # only the hp that existed counts
    stats = dict(dict(build_stats(game))["Run"])
    assert stats["Bosses killed"] == "1" and stats["Equations cast"] == "1"


def test_column_layout():
    assert column_layout(4, 1920)[0] == 4 and column_layout(4, 900)[0] == 2
    cols, w = column_layout(4, 1280)
    assert 24 + cols * (w + 24) <= 1280 + 24


def test_stats_scene_back():
    game = make_game()
    scene = StatsScene(game, lambda: game)
    scene.update(0.1)
    scene.draw(pygame.display.get_surface())
    click(scene, scene.back_btn.rect.center)
    assert scene.next_scene is game
    scene = StatsScene(game, lambda: game)
    key(scene, pygame.K_ESCAPE)
    assert scene.next_scene is game


# -- settings page -----------------------------------------------------------------------------------------
def test_note_text():
    s = settings.find("PLAYER_HP")
    assert note_text(s).endswith("(next run)")
    assert note_text(settings.find("UNIT_PX")) == "Pixels per math unit; rebuilds the curves"
    assert note_text(settings.find("FULLSCREEN_START")) != "" and "next run" not in note_text(settings.find("WINDOW_FRACTION"))


def test_tabs_rows_and_drawing():
    scene = SettingsScene(lambda: None)
    assert scene.tab_names == settings.tabs() and scene.tab == "Display"
    for name in scene.tab_names:
        scene.select_tab(name)
        scene.draw(pygame.display.get_surface())
        assert [s.key for s in scene.rows()] == [s.key for s in settings.settings_for(name)]


def test_buttons_field_toggle_and_reset():
    scene = SettingsScene(lambda: None)
    scene.draw(pygame.display.get_surface())
    r = scene.row_rects("UNIT_PX")
    click(scene, r["plus"].center)
    assert config.UNIT_PX == 55
    click(scene, r["minus"].center)
    click(scene, r["minus"].center)
    assert config.UNIT_PX == 45
    # type a value: click the field, type, Enter
    click(scene, scene.row_rects("UNIT_PX")["field"].center)
    assert scene.focused_key() == "UNIT_PX"
    scene.handle_event(pygame.event.Event(pygame.TEXTINPUT, text="80"))
    key(scene, pygame.K_RETURN)
    assert config.UNIT_PX == 80 and scene.focused_key() is None
    click(scene, scene.row_rects("UNIT_PX")["field"].center)           # out of range: clamped
    scene.handle_event(pygame.event.Event(pygame.TEXTINPUT, text="999"))
    key(scene, pygame.K_RETURN)
    assert config.UNIT_PX == 100
    # bool toggle switch
    before = config.SHOW_GRID_DEFAULT
    click(scene, scene.row_rects("SHOW_GRID_DEFAULT")["switch"].center)
    assert config.SHOW_GRID_DEFAULT is (not before)
    # per-row reset
    click(scene, scene.row_rects("SHOW_GRID_DEFAULT")["reset"].center)
    assert config.SHOW_GRID_DEFAULT is before
    click(scene, scene.row_rects("UNIT_PX")["reset"].center)
    assert config.UNIT_PX == settings.default("UNIT_PX")


def test_reset_tab_and_reset_all():
    scene = SettingsScene(lambda: None)
    settings.set_value("UNIT_PX", 70)
    settings.set_value("PLAYER_SPEED", 300)
    scene.select_tab("Player")
    click(scene, scene.reset_tab_btn.rect.center)
    assert config.PLAYER_SPEED == settings.default("PLAYER_SPEED") and config.UNIT_PX == 70
    settings.set_value("PLAYER_SPEED", 300)
    click(scene, scene.reset_all_btn.rect.center)
    assert settings.is_default("PLAYER_SPEED") and settings.is_default("UNIT_PX")


def test_escape_cancels_edit_then_leaves():
    left = []
    scene = SettingsScene(lambda: left.append(1) or "scene")
    click(scene, scene.row_rects("UNIT_PX")["field"].center)
    key(scene, pygame.K_ESCAPE)
    assert scene.focused_key() is None and scene.next_scene is None and not left
    key(scene, pygame.K_ESCAPE)
    assert scene.next_scene == "scene" and left
    scene = SettingsScene(lambda: "again")
    click(scene, scene.back_btn.rect.center)
    assert scene.next_scene == "again"


def test_scroll_on_hover_and_tab_resets_scroll():
    scene = SettingsScene(lambda: None)
    scene.select_tab("Enemies")
    assert scene.area.max_scroll > 0
    wheel = pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=-1, pos=scene.area.rect.center)
    scene.handle_event(wheel)
    assert scene.area.scroll == 3 * config.SCROLL_ROW_PX
    scene.handle_event(pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=-1, pos=(5, 5)))     # not hovering the rows
    assert scene.area.scroll == 3 * config.SCROLL_ROW_PX
    scene.select_tab("Display")
    assert scene.area.scroll == 0


def test_changes_are_saved_and_round_trip():
    scene = SettingsScene(lambda: None)
    click(scene, scene.row_rects("GRID_STEP")["plus"].center)
    data = json.loads(config.SETTINGS_PATH.read_text())
    assert data["values"] == {"GRID_STEP": 4}
    settings.reset_all()
    assert settings.apply_saved() == 1 and config.GRID_STEP == 4


def test_window_size_applies_live():
    display.fullscreen = False
    scene = SettingsScene(lambda: None)
    click(scene, scene.row_rects("WINDOW_FRACTION")["minus"].center)
    assert config.WINDOW_FRACTION == pytest.approx(0.80)
    assert not display.fullscreen and view.W == view.H == display.window_side()
    assert pygame.display.get_surface().get_size() == (view.W, view.H)
    assert scene.area.rect.right <= view.W


# -- menu and pause ------------------------------------------------------------------------------------------
def test_menu_buttons_and_best_run():
    menu = MenuScene()
    assert list(menu.buttons) == ["Play", "Settings", "Library", "Achievements", "Quit"]
    ys = [b.rect.centery for b in menu.buttons.values()]
    assert ys == sorted(ys) and menu.buttons["Quit"].rect.bottom < view.H
    menu.draw(pygame.display.get_surface())
    click(menu, menu.buttons["Settings"].rect.center)
    page = menu.next_scene
    assert isinstance(page, SettingsScene)
    key(page, pygame.K_ESCAPE)
    assert isinstance(page.next_scene, MenuScene)
    for name in ("Library", "Achievements"):                       # a missing page must not crash
        menu = MenuScene()
        click(menu, menu.buttons[name].rect.center)
    click(MenuScene(), (-5, -5))
    m = MenuScene()
    click(m, m.quit.rect.center)
    assert m.next_scene == QUIT


def test_open_page_unknown_is_none():
    assert open_page("nonsense", lambda: None) is None


def test_pause_menu_pages_return_to_the_same_game():
    game = make_game()
    key(game, pygame.K_ESCAPE)
    assert game.paused
    for btn, cls in ((game.settings_btn, SettingsScene), (game.stats_btn, StatsScene)):
        game.next_scene = None
        click(game, btn.rect.center)
        page = game.next_scene
        assert isinstance(page, cls)
        key(page, pygame.K_ESCAPE)
        assert page.next_scene is game and game.paused
    game.next_scene = None
    click(game, game.library_btn.rect.center)                      # exists or not: no crash
    assert game.next_scene is None or game.next_scene is not game


def test_zoom_change_from_pause_rebuilds_the_game():
    game = make_game()
    key(game, pygame.K_ESCAPE)
    n0 = len(game.grid_lines)
    click(game, game.settings_btn.rect.center)
    page = game.next_scene
    page.select_tab("Display")
    page.set_value("UNIT_PX", 25)
    key(page, pygame.K_ESCAPE)
    assert page.next_scene is game and len(game.grid_lines) > n0         # smaller units: more grid lines


def test_run_recorded_once_on_exit_to_menu_and_at_death():
    game = make_game()
    game.game_t, game.kills = 75.0, 12
    key(game, pygame.K_ESCAPE)
    click(game, game.menu_btn.rect.center)
    assert isinstance(game.next_scene, MenuScene)
    assert (game.profile.best_time, game.profile.best_kills) == (75.0, 12)
    game.game_t = 200.0
    game.finish_run()                                              # already recorded for this run
    assert game.profile.best_time == 75.0
    dead = make_game()
    dead.game_t, dead.kills = 30.0, 4
    dead.player.hp = 0.0
    dead.update(0.01)
    assert dead.profile.best_text() == "Best run: 00:30 - 4 kills"
