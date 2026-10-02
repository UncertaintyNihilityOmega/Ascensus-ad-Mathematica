"""Swarm / difficulty / player tests (headless)."""
import numpy as np
import pytest

from ascensus import config, view
from ascensus.game.enemies import Spawner, Swarm, difficulty
from ascensus.game.player import Player


def test_difficulty_curve():
    assert difficulty(0) == (20.0, 8.0, 70.0, 1.0)
    hp, dmg, speed, interval = difficulty(120)
    assert hp == pytest.approx(26.0) and dmg == pytest.approx(9.6)
    assert speed == pytest.approx(74.2) and interval == pytest.approx(1 / 1.7)
    assert difficulty(10_000)[2] == config.ENEMY_SPEED_MAX
    assert difficulty(10_000)[3] == config.SPAWN_MIN_INTERVAL


def test_spawner_counts():
    s = Spawner()
    assert s.update(0.5, 0) == 0
    assert s.update(0.5, 0) == 1
    assert s.update(2.0, 0) == 2


def test_spawn_distance_and_cap():
    sw = Swarm(np.random.default_rng(1))
    p = np.array([100.0, -50.0])
    for _ in range(config.ENEMY_MAX_ALIVE + 10):
        sw.spawn(p, 0.0)
    assert len(sw) == config.ENEMY_MAX_ALIVE
    d = np.hypot(*(sw.pos - p).T)
    assert np.allclose(d, np.hypot(view.W, view.H) / 2 + config.ENEMY_SPAWN_MARGIN)


def test_chase_and_contact():
    sw = Swarm(np.random.default_rng(1))
    sw.spawn(np.zeros(2), 0.0)
    for _ in range(1000):
        sw.update(1 / 60, np.zeros(2))
    assert sw.contact_damage(np.zeros(2), config.PLAYER_RADIUS) == 8.0
    assert sw.contact_damage(np.array([500.0, 0]), config.PLAYER_RADIUS) == 0.0


