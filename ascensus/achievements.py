"""The 40 achievements (data) and AchievementTracker, fed by game events. No pygame."""
from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass
from typing import Any

from . import config
from .eqmatch import matches
from .profile import Profile


@dataclass(frozen=True)
class Achievement:
    id: str
    name: str
    desc: str


ACHIEVEMENTS: tuple[Achievement, ...] = (
    Achievement("hello_sine", "Hello, Sine", "Cast an equation with sin"),
    Achievement("co_star", "Co-Star", "Cast an equation with cos"),
    Achievement("tangent", "Off on a Tangent", "Cast an equation with tan"),
    Achievement("full_circle", "Full Circle", "Cast an equation containing both x^2 and y^2"),
    Achievement("rooted", "Rooted", "Use sqrt or root"),
    Achievement("natural_talent", "Natural Talent", "Use ln"),
    Achievement("inverse_thinking", "Inverse Thinking", "Use an inverse trig function"),
    Achievement("hyperbole", "Hyperbole", "Use sinh, cosh or tanh"),
    Achievement("time_lord", "Time Lord", "Use t in an equation"),
    Achievement("variable_star", "Variable Star", "Create a variable"),
    Achievement("autoplay", "Autoplay", "Press play on a variable"),
    Achievement("full_house", "Full House", "Have 6 equations active at once"),
    Achievement("ocean", "Ocean", "Cast y/x = tan(sqrt(x^2+y^2)*a), with a variable a"),
    Achievement("first_blood", "First Blood", "Get your first kill"),
    Achievement("centurion", "Centurion", "Get 100 kills in one run"),
    Achievement("giant_slayer", "Giant Slayer", "Kill a boss"),
    Achievement("survivor", "Survivor", "Survive 5:00"),
    Achievement("marathon", "Marathon", "Survive 15:00"),
    Achievement("investor", "Investor", "Buy an upgrade"),
    Achievement("dash_addict", "Dash Addict", "Dash 100 times (lifetime)"),
    # equation shapes ("a" / "c" may be any variable; sides, order and scale do not matter)
    Achievement("sakuna", "Sakuna", "Cast 0 = sin(x*a)*sin(y*a), with a variable a"),
    Achievement("cosmic", "Cosmic", "Cast 200 = (x^5+y^5)^2"),
    Achievement("lily", "Lily", "Cast (x^2-abs(y)*6)(y^2-abs(x)*6) = 0"),
    Achievement("cross0", "Cross0", "Cast (abs(a)x^2-y^2)(x^2-abs(a)y^2) = 0"),
    Achievement("cross2", "Cross2", "Cast (x-a y)^(-2)+(y-a x)^(-2) = 10"),
    Achievement("aliens", "Aliens", "Cast 10(x^2-c y)^2(y^2-c x)^2 = (x^2-c y)^2+(y^2-c x)^2"),
    Achievement("circular", "Circular", "Cast cos(2x)+cos(2y) = 0.39a"),
    Achievement("fog", "Fog", "Cast mod(x^2+y^2, 2) = 0.5"),
    Achievement("love_is_endless", "Love is Endless", "Cast 1 = x^2+(y-sqrt(abs(x)))^2"),
    Achievement("heartbeat", "Heartbeat", "Cast (x^2+y^2-1)^3 = x^2 y^3"),
    Achievement("four_leaf", "Four Leaf", "Cast (x^2+y^2)^3 = 4x^2 y^2"),
    Achievement("infinity", "Infinity", "Cast (x^2+y^2)^2 = a(x^2-y^2), with a variable a"),
    # play
    Achievement("speed_demon", "Speed Demon", "Play 60 s of game time at 3x speed in one run"),
    Achievement("untouchable", "Untouchable", "Survive 2:00 without taking damage"),
    Achievement("eternity", "Eternity", "Survive 60:00"),
    Achievement("mathematician", "Mathematician", "Have 50 equations in the sidebar"),
    Achievement("rainbow", "Rainbow", "Have 6 active equations, all in different colors"),
    Achievement("second_thoughts", "Second Thoughts", "Undo a deleted equation"),
    Achievement("time_capsule", "Time Capsule", "Export a save"),
    Achievement("homecoming", "Homecoming", "Import a save"),
)
BY_ID: dict[str, Achievement] = {a.id: a for a in ACHIEVEMENTS}
TOTAL = len(ACHIEVEMENTS)

