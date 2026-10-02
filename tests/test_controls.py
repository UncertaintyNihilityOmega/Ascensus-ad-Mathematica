"""P19 controls: mouse/WASD movement, dash key and right-click, mouse-over-UI, Controls settings tab."""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import numpy as np  # noqa: E402
import pygame  # noqa: E402
import pytest  # noqa: E402

from ascensus import config, controls, settings, view  # noqa: E402
from ascensus.profile import Profile  # noqa: E402
from ascensus.scenes import GameScene  # noqa: E402
from ascensus.settings_scene import SettingsScene  # noqa: E402
from ascensus.ui import widgets  # noqa: E402
from ascensus.ui.keyfield import KeyField  # noqa: E402

DT = 1 / 60
CX, CY = 640, 360


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    pygame.init()
    pygame.display.set_mode((1280, 720))
    view.set_size(1280, 720)
    widgets._fonts.clear()
    widgets._text_cache.clear()
    settings.reset_all()
    monkeypatch.setattr(controls, "window_active", lambda: True)
    yield
    settings.reset_all()
    config.SETTINGS_PATH.unlink(missing_ok=True)


@pytest.fixture
def cursor(monkeypatch):
    pos = [CX, CY]
    monkeypatch.setattr(controls, "mouse_pos", lambda: tuple(pos))
    return pos


def game_in_mouse_mode():
    settings.set_value("MOVE_MODE", "Mouse")
    game = GameScene(seed=1, profile=Profile.in_memory())
    game.player.hp = 1e9
    return game


def run(game, frames):
    for _ in range(frames):
        game.update(DT)


def ev(kind, **kw):
    return pygame.event.Event(kind, **kw)


# -- pure helpers -----------------------------------------------------------------------------------------
def test_mouse_direction_dead_zone_and_unit_vector():
    assert controls.mouse_direction((CX + 5, CY)) == (0.0, 0.0)                 # inside the default dead zone
    assert controls.mouse_direction((CX + config.MOUSE_DEAD_ZONE, CY)) == (0.0, 0.0)
    dx, dy = controls.mouse_direction((CX + 300, CY + 400))
    assert (dx, dy) == pytest.approx((0.6, 0.8))
    assert controls.mouse_direction((CX + 30, CY), dead_zone=40) == (0.0, 0.0)
    assert controls.aim((CX, CY)) == (0.0, 0.0)
    assert controls.aim((CX - 7, CY)) == pytest.approx((-1.0, 0.0))


def test_default_dead_zone_is_player_radius():
    assert config.MOUSE_DEAD_ZONE == config.PLAYER_RADIUS and config.MOVE_MODE == "WASD"
    assert config.DASH_KEY == "j"


def test_keys_direction():
    class Keys(dict):
        def __missing__(self, k):
            return False
    assert controls.keys_direction(Keys({pygame.K_d: True, pygame.K_w: True})) == (1.0, -1.0)
    assert controls.keys_direction(Keys({pygame.K_LEFT: True, pygame.K_DOWN: True})) == (-1.0, 1.0)
    assert controls.keys_direction(Keys()) == (0.0, 0.0)


def test_dash_key_code_and_fallback():
    assert controls.dash_key_code() == pygame.K_j and controls.dash_key_label() == "J"
    config.DASH_KEY = "space"
    assert controls.dash_key_code() == pygame.K_SPACE
    config.DASH_KEY = "not a key"
    assert controls.dash_key_code() == pygame.K_j


def test_is_dash_event_modes():
    key_j = ev(pygame.KEYDOWN, key=pygame.K_j, mod=0, unicode="j")
    key_r = ev(pygame.KEYDOWN, key=pygame.K_r, mod=0, unicode="r")
    right = ev(pygame.MOUSEBUTTONDOWN, pos=(10, 10), button=3)
    left = ev(pygame.MOUSEBUTTONDOWN, pos=(10, 10), button=1)
    assert controls.is_dash_event(key_j) and not controls.is_dash_event(key_r)
    assert not controls.is_dash_event(right)                       # WASD mode: no right-click dash
    config.MOVE_MODE = "Mouse"
    assert controls.is_dash_event(right) and not controls.is_dash_event(left) and controls.is_dash_event(key_j)


# -- GameScene -------------------------------------------------------------------------------------------
def test_mouse_mode_walks_toward_cursor_and_faces_it(cursor):
    game = game_in_mouse_mode()
    cursor[:] = [CX + 200, CY]
    p0 = game.player.pos.copy()
    run(game, 60)
    assert game.player.pos[0] - p0[0] == pytest.approx(config.PLAYER_SPEED, rel=0.01)
    assert game.player.pos[1] == pytest.approx(p0[1])
    cursor[:] = [CX, CY - 200]
    run(game, 1)
    assert tuple(game.player.facing) == pytest.approx((0.0, -1.0))