def test_damage_where_and_remove_dead():
    sw = Swarm(np.random.default_rng(1))
    for _ in range(3):
        sw.spawn(np.zeros(2), 0.0)
    player = np.array([10.0, 20.0])
    # enemy 0 at screen (100, 100), 1 at (400, 300), 2 off-window
    sw.pos[:] = [[100, 100], [400, 300], [-5000, 0]]
    sw.pos += player - np.array([view.W / 2, view.H / 2])
    mask = np.zeros((90, 160), dtype=bool)
    mask[100 // 8, 100 // 8] = True
    assert sw.damage_where(mask, 25.0, player) == 1
    assert sw.hp[0] == -5 and sw.flash[0] == config.ENEMY_FLASH and sw.hp[1] == 20
    sw.max_hp[0] = 33.0
    assert sw.remove_dead() == 1 and len(sw) == 2 and len(sw.flash) == 2
    assert sw.last_removed_max_hp == 33.0
    assert sw.remove_dead() == 0 and sw.last_removed_max_hp == 0.0


def test_player_iframes_and_death():
    p = Player()
    assert p.take_damage(10) and p.hp == 90
    assert not p.take_damage(10) and p.hp == 90
    p.update(config.PLAYER_IFRAMES + 0.01, (0, 0))
    assert p.take_damage(200) and p.hp == 0 and not p.alive


def test_player_diagonal_is_normalized():
    p = Player()
    p.update(1.0, (1, 1))
    assert np.hypot(*p.pos) == pytest.approx(config.PLAYER_SPEED)


# ---- P8: collision, knockback, regen, dash, boss -------------------------------------------

ZERO = np.zeros(2)


def _swarm(*world_pts, seed=1):
    sw = Swarm(np.random.default_rng(seed))
    for _ in world_pts:
        sw.spawn(ZERO, 0.0)
    sw.pos = np.array(world_pts, float).reshape(-1, 2)
    return sw


def _min_gap(sw):
    """Smallest (distance - r_i - r_j) over all pairs (negative = overlap)."""
    d = sw.pos[:, None] - sw.pos[None]
    gap = np.hypot(d[..., 0], d[..., 1]) - (sw.radius[:, None] + sw.radius[None])
    np.fill_diagonal(gap, np.inf)
    return gap.min()


def test_enemies_do_not_overlap_after_separation():
    rng = np.random.default_rng(5)
    sw = _swarm(*(rng.uniform(300, 360, (30, 2))))        # a dense blob, far from the player
    sw.speed[:] = 0
    for _ in range(40):
        sw.update(1 / 60, ZERO)
    assert _min_gap(sw) > -1.0
    assert len(sw.radius) == 30 and np.all(sw.radius == config.ENEMY_RADIUS)


def test_separation_mass_weighted_and_coincident():
    sw = _swarm((300, 0), (300, 0))                          # exactly coincident: no NaN
    sw.speed[:] = 0
    sw.update(1 / 60, ZERO)
    assert np.isfinite(sw.pos).all() and _min_gap(sw) > -1e-6
    sw = _swarm((300, 0), (300, 30))                         # boss (heavy) barely moves
    sw.boss[1] = True
    sw.radius[1] = config.BOSS_RADIUS
    sw.speed[:] = 0
    before = sw.pos.copy()
    sw.update(1 / 60, ZERO)
    assert np.linalg.norm(sw.pos[1] - before[1]) < 0.15 * np.linalg.norm(sw.pos[0] - before[0])
    assert _min_gap(sw) > -1e-6


def test_enemies_pushed_out_of_player_never_vice_versa():
    sw = _swarm((5, 0), (0, -3), (0, 0))
    sw.speed[:] = 0
    p = ZERO.copy()
    sw.update(1 / 60, p)
    d = np.hypot(*(sw.pos - p).T)
    assert np.all(d >= config.PLAYER_RADIUS + config.ENEMY_RADIUS - 1e-6)
    assert np.all(p == 0)
    # a normal chase settles exactly touching, which counts as contact (slop)
    assert sw.contact_damage(p, config.PLAYER_RADIUS) > 0


def test_contact_slop():
    reach = config.PLAYER_RADIUS + config.ENEMY_RADIUS
    sw = _swarm((reach + config.CONTACT_SLOP - 0.1, 0))
    assert sw.contact_damage(ZERO, config.PLAYER_RADIUS) > 0
    sw = _swarm((reach + config.CONTACT_SLOP + 0.5, 0))
    assert sw.contact_damage(ZERO, config.PLAYER_RADIUS) == 0


def test_knockback_moves_only_touching_enemies_away():
    reach = config.PLAYER_RADIUS + config.ENEMY_RADIUS
    sw = _swarm((reach, 0), (0, reach + 1), (500, 0))
    assert sw.knockback(ZERO, config.PLAYER_RADIUS) == 2
    assert np.allclose(sw.pos[0], (reach + config.KNOCKBACK_DIST, 0))
    assert np.allclose(sw.pos[1], (0, reach + 1 + config.KNOCKBACK_DIST))
    assert np.allclose(sw.pos[2], (500, 0))


def test_regen_capped_at_max_hp():
    p = Player()
    p.hp = 50.0
    p.update(60.0, (0, 0))
    assert p.hp == pytest.approx(50.0 + config.PLAYER_REGEN_PER_MIN)
    p.update(600.0, (0, 0))
    assert p.hp == p.max_hp
    p.hp = 0.0                                   # the dead do not regenerate
    p.update(60.0, (0, 0))
    assert p.hp == 0.0


def test_dash_distance_direction_and_invulnerability():
    p = Player()
    p.update(0.01, (0, -1))                      # face up
    start = p.pos.copy()
    assert p.start_dash() and p.dash_count == 1
    assert not p.start_dash() and p.dash_count == 1        # no restart mid-dash
    assert p.dashing and not p.take_damage(10) and p.hp == config.PLAYER_HP
    steps = 0
    while p.dashing:
        p.update(1 / 60, (0, 0))                  # no input needed: dash uses the facing direction
        steps += 1
        assert steps < 100
    moved = p.pos - start
    assert np.allclose(moved, (0, -config.DASH_DIST))
    assert p.take_damage(10)                      # vulnerable again
    assert p.start_dash() and p.dash_count == 2   # DASH_COOLDOWN is 0


def test_dash_defaults_to_facing_right():
    p = Player()
    p.start_dash()
    while p.dashing:
        p.update(1 / 60, (0, 0))
    assert np.allclose(p.pos, (config.DASH_DIST, 0))


def test_boss_spawn_timing_and_cap_exemption():
    sp = Spawner()
    assert sp.bosses_due(config.BOSS_INTERVAL - 0.01) == 0
    assert sp.bosses_due(config.BOSS_INTERVAL) == 1
    assert sp.bosses_due(config.BOSS_INTERVAL + 1) == 0
    assert sp.bosses_due(2 * config.BOSS_INTERVAL) == 1
    sw = Swarm(np.random.default_rng(1))
    for _ in range(config.ENEMY_MAX_ALIVE):
        sw.spawn(ZERO, 0.0)
    sw.spawn_boss(ZERO, 0.0)
    assert len(sw) == config.ENEMY_MAX_ALIVE + 1 and sw.normal_count() == config.ENEMY_MAX_ALIVE
    assert not sw.spawn(ZERO, 0.0)               # still capped; boss does not free a slot
    i = int(np.flatnonzero(sw.boss)[0])
    hp, dmg, speed, _ = difficulty(0.0)
    assert sw.hp[i] == hp * config.BOSS_HP_MULT and sw.dmg[i] == dmg * config.BOSS_DMG_MULT
    assert sw.speed[i] == pytest.approx(speed * config.BOSS_SPEED_MULT)
    assert sw.radius[i] == config.BOSS_RADIUS == 40


def test_boss_hit_test_uses_bounding_box():
    sw = Swarm(np.random.default_rng(1))
    sw.spawn_boss(ZERO, 0.0)
    sw.pos[0] = (view.W / 2 + 200 - view.W / 2, 0.0)         # boss centre at screen (view.W/2+200, view.H/2)
    cx, cy = int(view.W / 2 + 200), int(view.H / 2)
    rows, cols = -(-view.H // config.HIT_CELL), -(-view.W // config.HIT_CELL)
    mask = np.zeros((rows, cols), dtype=bool)
    mask[cy // config.HIT_CELL, (cx + 35) // config.HIT_CELL] = True       # off-centre, inside the box
    assert sw.damage_where(mask, 10.0, ZERO) == 1
    assert sw.hp[0] == config.ENEMY_HP_BASE * config.BOSS_HP_MULT - 10
    mask[:] = False
    mask[cy // config.HIT_CELL, (cx + 60) // config.HIT_CELL] = True       # outside the box
    assert sw.damage_where(mask, 10.0, ZERO) == 0