_INVERSE = ("asin", "acos", "atan", "acot", "asec", "acsc", "arcsin", "arccos", "arctan",
            "arccot", "arcsec", "arccsc")
# Equation-shape achievements: id -> pattern (see eqmatch: any variable names, sides, order and scale).
EQUATION_PATTERNS: dict[str, str] = {
    "ocean": "y/x = tan(sqrt(x^2+y^2)*a)",
    "sakuna": "0 = sin(x*a)*sin(y*a)",
    "cosmic": "200 = (x^5+y^5)^2",
    "lily": "(x^2-abs(y)*6)(y^2-abs(x)*6) = 0",
    "cross0": "(abs(a)x^2-y^2)(x^2-abs(a)y^2) = 0",
    "cross2": "(x-a y)^(-2)+(y-a x)^(-2) = 10",
    "aliens": "10(x^2-c y)^2(y^2-c x)^2 = (x^2-c y)^2+(y^2-c x)^2",
    "circular": "cos(2x)+cos(2y) = 0.39a",
    "fog": "mod(x^2+y^2, 2) = 0.5",
    "love_is_endless": "1 = x^2+(y-sqrt(abs(x)))^2",
    "heartbeat": "(x^2+y^2-1)^3 = x^2 y^3",
    "four_leaf": "(x^2+y^2)^3 = 4x^2 y^2",
    "infinity": "(x^2+y^2)^2 = a(x^2-y^2)",
}
_SQUARE_X = re.compile(r"(?<![a-z])x\*\*\(?2\)?(?![\d.])")
_SQUARE_Y = re.compile(r"(?<![a-z])y\*\*\(?2\)?(?![\d.])")
_T_VAR = re.compile(r"(?<![a-z])t(?![a-z])")


def _has_word(text: str, names: tuple[str, ...]) -> bool:
    """True if any name appears as a whole word in text (so 'sin' does not match 'sinh' or 'asin')."""
    return any(re.search(rf"(?<![a-z]){n}(?![a-z])", text) for n in names)


def equation_features(parsed: Any) -> set[str]:
    """Which achievement-relevant features a parsed equation uses. Tolerant of old/new ParsedEquation shapes:
    uses `funcs` / `variables` when present and always also scans the source and expr text."""
    source = str(getattr(parsed, "source", "") or "").lower()
    expr = str(getattr(parsed, "expr", "") or "").lower()
    text = f"{source} {expr}"
    funcs = {str(f).lower() for f in (getattr(parsed, "funcs", None) or ())}
    variables = {str(v).lower() for v in (getattr(parsed, "variables", None) or ())}

    def uses(*names: str) -> bool:
        return bool(funcs.intersection(names)) or _has_word(text, names)

    found: set[str] = set()
    if uses("sin"):
        found.add("hello_sine")
    if uses("cos"):
        found.add("co_star")
    if uses("tan"):
        found.add("tangent")
    sq = (source.replace("^", "**"), expr)
    if any(_SQUARE_X.search(s) for s in sq) and any(_SQUARE_Y.search(s) for s in sq):
        found.add("full_circle")
    if uses("sqrt", "root") or "√" in source:
        found.add("rooted")
    if uses("ln"):
        found.add("natural_talent")
    if uses(*_INVERSE):
        found.add("inverse_thinking")
    if uses("sinh", "cosh", "tanh"):
        found.add("hyperbole")
    if bool(getattr(parsed, "uses_t", False)) or "t" in variables or _T_VAR.search(expr) or _T_VAR.search(source):
        found.add("time_lord")
    if callable(getattr(parsed, "func", None)) and hasattr(parsed, "variables"):
        found.update(ach_id for ach_id, text in EQUATION_PATTERNS.items() if matches(parsed, text))
    return found


