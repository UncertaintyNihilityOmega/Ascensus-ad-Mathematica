"""Settings registry: tunable config attributes shown on the Settings page (no pygame).

Each Setting names an attribute of `ascensus.config`. Values are applied with setattr(config, ...),
saved to config.SETTINGS_PATH (only values that differ from the defaults) and re-applied at startup
with apply_saved(). Defaults are captured when this module is imported.

Scene usage:
    for tab in settings.tabs(): ...                 # tab names, in display order
    for s in settings.settings_for(tab): ...        # Setting rows (label, kind, min, max, step, note)
    settings.get(s.key); settings.set_value(s.key, v); settings.nudge(s.key, +1)   # the [+] button
    settings.reset(s.key); settings.reset_tab(tab); settings.reset_all(); settings.save()
    s.next_run  -> show "(next run)": the value only matters when a new run starts
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

from ascensus import config


@dataclass(frozen=True)
class Setting:
    """One tunable: `kind` is 'int', 'float', 'bool', 'choice' (value is one of `choices`) or
    'key' (a pygame key name such as 'j' or 'space', bound by clicking and pressing a key)."""
    key: str                      # attribute name in ascensus.config
    label: str
    tab: str
    kind: str = "float"
    min: float = 0.0
    max: float = 1.0
    step: float = 1.0             # size of the [-] / [+] buttons
    note: str = ""
    next_run: bool = False        # True: only applies to a new run (or launch)
    choices: tuple = ()


def _i(key, label, tab, lo, hi, step=1, note="", next_run=False) -> Setting:
    return Setting(key, label, tab, "int", lo, hi, step, note, next_run)


def _f(key, label, tab, lo, hi, step, note="", next_run=False) -> Setting:
    return Setting(key, label, tab, "float", lo, hi, step, note, next_run)


def _b(key, label, tab, note="", next_run=False) -> Setting:
    return Setting(key, label, tab, "bool", 0, 1, 1, note, next_run)


def _c(key, label, tab, choices, note="") -> Setting:
    return Setting(key, label, tab, "choice", note=note, choices=tuple(choices))


def _k(key, label, tab, note="") -> Setting:
    return Setting(key, label, tab, "key", note=note)


DISPLAY, CONTROLS, PLAYER, ENEMIES, BOSS, COMBAT, UPGRADES, EQUATIONS = (
    "Display", "Controls", "Player", "Enemies", "Boss", "Combat", "Upgrades & XP", "Equations & Variables")

SETTINGS: list[Setting] = [
    # Display
    _b("FULLSCREEN_START", "Fullscreen", DISPLAY, "Start in full screen (F11 toggles in game)", True),
    _f("WINDOW_FRACTION", "Window size", DISPLAY, 0.3, 1.0, 0.05, "Window height as a fraction of the screen", True),
    _f("UNIT_PX", "Zoom (pixels per unit)", DISPLAY, 25, 100, 5, "Pixels per math unit; rebuilds the curves"),
    _b("SHOW_FPS_DEFAULT", "Show FPS", DISPLAY, "F3 toggles in game"),
    _b("SHOW_GRID_DEFAULT", "Show grid", DISPLAY, "G toggles in game"),
    _i("GRID_STEP", "Curve quality (grid step)", DISPLAY, 2, 6, 1, "Smaller is smoother but slower"),
    # Controls
    _c("MOVE_MODE", "Movement", CONTROLS, ("WASD", "Mouse"), "WASD keys, or walk toward the mouse (right-click dashes)"),
    _k("DASH_KEY", "Dash key", CONTROLS, "Click, then press a key (Esc cancels)"),
    _f("MOUSE_DEAD_ZONE", "Mouse dead zone", CONTROLS, 0, 200, 1, "Pixels around you where the mouse means stand still"),
    # Player
    _i("PLAYER_HP", "Base max HP", PLAYER, 10, 1000, 10, "", True),
    _f("PLAYER_SPEED", "Speed", PLAYER, 50, 600, 10, "Pixels per second"),
    _f("PLAYER_REGEN_PER_MIN", "Regen per minute", PLAYER, 0, 200, 5),
    _f("PLAYER_IFRAMES", "Invulnerability after a hit (s)", PLAYER, 0, 3, 0.1),
    _f("DASH_DIST", "Dash distance", PLAYER, 20, 600, 10, "Pixels"),
    _f("DASH_TIME", "Dash time (s)", PLAYER, 0.03, 1.0, 0.01),
    _f("DASH_COOLDOWN", "Dash cooldown (s)", PLAYER, 0, 10, 0.1, "0 means no limit"),
    _f("TYPING_TIME_SCALE", "Typing slow-mo", PLAYER, 0.0, 1.0, 0.05, "Game speed while typing (1 = none)"),
    # Enemies
    _f("ENEMY_RADIUS", "Radius", ENEMIES, 4, 40, 1, "Pixels"),
    _i("ENEMY_MAX_ALIVE", "Max alive", ENEMIES, 10, 600, 10, "Bosses are not counted"),
    _f("ENEMY_SPAWN_MARGIN", "Spawn margin", ENEMIES, 0, 200, 5, "Pixels outside the screen"),
    _f("ENEMY_FLASH", "Hit flash (s)", ENEMIES, 0, 1, 0.05),
    _f("ENEMY_HP_BASE", "HP at start", ENEMIES, 1, 1000, 1),
    _f("ENEMY_HP_PER_MIN", "HP growth per minute", ENEMIES, 0, 2, 0.05, "Fraction of the base"),
    _f("ENEMY_DMG_BASE", "Contact damage at start", ENEMIES, 0, 200, 1),
    _f("ENEMY_DMG_PER_MIN", "Damage growth per minute", ENEMIES, 0, 2, 0.05, "Fraction of the base"),
    _f("ENEMY_SPEED_BASE", "Speed at start", ENEMIES, 10, 400, 5),
    _f("ENEMY_SPEED_PER_MIN", "Speed growth per minute", ENEMIES, 0, 1, 0.01, "Fraction of the base"),
    _f("ENEMY_SPEED_MAX", "Speed cap", ENEMIES, 20, 600, 5),
    _f("SPAWN_MIN_INTERVAL", "Fastest spawn interval (s)", ENEMIES, 0.02, 3, 0.01),
    _f("SPAWN_RATE_PER_MIN", "Spawn speed-up per minute", ENEMIES, 0, 2, 0.05),
    _f("KNOCKBACK_DIST", "Knockback distance", ENEMIES, 0, 200, 5, "Touching enemies are shoved on a hit"),
    # Boss
    _f("BOSS_INTERVAL", "Interval (s)", BOSS, 30, 1800, 30, "Game time between bosses"),
    _f("BOSS_HP_MULT", "HP multiplier", BOSS, 1, 500, 5),
    _f("BOSS_DMG_MULT", "Damage multiplier", BOSS, 0.5, 20, 0.5),
    _f("BOSS_SPEED_MULT", "Speed multiplier", BOSS, 0.1, 3, 0.05),
    _f("BOSS_RADIUS", "Radius", BOSS, 10, 120, 1, "Pixels"),
    # Combat
    _i("MAX_ACTIVE", "Active equations", COMBAT, 1, 12, 1, "Equations that can fire at once"),
    _f("BASE_DMG", "Base damage at start", COMBAT, 1, 10000, 10, "", True),
    _f("PULSE_PERIOD", "Base cooldown (s)", COMBAT, 0.05, 10, 0.05, "Seconds between pulses", True),
    _f("COOLDOWN_MIN", "Cooldown floor (s)", COMBAT, 0.01, 1, 0.01),
    _f("DMG_SCALE", "Damage scale", COMBAT, 0.1, 100, 0.5, "dmg = base * scale / curve length"),
    _f("L_MIN", "Minimum curve length", COMBAT, 0.5, 50, 0.5, "Short curves do not get extra damage"),
    _i("HIT_DILATE", "Hit thickness", COMBAT, 0, 6, 1, "Hit-mask cells added around a curve"),
    # Upgrades & XP
    _f("XP_PER_HP", "XP per enemy HP", UPGRADES, 0, 10, 0.05),
    _i("UPG_HP_STEP", "Max HP step", UPGRADES, 1, 500, 5),
    _i("UPG_DMG_STEP", "Base DMG step", UPGRADES, 1, 500, 5),
    _f("UPG_CD_MULT", "Cooldown multiplier", UPGRADES, 0.5, 0.99, 0.01, "Applied on each Cooldown buy"),
    _f("UPG_COST_BASE", "Cost base", UPGRADES, 1, 1000, 5),
    _f("UPG_COST_GROWTH", "Cost growth", UPGRADES, 1.0, 3.0, 0.01, "Cost = base * growth ^ level"),
    # Equations & Variables
    _i("MAX_ROWS", "Max equations", EQUATIONS, 1, 500, 10),
    _i("MAX_VARIABLES", "Max variables", EQUATIONS, 1, 500, 10),
    _f("VAR_MIN", "Variable minimum", EQUATIONS, -1000, 0, 1, "Slider and play range"),
    _f("VAR_MAX", "Variable maximum", EQUATIONS, 0, 1000, 1, "Slider and play range"),
    _f("VAR_STEP", "Variable step", EQUATIONS, 0.001, 1, 0.01, "Slider snap and play step"),
    _f("VAR_PLAY_HZ", "Variable play rate (Hz)", EQUATIONS, 1, 600, 5, "Steps per second of game time"),
    _f("VAR_DEFAULT", "Variable default", EQUATIONS, -1000, 1000, 0.5, "Value of a new variable"),
    _f("T_REBUILD_HZ", "Animated curve rebuilds (Hz)", EQUATIONS, 1, 60, 1, "Per curve that uses t or a moving variable"),
]

_BY_KEY: dict[str, Setting] = {s.key: s for s in SETTINGS}
assert len(_BY_KEY) == len(SETTINGS), "duplicate setting key"
DEFAULTS: dict[str, object] = {s.key: getattr(config, s.key) for s in SETTINGS}   # captured at import


# -- lookup ------------------------------------------------------------------------------------------
def tabs() -> list[str]:
    """Tab names in display order."""
    return list(dict.fromkeys(s.tab for s in SETTINGS))


def settings_for(tab: str) -> list[Setting]:
    """The Setting rows of one tab, in display order."""
    return [s for s in SETTINGS if s.tab == tab]


def find(key: str) -> Setting | None:
    return _BY_KEY.get(key)


def get(key: str):
    """Current value (read from config)."""
    return getattr(config, _BY_KEY[key].key)


def default(key: str):
    return DEFAULTS[key]


def is_default(key: str) -> bool:
    return get(key) == DEFAULTS[key]


# -- changing values ---------------------------------------------------------------------------------
def coerce(s: Setting, v):
    """Convert `v` to the setting's type and clamp it; raises ValueError/TypeError if impossible."""
    if s.kind == "bool":
        if not isinstance(v, (bool, int, float)) or isinstance(v, float) and v not in (0.0, 1.0):
            raise ValueError("not a bool")
        return bool(v)
    if s.kind == "choice":
        if v not in s.choices:
            raise ValueError("not a choice")
        return v
    if s.kind == "key":
        if not isinstance(v, str) or not v.strip() or len(v) > 32:
            raise ValueError("not a key name")
        return v.strip().lower()
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise ValueError("not a finite number")
    v = min(max(v, s.min), s.max)
    return int(round(v)) if s.kind == "int" else round(float(v), 6)


