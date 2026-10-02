"""The 20 achievements (data) and AchievementTracker, fed by game events. No pygame (see DESIGN_V2 V6)."""
from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass
from typing import Any

from . import config
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
    Achievement("tan_monster", "The Tan Monster", "Cast tan(sqrt(x^2+y^2)) = y/x"),
    Achievement("first_blood", "First Blood", "Get your first kill"),
    Achievement("centurion", "Centurion", "Get 100 kills in one run"),
    Achievement("giant_slayer", "Giant Slayer", "Kill a boss"),
    Achievement("survivor", "Survivor", "Survive 5:00"),
    Achievement("marathon", "Marathon", "Survive 15:00"),
    Achievement("investor", "Investor", "Buy an upgrade"),
    Achievement("dash_addict", "Dash Addict", "Dash 100 times (lifetime)"),
)
BY_ID: dict[str, Achievement] = {a.id: a for a in ACHIEVEMENTS}
TOTAL = len(ACHIEVEMENTS)

_INVERSE = ("asin", "acos", "atan", "acot", "asec", "acsc", "arcsin", "arccos", "arctan",
            "arccot", "arcsec", "arccsc")
_TAN_MONSTER = "tan(sqrt(x^2+y^2))=y/x"
_SQUARE_X = re.compile(r"(?<![a-z])x\*\*\(?2\)?(?![\d.])")
_SQUARE_Y = re.compile(r"(?<![a-z])y\*\*\(?2\)?(?![\d.])")
_T_VAR = re.compile(r"(?<![a-z])t(?![a-z])")


def _has_word(text: str, names: tuple[str, ...]) -> bool:
    """True if any name appears as a whole word in text (so 'sin' does not match 'sinh' or 'asin')."""
    return any(re.search(rf"(?<![a-z]){n}(?![a-z])", text) for n in names)


def formula_features(parsed: Any) -> set[str]:
    """Which achievement-relevant features a parsed formula uses. Tolerant of old/new ParsedFormula shapes:
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
    norm = lambda s: re.sub(r"\s+", "", s.replace("**", "^"))   # noqa: E731
    if _TAN_MONSTER in (norm(source), norm(expr)) or norm(expr) == f"({_TAN_MONSTER.split('=')[0]})-(y/x)":
        found.add("tan_monster")
    return found


class AchievementTracker:
    """Receives game events, unlocks achievements on the profile and queues toasts for the UI."""

    def __init__(self, profile: Profile) -> None:
        self.profile = profile
        self.pending: deque[Achievement] = deque()   # newly unlocked, waiting to be shown as toasts
        self.run_kills = 0

    def reset_run(self) -> None:
        """Start of a new run (per-run counters only; lifetime counters live in the profile)."""
        self.run_kills = 0

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

    def on(self, event: str, **data: Any) -> list[Achievement]:
        """Handle a game event; returns the achievements unlocked by it (also queued in `pending`)."""
        out: list[Achievement] = []
        if event == "cast":
            for ach_id in sorted(formula_features(data.get("parsed"))):
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
            if int(data.get("active_count", 0)) >= config.ACH_FULL_HOUSE:
                self._unlock("full_house", out)
            game_t = float(data.get("game_t", 0.0))
            if game_t >= config.ACH_SURVIVOR_TIME:
                self._unlock("survivor", out)
            if game_t >= config.ACH_MARATHON_TIME:
                self._unlock("marathon", out)
        # "auto_on" and unknown events unlock nothing
        return out