class AchievementTracker:
    """Receives game events, unlocks achievements on the profile and queues toasts for the UI."""

    def __init__(self, profile: Profile) -> None:
        self.profile = profile
        self.pending: deque[Achievement] = deque()   # newly unlocked, waiting to be shown as toasts
        self.reset_run()

    def reset_run(self) -> None:
        """Start of a new run (per-run counters only; lifetime counters live in the profile)."""
        self.run_kills = 0
        self.fast_time = 0.0                  # game seconds played at 3x this run (Speed Demon)
        self._last_t: float | None = None     # game_t of the previous tick

    def pop_toast(self) -> Achievement | None:
        """Next achievement waiting for a toast, or None."""
        return self.pending.popleft() if self.pending else None

    @staticmethod
    def toast_text(ach: Achievement) -> str:
        return f"Achievement unlocked: {ach.name}"

    def unlocked_count(self) -> int:
        return sum(1 for a in ACHIEVEMENTS if self.profile.is_unlocked(a.id))

    def _unlock(self, ach_id: str, out: list[Achievement]) -> None:
        if self.profile.unlock(ach_id):
            ach = BY_ID[ach_id]
            out.append(ach)
            self.pending.append(ach)

    def _tick(self, data: dict, out: list[Achievement]) -> None:
        """Per simulation step: time, speed, damage-free time, active / total equations."""
        if int(data.get("active_count", 0)) >= config.ACH_FULL_HOUSE:
            self._unlock("full_house", out)
        game_t = float(data.get("game_t", 0.0))
        if game_t >= config.ACH_SURVIVOR_TIME:
            self._unlock("survivor", out)
        if game_t >= config.ACH_MARATHON_TIME:
            self._unlock("marathon", out)
        if game_t >= config.ACH_ETERNITY_TIME:
            self._unlock("eternity", out)
        if self._last_t is not None and float(data.get("speed", 1)) >= 3:
            step = game_t - self._last_t
            if 0 < step < 1:
                self.fast_time += step
                if self.fast_time >= config.ACH_SPEED_DEMON_TIME:
                    self._unlock("speed_demon", out)
        self._last_t = game_t
        if float(data.get("since_hit", 0.0)) >= config.ACH_UNTOUCHABLE_TIME:
            self._unlock("untouchable", out)
        if int(data.get("equation_count", 0)) >= config.ACH_MATHEMATICIAN:
            self._unlock("mathematician", out)
        colors = data.get("active_colors") or ()
        if len(colors) >= config.ACH_RAINBOW and len({tuple(c) for c in colors}) == len(colors):
            self._unlock("rainbow", out)

    def on(self, event: str, **data: Any) -> list[Achievement]:
        """Handle a game event; returns the achievements unlocked by it (also queued in `pending`)."""
        out: list[Achievement] = []
        if event == "cast":
            for ach_id in sorted(equation_features(data.get("parsed"))):
                self._unlock(ach_id, out)
        elif event == "kill":
            self.run_kills += 1
            self.profile.add_lifetime("kills")
            self._unlock("first_blood", out)
            if self.run_kills >= config.ACH_CENTURION_KILLS:
                self._unlock("centurion", out)
        elif event == "boss_kill":
            self._unlock("giant_slayer", out)
        elif event == "upgrade":
            self._unlock("investor", out)
        elif event == "dash":
            if self.profile.add_lifetime("dashes") >= config.ACH_DASH_COUNT:
                self._unlock("dash_addict", out)
        elif event == "var_play":
            self._unlock("autoplay", out)
        elif event == "var_created":
            self._unlock("variable_star", out)
        elif event == "tick":
            self._tick(data, out)
        elif event == "undo":
            self._unlock("second_thoughts", out)
        elif event == "export":
            self._unlock("time_capsule", out)
        elif event == "import":
            self._unlock("homecoming", out)
        # "auto_on" and unknown events unlock nothing
        return out
