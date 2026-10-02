"""P19 speed button: cycle, substeps, per-run reset, layout next to the timer, Stats line."""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402
import pytest  # noqa: E402

from ascensus import config, settings, view  # noqa: E402
from ascensus.profile import Profile  # noqa: E402
from ascensus.scenes import GameScene  # noqa: E402
from ascensus.stats import build_stats  # noqa: E402
from ascensus.ui import widgets  # noqa: E402
from ascensus.ui.speed_button import SpeedButton, next_speed  # noqa: E402


@pytest.fixture(autouse=True)
def _env():
    pygame.init()
    pygame.display.set_mode((1280, 720))
    view.set_size(1280, 720)
    widgets._fonts.clear()
    widgets._text_cache.clear()
    settings.reset_all()
    yield
    settings.reset_all()


def make():
    g = GameScene(seed=1, profile=Profile.in_memory())
    g.player.hp = 1e9
    return g


def click(g, pos, button=1):
    g.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=button))


def test_next_speed_cycles_1_2_3_1():
    assert [next_speed(s) for s in (1, 2, 3)] == [2, 3, 1]
    assert next_speed(7) == 1


def test_click_cycles_speed_and_run_starts_at_1x():
    g = make()
    assert g.speed == 1 and isinstance(g.speed, int)
    for want in (2, 3, 1):
        click(g, g.speed_button.rect.center)
        assert g.speed == want
    click(g, g.speed_button.rect.center, button=3)            # right click does nothing
    assert g.speed == 1
    g.speed = 3
    assert make().speed == 1                                  # per run


def test_button_sits_right_of_the_timer_and_follows_resize():
    g = make()
    r = g.speed_button.rect
    timer_right = view.W // 2 + widgets.get_font(config.HUD_TIMER_FONT).size("00:00")[0] // 2
    assert r.left > timer_right and r.top >= 0 and r.right < view.W
    assert not r.colliderect(g.sidebar.panel_rect) and not r.colliderect(g.upgrade_panel.panel_rect)
    view.set_size(1920, 1080)
    pygame.display.set_mode((1920, 1080))
    g.on_resize()
    assert g.speed_button.rect.left > 960 and g.speed_button.rect.centerx > r.centerx
    g.draw(pygame.display.get_surface())


def test_button_fill_is_semi_transparent():
    sb = SpeedButton()
    bg = sb._background(False)
    assert bg.get_at((bg.get_width() // 2, bg.get_height() // 2)).a == config.SPEED_BTN_ALPHA


def test_game_time_scales_with_speed_and_typing():
    g = make()
    g.update(1 / 60)
    t1 = g.game_t
    g.speed = 3
    g.update(1 / 60)
    assert g.game_t - t1 == pytest.approx(3 / 60)
    g.input.focused = True
    t2 = g.game_t
    g.update(1 / 60)
    assert g.game_t - t2 == pytest.approx(3 / 60 * config.TYPING_TIME_SCALE)


def test_substeps_never_exceed_limit_and_sum_to_dt():
    g = make()
    g.speed = 3
    dts = []
    orig = g.swarm.update
    g.swarm.update = lambda dt, pos: (dts.append(dt), orig(dt, pos))[1]
    g.update(0.1)                                              # 0.3 s of game time
    assert len(dts) == 9 and max(dts) <= config.SIM_MAX_SUBSTEP + 1e-12
    assert sum(dts) == pytest.approx(0.3) and g.game_t == pytest.approx(0.3)
    dts.clear()
    g.speed = 1
    g.update(1 / 60)
    assert len(dts) == 1                                       # normal frames are a single step


def test_substep_count_is_capped():
    g = make()
    g.speed = 3
    n = []
    orig = g.swarm.update
    g.swarm.update = lambda dt, pos: (n.append(dt), orig(dt, pos))[1]
    g.update(10.0)
    assert len(n) == config.SIM_MAX_SUBSTEPS and g.game_t == pytest.approx(30.0)


def test_fast_play_does_not_tunnel_through_the_player():
    g = make()
    g.player.hp = 100.0
    g.speed = 3
    g.swarm.spawn(g.player.pos, 0.0)
    g.swarm.pos[0] = g.player.pos + (0.0, 200.0)
    g.swarm.speed[0] = 600.0
    g.update(0.2)                                              # 0.6 s of game time: 360 px of travel
    assert g.player.hp < 100.0                                 # the hit was registered on the way


def test_death_stops_the_substeps():
    g = make()
    g.speed = 3
    g.player.hp = 1.0
    g.swarm.spawn(g.player.pos, 0.0)
    g.swarm.pos[0] = g.player.pos
    g.update(0.1)
    assert not g.player.alive and g.next_scene is not None


def test_paused_game_does_not_advance():
    g = make()
    g.speed = 3
    g.paused = True
    g.update(0.1)
    assert g.game_t == 0.0


def test_stats_show_game_speed():
    g = make()
    g.speed = 2
    run = dict(dict(build_stats(g))["Run"])
    assert run["Game speed"] == "2x"
