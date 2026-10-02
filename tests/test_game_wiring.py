"""GameScene -> AchievementTracker wiring: events, unlocks through real calls, toast queue timing."""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402
import pytest  # noqa: E402

from ascensus import config, view  # noqa: E402
from ascensus.profile import Profile, get_profile, set_profile  # noqa: E402
from ascensus.scenes import GameScene  # noqa: E402
from ascensus.ui import widgets  # noqa: E402


@pytest.fixture(autouse=True)
def _pg():
    pygame.init()
    pygame.display.set_mode((1280, 720))
    widgets._fonts.clear()
    widgets._text_cache.clear()
    view.set_size(1280, 720)
    yield
    set_profile(None)
    widgets._fonts.clear()
    widgets._text_cache.clear()
    pygame.quit()


def make(profile=None):
    return GameScene(seed=1, save_path=None, profile=profile or Profile.in_memory())


def key(scene, k):
    scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=k, mod=0, unicode=""))


def cast(scene, text):
    key(scene, pygame.K_RETURN)
    scene.handle_event(pygame.event.Event(pygame.TEXTINPUT, text=text))
    key(scene, pygame.K_RETURN)


def test_casting_sin_unlocks_hello_sine_and_shows_toast():
    sc = make()
    cast(sc, "y = sin(x)")
    assert sc.profile.is_unlocked("hello_sine") and not sc.profile.is_unlocked("co_star")
    assert sc.toast is None                                  # shown on the next update
    sc.update(0.016)
    assert sc.toast is not None and sc.toast[0] == "Achievement unlocked: Hello, Sine"
    sc.draw(pygame.display.get_surface())                    # drawing the toast must not raise


def test_toasts_queue_and_last_three_seconds():
    sc = make()
    cast(sc, "y = sin(x) + cos(x)")
    sc.update(0.016)
    assert sc.toast[0].endswith("Co-Star") and len(sc.tracker.pending) == 1
    sc.update(config.TOAST_TIME - 0.5)                       # still the first one
    assert sc.toast[0].endswith("Co-Star")
    sc.update(0.6)                                           # expired -> next in the queue
    assert sc.toast[0].endswith("Hello, Sine") and not sc.tracker.pending
    sc.update(config.TOAST_TIME + 0.1)
    assert sc.toast is None


def test_toast_keeps_counting_while_paused():
    sc = make()
    cast(sc, "y = sin(x)")
    sc.update(0.016)
    sc.paused = True
    sc.update(config.TOAST_TIME + 0.1)
    assert sc.toast is None


def test_tan_monster_and_full_circle_through_the_scene():
    sc = make()
    cast(sc, "tan(sqrt(x^2+y^2)) = y/x")
    cast(sc, "x^(2) + y^2 = 4")
    for ach in ("tangent", "rooted", "tan_monster", "full_circle"):
        assert sc.profile.is_unlocked(ach), ach


def test_kill_boss_kill_upgrade_dash_and_tick_events():
    sc = make()
    sc.equations.update = lambda *a, **k: 2                   # two enemies die this frame
    sc.swarm.last_removed_bosses = 1
    sc.update(0.016)
    assert sc.profile.is_unlocked("first_blood") and sc.profile.is_unlocked("giant_slayer")
    assert sc.tracker.run_kills == 2 and sc.profile.get_lifetime("kills") == 2
    assert sc.swarm.last_removed_bosses == 0
    sc.upgrades.xp = 10_000
    assert sc.buy("base_dmg") and sc.profile.is_unlocked("investor")
    sc.profile.lifetime["dashes"] = config.ACH_DASH_COUNT - 1
    key(sc, pygame.K_r)
    assert sc.profile.get_lifetime("dashes") == config.ACH_DASH_COUNT and sc.profile.is_unlocked("dash_addict")
    sc.game_t = config.ACH_SURVIVOR_TIME
    sc.update(0.016)
    assert sc.profile.is_unlocked("survivor") and not sc.profile.is_unlocked("marathon")


def test_full_house_with_six_active_equations():
    sc = make()
    for i in range(6):
        sc.equations.add(f"y = x + {i}")
    sc.update(0.016)
    assert sc.profile.is_unlocked("full_house")


def test_emit_is_a_noop_without_a_tracker_and_unlock_saves(tmp_path):
    sc = make()
    sc.tracker = None
    sc.emit("kill")
    sc.update(0.016)
    assert not sc.profile.achievements
    path = tmp_path / "profile.json"
    sc2 = make(Profile(path))
    cast(sc2, "y = sin(x)")
    assert "hello_sine" in path.read_text()


def test_shared_profile_accessor_and_injection(tmp_path):
    p = Profile(tmp_path / "p.json")
    set_profile(p)
    assert get_profile() is p
    assert GameScene(seed=1, save_path=None).profile is p


def test_variable_events_reach_the_tracker():
    sc = make()
    cast(sc, "y = a sin(x)")
    assert sc.profile.is_unlocked("variable_star") and not sc.profile.is_unlocked("autoplay")
    sc.equations.store.toggle_play("a")
    assert sc.profile.is_unlocked("autoplay")
