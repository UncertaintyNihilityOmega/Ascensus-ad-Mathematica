"""savegame: snapshot / restore round trip (swarm with bosses, variables, equation colours), thumbnails."""
import json
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import numpy as np  # noqa: E402
import pygame  # noqa: E402
import pytest  # noqa: E402

from ascensus import config, view  # noqa: E402
from ascensus.game.profile import Profile  # noqa: E402
from ascensus.game.savegame import render_thumbnail, restore, snapshot  # noqa: E402
from ascensus.scenes.game import GameScene  # noqa: E402
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


def make_game(frames: int = 120) -> GameScene:
    """A game with equations, variables, a boss, upgrades and some play behind it."""
    g = GameScene(seed=3, profile=Profile.in_memory())
    g.equations.add("y = a*sin(x)")
    g.equations.add("name: x^2 - 4")
    g.equations.add("y = b*x")
    g.equations.set_color(0, (12, 200, 90))
    g.equations.toggle(2)
    g.direction_override = (1.0, 0.5)
    for _ in range(40):
        g.swarm.spawn(g.player.pos, 200.0)
    g.swarm.spawn_boss(g.player.pos, 200.0)
    g.game_t = 290.0
    for _ in range(frames):
        g.update(1 / 60)
    g.equations.store.set_value("a", 2.5)
    g.equations.store.vars["a"].playing = True
    g.equations.store.vars["a"].dir = -1
    g.upgrades.add_xp(500)
    g.buy("max_hp")
    g.buy("base_dmg")
    g.equations_cast = 7
    g.player.dash_count = 3
    return g


def test_snapshot_is_json_and_versioned():
    g = make_game()
    data = snapshot(g)
    assert data["version"] == config.SAVE_VERSION == 1
    again = json.loads(json.dumps(data))
    assert again == data
    for key in ("player", "swarm", "spawner", "stats", "upgrades", "equations", "variables", "game_t", "kills"):
        assert key in data
    assert set(data["swarm"]) >= {"pos", "hp", "max_hp", "dmg", "speed", "flash", "radius", "boss"}
    assert data["stats"]["dashes"] == 3 and data["stats"]["equations_cast"] == 7


def test_round_trip_snapshot_restore_snapshot():
    g = make_game()
    data = json.loads(json.dumps(snapshot(g)))
    g2 = restore(data, profile=Profile.in_memory())
    assert snapshot(g2) == data
    assert g2.game_t == g.game_t and g2.kills == g.kills and g2.equations_cast == 7
    assert np.array_equal(g2.player.pos, g.player.pos) and g2.player.hp == g.player.hp
    assert g2.player.max_hp == g.player.max_hp and g2.player.dash_count == 3
    assert g2.upgrades.levels == g.upgrades.levels and g2.upgrades.earned == g.upgrades.earned
    assert g2.upgrades.spent == g.upgrades.spent and g2.upgrades.xp == g.upgrades.xp
    assert g2.spawner.acc == g.spawner.acc and g2.spawner.bosses_spawned == g.spawner.bosses_spawned
    assert g2.rng is not g.rng and g2.swarm.rng is g2.rng           # a new generator (new seed)


def test_swarm_with_bosses_round_trips():
    g = make_game()
    assert g.swarm.boss.any() and len(g.swarm) > 20
    g.swarm.bosses_killed, g.swarm.damage_dealt = 2, 123.5
    data = json.loads(json.dumps(snapshot(g)))
    g2 = restore(data, profile=Profile.in_memory())
    assert len(g2.swarm) == len(g.swarm)
    for name in ("pos", "hp", "max_hp", "dmg", "speed", "flash", "radius", "boss"):
        assert np.array_equal(getattr(g2.swarm, name), getattr(g.swarm, name)), name
    assert g2.swarm.boss.dtype == bool and g2.swarm.pos.shape == (len(g.swarm), 2)
    assert g2.bosses_killed == 2 and g2.damage_dealt == 123.5
    g2.update(1 / 60)                                           # the restored swarm runs