def test_mouse_mode_dead_zone_stands_still_but_faces(cursor):
    game = game_in_mouse_mode()
    cursor[:] = [CX - 8, CY]
    p0 = game.player.pos.copy()
    run(game, 30)
    assert np.allclose(game.player.pos, p0)
    assert tuple(game.player.facing) == pytest.approx((-1.0, 0.0))


def test_mouse_mode_no_move_over_ui_or_unfocused(cursor, monkeypatch):
    game = game_in_mouse_mode()
    game.update(DT)
    p0 = game.player.pos.copy()
    targets = {
        "sidebar": game.sidebar.panel_rect.center,
        "upgrades": game.upgrade_panel.panel_rect.center,
        "input": game.input.rect.center,
        "speed": game.speed_button.rect.center,
    }
    for name, pos in targets.items():
        cursor[:] = pos
        assert controls.mouse_over_ui(game, pos), name
        run(game, 10)
        assert np.allclose(game.player.pos, p0), name
    cursor[:] = [CX + 200, CY]                                       # free space: walks
    run(game, 10)
    assert game.player.pos[0] > p0[0] + 10
    p1 = game.player.pos.copy()
    monkeypatch.setattr(controls, "window_active", lambda: False)    # unfocused: stops
    run(game, 10)
    assert np.allclose(game.player.pos, p1)


def test_collapsed_sidebar_tab_blocks_but_panel_area_is_free(cursor):
    game = game_in_mouse_mode()
    game.sidebar.collapsed = True
    inside_old_panel = (game.sidebar.tab_rect.right + 40, 300)
    assert not controls.mouse_over_ui(game, inside_old_panel)
    assert controls.mouse_over_ui(game, game.sidebar.tab_rect.center)


def test_mouse_mode_ignores_wasd_and_typing_stops_movement(cursor):
    game = game_in_mouse_mode()
    cursor[:] = [CX + 200, CY]
    game.input.focused = True
    p0 = game.player.pos.copy()
    run(game, 10)
    assert np.allclose(game.player.pos, p0)


def test_right_click_dashes_toward_cursor(cursor):
    game = game_in_mouse_mode()
    pos = (CX, CY + 250)
    cursor[:] = [CX, CY + 250]
    game.handle_event(ev(pygame.MOUSEBUTTONDOWN, pos=pos, button=3))
    assert game.player.dash_count == 1 and game.player.dashing
    p0 = game.player.pos.copy()
    while game.player.dashing:
        game.update(DT)
    d = game.player.pos - p0
    assert d[1] > 0 and abs(d[0]) < 1.0
    assert np.hypot(*d) == pytest.approx(config.DASH_DIST, abs=config.PLAYER_SPEED * DT * 2 + 1)


def test_right_click_over_ui_or_in_wasd_mode_does_not_dash(cursor):
    game = game_in_mouse_mode()
    game.handle_event(ev(pygame.MOUSEBUTTONDOWN, pos=game.speed_button.rect.center, button=3))
    game.handle_event(ev(pygame.MOUSEBUTTONDOWN, pos=game.sidebar.panel_rect.center, button=3))
    assert game.player.dash_count == 0
    settings.set_value("MOVE_MODE", "WASD")
    game.handle_event(ev(pygame.MOUSEBUTTONDOWN, pos=(CX + 100, CY), button=3))
    assert game.player.dash_count == 0


def test_dash_key_j_default_rebound_and_r_no_longer_dashes():
    game = GameScene(seed=1, profile=Profile.in_memory())
    game.handle_event(ev(pygame.KEYDOWN, key=pygame.K_r, mod=0, unicode="r"))
    assert game.player.dash_count == 0
    game.handle_event(ev(pygame.KEYDOWN, key=pygame.K_j, mod=0, unicode="j"))
    assert game.player.dash_count == 1
    while game.player.dashing:
        game.update(DT)
    settings.set_value("DASH_KEY", "space")
    game.handle_event(ev(pygame.KEYDOWN, key=pygame.K_j, mod=0, unicode="j"))
    assert game.player.dash_count == 1
    game.handle_event(ev(pygame.KEYDOWN, key=pygame.K_SPACE, mod=0, unicode=" "))
    assert game.player.dash_count == 2


def test_dash_key_ignored_while_typing():
    game = GameScene(seed=1, profile=Profile.in_memory())
    game.handle_event(ev(pygame.KEYDOWN, key=pygame.K_RETURN, mod=0, unicode=""))
    assert game.input.focused
    game.handle_event(ev(pygame.KEYDOWN, key=pygame.K_j, mod=0, unicode="j"))
    assert game.player.dash_count == 0


