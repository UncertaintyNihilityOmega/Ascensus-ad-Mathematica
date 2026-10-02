"""VariableStore: the free variables of the equations (a, b_1, ...), their values and play state. Headless."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Iterable

from ascensus import config


@dataclass
class Variable:
    """One variable: its value, whether it is playing (ping-pong) and the direction of the next step."""
    value: float = 1.0
    playing: bool = False
    dir: int = 1


class VariableStore:
    """Ordered map name -> Variable.

    The owner (EquationManager) calls sync() with the names the equations use: unknown names are
    created (value VAR_DEFAULT), unused ones removed. update(dt) advances the playing variables.
    `changed` collects the names whose value moved since the owner last called drain_changed().
    `listener(event, **data)` (if set) hears ("var_created", name=) and ("var_play", name=).
    """

    def __init__(self) -> None:
        self.vars: dict[str, Variable] = {}
        self.values: dict[str, float] = {}           # name -> value, handed to build_curve(vars=)
        self.changed: set[str] = set()
        self.listener: Callable[..., None] | None = None
        self._acc = 0.0                              # fractional play steps carried between frames
        self._names: list[str] = []

    # --- queries -----------------------------------------------------------
    def __len__(self) -> int:
        return len(self.vars)

    def __contains__(self, name: str) -> bool:
        return name in self.vars

    def names(self) -> list[str]:
        """Names in creation order (shared list: do not mutate)."""
        return self._names

    def get(self, name: str) -> Variable:
        return self.vars[name]

    def _emit(self, event: str, **data) -> None:
        if self.listener is not None:
            self.listener(event, **data)

    # --- structure ---------------------------------------------------------
    def sync(self, used: Iterable[str], quiet: bool = False) -> None:
        """Make the store hold exactly the names in `used` (creation order kept, new names appended).

        Raises ValueError when that would exceed MAX_VARIABLES. `quiet` skips the var_created events.
        """
        used = list(dict.fromkeys(used))
        keep = set(used)
        new = [n for n in used if n not in self.vars]
        if len(keep) > config.MAX_VARIABLES:
            raise ValueError(f"Too many variables ({config.MAX_VARIABLES})")
        for n in [n for n in self.vars if n not in keep]:
            del self.vars[n], self.values[n]
            self.changed.discard(n)
        for n in new:
            self.vars[n] = Variable(config.VAR_DEFAULT)
            self.values[n] = config.VAR_DEFAULT
            if not quiet:
                self._emit("var_created", name=n)
        self._names = list(self.vars)

    # --- values ------------------------------------------------------------
    def set_value(self, name: str, v: float) -> None:
        """Set a value (typed floats may lie outside VAR_MIN..VAR_MAX); marks it changed when it moved."""
        v = float(v)
        if not math.isfinite(v):
            return
        var = self.vars[name]
        if v != var.value:
            var.value = self.values[name] = v
            self.changed.add(name)

    def toggle_play(self, name: str) -> None:
        var = self.vars[name]
        var.playing = not var.playing
        if var.playing:
            self._emit("var_play", name=name)

    def set_playing(self, name: str, playing: bool) -> None:
        if self.vars[name].playing != playing:
            self.toggle_play(name)

    def drain_changed(self) -> set[str]:
        """The names changed since the last call (and forget them)."""
        out, self.changed = self.changed, set()
        return out

    def update(self, dt: float) -> None:
        """Advance playing variables: VAR_PLAY_HZ steps of VAR_STEP per second of game time, ping-pong."""
        playing = [n for n, v in self.vars.items() if v.playing]
        if not playing or config.VAR_STEP <= 0:
            self._acc = 0.0
            return
        self._acc += max(dt, 0.0) * config.VAR_PLAY_HZ
        steps = int(self._acc)
        self._acc -= steps
        if steps:
            for n in playing:
                self._advance(n, steps)

    def _advance(self, name: str, steps: int) -> None:
        """Move `steps` ticks along the lo..hi ping-pong (closed form, so a dt spike costs nothing)."""
        lo, step = config.VAR_MIN, config.VAR_STEP
        top = max(int(round((config.VAR_MAX - lo) / step)), 1)          # ticks from lo to hi
        var = self.vars[name]
        k = min(max(int(round((var.value - lo) / step)), 0), top)       # current tick (clamped into range)
        pos = k if var.dir >= 0 else 2 * top - k                        # position on the unfolded cycle
        pos = (pos + steps) % (2 * top)
        if pos < top:
            k, var.dir = pos, 1
        else:
            k, var.dir = 2 * top - pos, -1
        self.set_value(name, round(lo + k * step, 10))

    # --- persistence -------------------------------------------------------
    def to_dict(self) -> dict:
        """{name: {"value", "playing"}} for the save file."""
        return {n: {"value": v.value, "playing": v.playing} for n, v in self.vars.items()}

    def load_values(self, data: object) -> None:
        """Apply saved values / play flags to the variables that exist; malformed entries are ignored."""
        if not isinstance(data, dict):
            return
        for name, row in data.items():
            var = self.vars.get(name)
            if var is None or not isinstance(row, dict):
                continue
            try:
                v = float(row.get("value", var.value))
            except (TypeError, ValueError):
                continue
            if math.isfinite(v):
                var.value = self.values[name] = v
            var.playing = bool(row.get("playing", False))
