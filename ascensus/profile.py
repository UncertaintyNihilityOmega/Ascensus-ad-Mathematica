"""Persistent player profile: best run, lifetime counters and achievements (save/profile.json). No pygame."""
from __future__ import annotations

import datetime
import json
from pathlib import Path

from . import config


class Profile:
    """Best time / kills, lifetime counters and {achievement id: unlock date}. Loading never raises."""

    def __init__(self, path: Path | str | None = None) -> None:
        self.path: Path | None = Path(path) if path is not None else Path(config.PROFILE_PATH)
        self.best_time = 0.0
        self.best_kills = 0
        self.lifetime: dict[str, int] = {"dashes": 0, "kills": 0}
        self.achievements: dict[str, str] = {}
        self.load()

    @classmethod
    def in_memory(cls) -> "Profile":
        """A profile that never touches the disk (tests, smoke)."""
        p = cls.__new__(cls)
        p.path = None
        p.best_time, p.best_kills = 0.0, 0
        p.lifetime = {"dashes": 0, "kills": 0}
        p.achievements = {}
        return p

    # -- persistence ---------------------------------------------------------------------------------
    def load(self) -> bool:
        """Read the file; on a missing or corrupt file keep defaults and return False."""
        if self.path is None:
            return False
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.best_time = max(float(data.get("best_time", 0.0)), 0.0)
            self.best_kills = max(int(data.get("best_kills", 0)), 0)
            life = data.get("lifetime", {})
            self.lifetime = {"dashes": 0, "kills": 0}
            for k, v in life.items():
                self.lifetime[str(k)] = max(int(v), 0)
            ach = data.get("achievements", {})
            self.achievements = {str(k): str(v) for k, v in ach.items()}
            return True
        except (OSError, ValueError, TypeError, AttributeError):
            self.best_time, self.best_kills = 0.0, 0
            self.lifetime = {"dashes": 0, "kills": 0}
            self.achievements = {}
            return False

    def save(self) -> bool:
        """Write the file (creating the folder); returns False if it cannot be written."""
        if self.path is None:
            return False
        data = {"best_time": self.best_time, "best_kills": self.best_kills,
                "lifetime": self.lifetime, "achievements": self.achievements}
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
            tmp.replace(self.path)
            return True
        except OSError:
            return False

    # -- updates -------------------------------------------------------------------------------------
    def record_run(self, time: float, kills: int) -> bool:
        """Update the bests (time and kills independently), save, return True if either improved."""
        improved = False
        if time > self.best_time:
            self.best_time, improved = float(time), True
        if kills > self.best_kills:
            self.best_kills, improved = int(kills), True
        self.save()
        return improved

    def add_lifetime(self, name: str, n: int = 1) -> int:
        """Add n to a lifetime counter (in memory; saved by record_run/unlock/save) and return the new total."""
        self.lifetime[name] = self.lifetime.get(name, 0) + int(n)
        return self.lifetime[name]

    def get_lifetime(self, name: str) -> int:
        return self.lifetime.get(name, 0)

    def unlock(self, ach_id: str) -> bool:
        """Record an unlock dated today and save; False if it was already unlocked."""
        if ach_id in self.achievements:
            return False
        self.achievements[ach_id] = datetime.date.today().isoformat()
        self.save()
        return True

    def is_unlocked(self, ach_id: str) -> bool:
        return ach_id in self.achievements

    def best_text(self) -> str:
        """Menu line: 'Best run: 07:32 · 154 kills' or 'Best run: --:--' if nothing recorded."""
        if self.best_time <= 0 and self.best_kills <= 0:
            return "Best run: --:--"
        m, s = divmod(int(self.best_time), 60)
        return f"Best run: {m:02d}:{s:02d} - {self.best_kills} kills"


_shared: Profile | None = None


def get_profile() -> Profile:
    """The one shared Profile (loaded from config.PROFILE_PATH on first use)."""
    global _shared
    if _shared is None:
        _shared = Profile()
    return _shared


def set_profile(profile: Profile | None) -> None:
    """Replace the shared profile (tests); None makes the next get_profile() reload from disk."""
    global _shared
    _shared = profile


_shared: Profile | None = None


def get_profile() -> Profile:
    """The one Profile shared by the menu, stats, achievements and the game (loaded lazily from
    config.PROFILE_PATH, which honours the ASCENSUS_PROFILE environment variable)."""
    global _shared
    if _shared is None:
        _shared = Profile()
    return _shared


def set_profile(profile: Profile | None) -> None:
    """Replace the shared profile (tests and smoke inject temporary ones; None reloads lazily)."""
    global _shared
    _shared = profile
