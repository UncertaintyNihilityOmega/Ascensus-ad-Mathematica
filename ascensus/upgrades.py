"""Per-run XP and upgrade stats (headless: no pygame). Everything resets with a new Upgrades()."""
from __future__ import annotations

import math

from . import config

# Cheapest-first tie-break order: HP, then DMG, then CD.
STATS = ("max_hp", "base_dmg", "cooldown")


class Upgrades:
    """XP wallet plus the three upgradable stats and their per-stat levels."""

    def __init__(self) -> None:
        self.levels: dict[str, int] = {s: 0 for s in STATS}
        self.xp = 0.0            # current, spendable
        self.earned = 0.0        # total ever earned this run
        self.spent = 0.0         # total ever spent this run
        self.auto = False

    # --- stats -----------------------------------------------------------
    @property
    def max_hp(self) -> float:
        return config.PLAYER_HP + config.UPG_HP_STEP * self.levels["max_hp"]

    @property
    def base_dmg(self) -> float:
        return config.BASE_DMG + config.UPG_DMG_STEP * self.levels["base_dmg"]

    @property
    def cooldown(self) -> float:
        """Seconds between pulses: PULSE_PERIOD * UPG_CD_MULT^level, never below COOLDOWN_MIN."""
        return max(config.COOLDOWN_MIN, config.PULSE_PERIOD * config.UPG_CD_MULT ** self.levels["cooldown"])

    # --- XP --------------------------------------------------------------
    def kill_xp(self, killed_max_hp: float) -> float:
        """XP for enemies whose max hp sums to `killed_max_hp` (does not add it)."""
        return config.XP_PER_HP * killed_max_hp

    def add_xp(self, amount: float) -> None:
        self.xp += amount
        self.earned += amount

    # --- buying ----------------------------------------------------------
    def cost(self, stat: str) -> int:
        return round(config.UPG_COST_BASE * config.UPG_COST_GROWTH ** self.levels[stat])

    def affordable(self, stat: str) -> bool:
        return self.xp >= self.cost(stat)

    def buy(self, stat: str) -> bool:
        """Buy one level of `stat` if affordable; returns True when bought."""
        if not self.affordable(stat):
            return False
        c = self.cost(stat)
        self.xp -= c
        self.spent += c
        self.levels[stat] += 1
        return True

    def cheapest_affordable(self) -> str | None:
        """Cheapest affordable stat (ties HP -> DMG -> CD), or None."""
        best: str | None = None
        for s in STATS:
            if self.affordable(s) and (best is None or self.cost(s) < self.cost(best)):
                best = s
        return best

    def auto_buy(self) -> list[str]:
        """With Auto on, buy cheapest-first until nothing is affordable; returns the stats bought."""
        bought: list[str] = []
        while self.auto:
            s = self.cheapest_affordable()
            if s is None or not self.buy(s):
                break
            bought.append(s)
        return bought

    # --- persistence -----------------------------------------------------
    def to_dict(self) -> dict:
        """Saved state: levels, XP wallet, earned/spent totals and the Auto flag."""
        return {"levels": dict(self.levels), "xp": self.xp, "earned": self.earned,
                "spent": self.spent, "auto": self.auto}

    def load_dict(self, data: dict) -> None:
        """Restore from to_dict(); raises ValueError / KeyError / TypeError on bad data (nothing changes then)."""
        levels = {s: int(data["levels"][s]) for s in STATS}
        xp, earned, spent = float(data["xp"]), float(data["earned"]), float(data["spent"])
        if min(levels.values()) < 0 or not all(math.isfinite(v) and v >= 0 for v in (xp, earned, spent)):
            raise ValueError("negative upgrade value")
        self.levels, self.xp, self.earned, self.spent = levels, xp, earned, spent
        self.auto = bool(data.get("auto", False))

    # --- labels ----------------------------------------------------------
    def label(self, stat: str) -> str:
        """Button text, e.g. 'Max HP: 110 / 22 XP'."""
        c = self.cost(stat)
        if stat == "max_hp":
            return f"Max HP: {self.max_hp:.0f} / {c} XP"
        if stat == "base_dmg":
            return f"Base DMG: {self.base_dmg:.0f} / {c} XP"
        return f"Cooldown: {self.cooldown:.2f}s / {c} XP"