def test_wasd_mode_still_moves_with_direction_override():
    game = GameScene(seed=1, profile=Profile.in_memory())
    game.direction_override = (1.0, 0.0)
    run(game, 60)
    assert game.player.pos[0] == pytest.approx(config.PLAYER_SPEED, rel=0.01)


def test_player_face_ignored_mid_dash():
    from ascensus.player import Player
    p = Player()
    p.face((0, 3))
    assert tuple(p.facing) == pytest.approx((0, 1))
    p.start_dash()
    p.face((-1, 0))
    assert tuple(p.facing) == pytest.approx((0, 1))
    p.face((0, 0))


# -- settings: registry and Controls tab -----------------------------------------------------------------
def test_controls_tab_registry_and_round_trip(tmp_path):
    assert "Controls" in settings.tabs()
    keys = {s.key: s for s in settings.settings_for("Controls")}
    assert set(keys) == {"MOVE_MODE", "DASH_KEY", "MOUSE_DEAD_ZONE"}
    assert keys["MOVE_MODE"].kind == "choice" and keys["DASH_KEY"].kind == "key"
    settings.set_value("MOVE_MODE", "Mouse")
    settings.set_value("DASH_KEY", "Left Shift")
    settings.set_value("MOUSE_DEAD_ZONE", 30)
    assert config.DASH_KEY == "left shift"
    p = tmp_path / "s.json"
    assert settings.save(p)
    settings.reset_all()
    assert config.MOVE_MODE == "WASD" and config.DASH_KEY == "j"
    assert settings.apply_saved(p) == 3
    assert (config.MOVE_MODE, config.DASH_KEY, config.MOUSE_DEAD_ZONE) == ("Mouse", "left shift", 30)


def test_bad_control_values_are_rejected(tmp_path):
    for key, bad in (("MOVE_MODE", "Gamepad"), ("DASH_KEY", ""), ("DASH_KEY", 5), ("MOUSE_DEAD_ZONE", "x")):
        with pytest.raises(ValueError):
            settings.set_value(key, bad)
    assert settings.nudge("MOVE_MODE", +1) == "Mouse" and settings.nudge("MOVE_MODE", +1) == "WASD"
    assert settings.nudge("DASH_KEY", +1) == "j"


def test_keyfield_binds_cancels_and_rejects_reserved():
    kf = KeyField(pygame.Rect(0, 0, 100, 30), "j")
    key = lambda k: ev(pygame.KEYDOWN, key=k, mod=0, unicode="")   # noqa: E731
    assert kf.handle_event(key(pygame.K_k)) is None and not kf.listening     # not listening: ignored
    kf.handle_event(ev(pygame.MOUSEBUTTONDOWN, pos=(5, 5), button=1))
    assert kf.listening
    assert kf.handle_event(key(pygame.K_ESCAPE)) is None and not kf.listening and kf.name == "j"
    kf.handle_event(ev(pygame.MOUSEBUTTONDOWN, pos=(5, 5), button=1))
    assert kf.handle_event(key(pygame.K_g)) is None and kf.listening and kf.message     # reserved
    assert kf.handle_event(key(pygame.K_SPACE)) == "space" and not kf.listening and kf.name == "space"
    kf.handle_event(ev(pygame.MOUSEBUTTONDOWN, pos=(5, 5), button=1))
    kf.handle_event(ev(pygame.MOUSEBUTTONDOWN, pos=(500, 500), button=1))             # click elsewhere
    assert not kf.listening


def test_settings_scene_controls_tab_key_binding_and_choice():
    scene = SettingsScene(lambda: None)
    scene.select_tab("Controls")
    scene.draw(pygame.display.get_surface())
    r = scene.row_rects("DASH_KEY")["cycle"]
    scene.handle_event(ev(pygame.MOUSEBUTTONDOWN, pos=r.center, button=1))
    assert scene.listening_key() == "DASH_KEY"
    scene.handle_event(ev(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0, unicode=""))     # cancels, stays on page
    assert scene.listening_key() is None and scene.next_scene is None and config.DASH_KEY == "j"
    scene.handle_event(ev(pygame.MOUSEBUTTONDOWN, pos=r.center, button=1))
    scene.handle_event(ev(pygame.KEYDOWN, key=pygame.K_k, mod=0, unicode="k"))
    assert config.DASH_KEY == "k" and scene.listening_key() is None and scene.keyfields["DASH_KEY"].name == "k"
    scene.draw(pygame.display.get_surface())
    scene.handle_event(ev(pygame.MOUSEBUTTONDOWN, pos=scene.row_rects("MOVE_MODE")["cycle"].center, button=1))
    assert config.MOVE_MODE == "Mouse"
    scene.reset_one("DASH_KEY")
    assert config.DASH_KEY == "j" and scene.keyfields["DASH_KEY"].name == "j"
