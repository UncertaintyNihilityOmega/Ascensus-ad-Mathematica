"""Upgrades (headless): costs, buying, Auto order, stats, XP accounting, max-HP heal, cooldown pulses."""
import numpy as np
import pytest

from ascensus import config
from ascensus.enemies import Swarm
from ascensus.formulas import FormulaManager, pulse_damage
from ascensus.player import Player
from ascensus.upgrades import Upgrades


def test_cost_growth_per_stat():
    u = Upgrades()
    assert [u.cost(s) for s in ("max_hp", "base_dmg", "cooldown")] == [20, 20, 20]
    u.add_xp(1000)
    for level in range(1, 8):
        assert u.buy("max_hp")
        assert u.cost("max_hp") == round(20 * 1.12 ** level)
    assert u.cost("base_dmg") == 20 and u.levels["max_hp"] == 7        # per-stat levels
    assert round(20 * 1.12) == 22


def test_buy_needs_xp_and_tracks_spending():
    u = Upgrades()
    u.add_xp(19.9)
    assert not u.affordable("max_hp") and not u.buy("max_hp") and u.spent == 0
    u.add_xp(0.1)
    assert u.buy("max_hp")
    assert u.xp == pytest.approx(0) and u.spent == 20 and u.earned == pytest.approx(20)
    assert u.max_hp == config.PLAYER_HP + 10 and u.label("max_hp") == "Max HP: 110 / 22 XP"
    assert u.label("base_dmg") == "Base DMG: 100 / 20 XP" and u.label("cooldown") == "Cooldown: 1.00s / 20 XP"


def test_stats_scale_and_cooldown_floor():
    u = Upgrades()
    u.levels["base_dmg"] = 3
    assert u.base_dmg == 130
    u.levels["cooldown"] = 1
    assert u.cooldown == pytest.approx(0.95)
    u.levels["cooldown"] = 500
    assert u.cooldown == config.COOLDOWN_MIN


def test_xp_accounting():
    u = Upgrades()
    assert u.kill_xp(40.0) == config.XP_PER_HP * 40.0 == 20.0
    u.add_xp(u.kill_xp(40.0))
    u.add_xp(u.kill_xp(20.0))
    assert u.xp == 30 and u.earned == 30 and u.spent == 0
    assert u.buy("base_dmg")
    assert u.xp == 10 and u.earned == 30 and u.spent == 20


def test_auto_buys_cheapest_first_with_ties_hp_dmg_cd():
    u = Upgrades()
    u.auto = True
    u.add_xp(60)                                   # three level-0 buys at 20 each
    assert u.auto_buy() == ["max_hp", "base_dmg", "cooldown"]
    assert u.xp == 0 and u.auto_buy() == []


def test_auto_order_by_cost():
    u = Upgrades()
    u.levels.update(max_hp=3, base_dmg=1, cooldown=2)
    assert (u.cost("max_hp"), u.cost("base_dmg"), u.cost("cooldown")) == (28, 22, 25)
    u.auto = True
    u.add_xp(22)
    assert u.auto_buy() == ["base_dmg"]
    u.add_xp(25)                                    # base_dmg is now 25 too: the tie goes to DMG
    assert u.auto_buy() == ["base_dmg"]
    u.add_xp(25)
    assert u.auto_buy() == ["cooldown"]


def test_auto_off_buys_nothing_and_stops_when_broke():
    u = Upgrades()
    u.add_xp(500)
    assert u.auto_buy() == []
    u.auto = True
    bought = u.auto_buy()
    assert len(bought) > 3 and not any(u.affordable(s) for s in u.levels)


def test_max_hp_buy_heals_and_caps():
    p = Player()
    p.hp = 50.0
    p.raise_max_hp(config.UPG_HP_STEP)
    assert p.max_hp == config.PLAYER_HP + 10 and p.hp == 60.0
    p.hp = p.max_hp
    p.raise_max_hp(10)
    assert p.hp == p.max_hp == config.PLAYER_HP + 20
    p.update(60.0, (0, 0))
    assert p.hp == p.max_hp                         # regen cap follows the stat


def test_pulse_period_is_the_cooldown_stat():
    m = FormulaManager()
    m.add("x = 0")
    sw = Swarm(np.random.default_rng(0))
    sw.spawn(np.zeros(2), 0.0)
    sw.pos = np.array([[0.0, 100.0]])               # on the line x = 0 (the player's x)
    sw.hp[:] = sw.max_hp[:] = 1e6
    t = 0.0
    for _ in range(100):                            # 1 s at 10 ms steps, cooldown 0.1 s
        t += 0.01
        m.update(0.01, t, sw, np.zeros(2), 100.0, 0.1)
    per_hit = pulse_damage(m.entries[0].curve.length_units, 100.0)
    hits = round((1e6 - sw.hp[0]) / per_hit)
    assert 8 <= hits <= 10                          # ~1 s / 0.1 s, not 1 pulse per second