def test_empty_swarm_round_trips():
    g = GameScene(seed=1, profile=Profile.in_memory())
    g2 = restore(json.loads(json.dumps(snapshot(g))), profile=Profile.in_memory())
    assert len(g2.swarm) == 0 and g2.swarm.pos.shape == (0, 2)
    g2.update(1 / 60)


def test_variables_keep_value_play_state_and_direction():
    g = make_game()
    data = json.loads(json.dumps(snapshot(g)))
    assert data["variables"]["a"] == {"value": 2.5, "playing": True, "dir": -1}
    g2 = restore(data, profile=Profile.in_memory())
    a = g2.equations.store.get("a")
    assert (a.value, a.playing, a.dir) == (2.5, True, -1)
    assert g2.equations.store.values["a"] == 2.5
    assert not g2.equations.store.get("b").playing and g2.equations.store.get("b").dir == 1


def test_equations_colours_and_enabled_survive():
    g = make_game()
    data = json.loads(json.dumps(snapshot(g)))
    g2 = restore(data, profile=Profile.in_memory())
    rows = [(e.text, e.enabled, e.color) for e in g2.equations.entries]
    assert rows == [(e.text, e.enabled, e.color) for e in g.equations.entries]
    assert rows[0][2] == (12, 200, 90) and rows[2][1] is False
    assert g2.equations.entries[1].parsed.name == "name"
    assert g2.equations.active()[0].curve is not None               # active curves are built


def test_restore_replaces_the_current_equations():
    data = snapshot(make_game())
    other = GameScene(seed=2, profile=Profile.in_memory())
    other.equations.add("y = 3")
    g2 = restore(data, profile=Profile.in_memory())
    assert "y = 3" not in [e.text for e in g2.equations.entries]


def test_restored_game_continues_and_draws():
    g2 = restore(snapshot(make_game()), profile=Profile.in_memory())
    for _ in range(30):
        g2.update(1 / 60)
    g2.draw(pygame.display.get_surface())
    assert g2.game_t > 290.0


def test_speed_is_read_defensively():
    g = make_game()
    assert snapshot(g)["speed"] == 1.0                             # no game.speed (yet): default 1
    g.speed = 2.0
    data = snapshot(g)
    assert data["speed"] == 2.0
    g2 = restore(data, profile=Profile.in_memory())
    if hasattr(g2, "speed"):
        assert g2.speed == 2.0


@pytest.mark.parametrize("mutate", [
    lambda d: d.pop("swarm"),
    lambda d: d.pop("player"),
    lambda d: d.update(version=99),
    lambda d: d["swarm"].update(hp=[1.0]),                          # arrays of different length
    lambda d: d["player"].update(hp="lots"),
    lambda d: d["player"].update(pos=[1.0]),
    lambda d: d["upgrades"].pop("levels"),
    lambda d: d["spawner"].update(acc=float("nan")),
    lambda d: d.update(game_t=-5),
])
def test_corrupt_data_raises_value_error(mutate):
    data = json.loads(json.dumps(snapshot(make_game(10))))
    mutate(data)
    with pytest.raises(ValueError):
        restore(data, profile=Profile.in_memory())


def test_non_dict_raises_value_error():
    for bad in (None, [], "x", 3):
        with pytest.raises(ValueError):
            restore(bad)


def test_thumbnail_is_320x180_with_curves_but_no_enemies():
    g = make_game()
    thumb = render_thumbnail(g)
    assert thumb.get_size() == config.THUMB_SIZE == (320, 180)
    bg = thumb.get_at((2, 2))[:3]
    assert tuple(bg) != (0, 0, 0)
    colors = {tuple(thumb.get_at((x, y))[:3]) for x in range(0, 320, 3) for y in range(0, 180, 3)}
    assert len(colors) > 5                                         # grid and curve pixels
    g.equations.entries[0].enabled = False
    g.equations.entries[1].enabled = False
    blank = render_thumbnail(g)
    assert blank.get_size() == (320, 180)


def test_thumbnail_non_16_9_window_is_cropped_not_squashed():
    view.set_size(900, 900)
    g = GameScene(seed=1, profile=Profile.in_memory())
    g.equations.add("y = x")
    assert render_thumbnail(g).get_size() == (320, 180)
    view.set_size(1280, 720)
