"""Data for the Stats page as a pure function: four column groups of (label, value) text."""
from __future__ import annotations

from . import config
from .enemies import difficulty
from .upgrades import STATS


def mmss(seconds: float) -> str:
    """mm:ss (minutes keep counting past 59)."""
    s = max(int(seconds), 0)
    return f"{s // 60:02d}:{s % 60:02d}"


def _count(x) -> int:
    try:
        return len(x)
    except TypeError:
        return 0


def next_boss_in(spawned: int, game_t: float) -> float:
    """Seconds of game time until the next boss spawns."""
    return max((spawned + 1) * config.BOSS_INTERVAL - game_t, 0.0)


def build_stats(game) -> list[tuple[str, list[tuple[str, str]]]]:
    """[(group title, [(label, value), ...]), ...] for Run / Player / Enemies now / Equations.

    `game` needs: game_t, kills, bosses_killed, damage_dealt, equations_cast, upgrades, player, swarm,
    spawner and equations (a GameScene, or any object with those attributes).
    """
    up, pl = game.upgrades, game.player
    hp, dmg, speed, interval = difficulty(game.game_t)
    names = {"max_hp": "Max HP", "base_dmg": "DMG", "cooldown": "Cooldown"}
    levels = [(f"{names[s]} level", f"{up.levels[s]}  (next {up.cost(s)} XP)") for s in STATS]
    run = [("Time", mmss(game.game_t)),
           ("Kills", str(game.kills)),
           ("Bosses killed", str(game.bosses_killed)),
           ("XP now", f"{up.xp:.0f}"),
           ("XP earned", f"{up.earned:.0f}"),
           ("XP spent", f"{up.spent:.0f}"),
           ("Dashes", str(pl.dash_count)),
           ("Damage dealt", f"{int(game.damage_dealt):,}"),
           ("Equations cast", str(game.equations_cast))]
    player = [("HP", f"{pl.hp:.0f} / {pl.max_hp:.0f}"),
              ("Regen", f"{config.PLAYER_REGEN_PER_MIN:g} / min"),
              ("Base DMG", f"{up.base_dmg:.0f}"),
              ("Cooldown", f"{up.cooldown:.2f} s"),
              *levels,
              ("Speed", f"{config.PLAYER_SPEED:g} px/s")]
    enemies = [("HP", f"{hp:.0f}"),
               ("Damage", f"{dmg:.1f}"),
               ("Speed", f"{speed:.0f} px/s"),
               ("Spawn every", f"{interval:.2f} s"),
               ("Alive", str(_count(game.swarm))),
               ("Next boss in", mmss(next_boss_in(game.spawner.bosses_spawned, game.game_t)))]
    equations = [("Active", f"{_count(game.equations.active())} / {config.MAX_ACTIVE}"),
                 ("Total", str(_count(game.equations.entries))),
                 ("Variables", str(_count(getattr(game.equations, "variables", ()))))]
    return [("Run", run), ("Player", player), ("Enemies now", enemies), ("Equations", equations)]