def set_value(key: str, v):
    """Clamp `v` to the setting's range, apply it to config and return the applied value."""
    s = _BY_KEY[key]
    v = coerce(s, v)
    setattr(config, key, v)
    return v


def nudge(key: str, direction: int):
    """The [-] / [+] buttons: move by one `step` (bool settings toggle). Returns the new value."""
    s = _BY_KEY[key]
    cur = get(key)
    if s.kind == "bool":
        return set_value(key, not cur)
    if s.kind == "choice":
        i = s.choices.index(cur) if cur in s.choices else 0
        return set_value(key, s.choices[(i + direction) % len(s.choices)])
    if s.kind == "key":
        return cur                                    # bound by pressing a key, not nudged
    return set_value(key, cur + direction * s.step)


def reset(key: str) -> None:
    setattr(config, key, DEFAULTS[key])


def reset_tab(tab: str) -> None:
    for s in settings_for(tab):
        reset(s.key)


def reset_all() -> None:
    for s in SETTINGS:
        reset(s.key)


# -- persistence -------------------------------------------------------------------------------------
def _path(path: Path | str | None) -> Path:
    return Path(config.SETTINGS_PATH if path is None else path)


def save(path: Path | str | None = None) -> bool:
    """Write the values that differ from the defaults; False if the file cannot be written."""
    values = {s.key: get(s.key) for s in SETTINGS if not is_default(s.key)}
    p = _path(path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps({"version": 1, "values": values}, indent=2), encoding="utf-8")
        tmp.replace(p)
        return True
    except OSError:
        return False


def load(path: Path | str | None = None) -> dict[str, object]:
    """Read the saved overrides: only known keys with valid, clamped values. Never raises."""
    try:
        data = json.loads(_path(path).read_text(encoding="utf-8"))
        raw = data["values"]
        items = list(raw.items())
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return {}
    out: dict[str, object] = {}
    for key, v in items:
        s = _BY_KEY.get(key)
        if s is None:
            continue                                  # unknown key: ignore
        try:
            out[key] = coerce(s, v)
        except (ValueError, TypeError):
            continue                                  # bad value: keep the default
    return out


def apply_saved(path: Path | str | None = None) -> int:
    """Load the saved file and apply it to config (call once at startup). Returns the count applied."""
    values = load(path)
    for key, v in values.items():
        setattr(config, key, v)
    return len(values)
