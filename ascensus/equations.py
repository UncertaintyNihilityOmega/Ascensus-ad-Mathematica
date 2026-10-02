"""EquationEntry + EquationManager: list ops, active set, queued layer, pulses, damage, rebuilds, save v2."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from . import config, view
from .curvefield import CurveData, build_curve, render_curve
from .enemies import Swarm
from .mathparse import EquationError, ParsedEquation, parse_equation
from .variables import VariableStore


@dataclass
class EquationEntry:
    text: str
    enabled: bool
    color: tuple[int, int, int]
    parsed: ParsedEquation
    curve: CurveData | None = None
    surface: "object | None" = None          # pygame.Surface, built lazily in draw
    bbox: "object | None" = None             # pygame.Rect of the curve on screen (surface origin)
    tiles: "list | None" = None              # sparse curves: [(screen xy, local area Rect)]; None = blit all
    pulse_timer: float = config.FIRST_PULSE_DELAY
    flash: float = 0.0
    rebuild_timer: float = 0.0
    stale: int | None = None                 # frame of a rebuild whose surface is not re-rendered yet
    var_dirty: bool = False                  # a variable this equation uses changed since its last build


def pulse_damage(length_units: float, base_dmg: float | None = None) -> float:
    """Damage per pulse: clamp(base*DMG_SCALE / max(L, L_MIN), DMG_MIN, base*DMG_MAX_FRAC)."""
    base = config.BASE_DMG if base_dmg is None else base_dmg
    d = base * config.DMG_SCALE / max(length_units, config.L_MIN)
    return min(max(d, config.DMG_MIN), base * config.DMG_MAX_FRAC)


def _bbox(points: np.ndarray):
    """Screen rect covering the curve plus its glow, clipped to the window."""
    import pygame
    m = config.CORE_DILATE + config.GLOW_DILATE + 2
    x0, y0 = np.floor(points.min(axis=0)).astype(int) - m
    x1, y1 = np.ceil(points.max(axis=0)).astype(int) + m
    return pygame.Rect(0, 0, view.W, view.H).clip(pygame.Rect(x0, y0, x1 - x0, y1 - y0))


def _tiles(points: np.ndarray, bbox):
    """Occupied CURVE_TILE squares (curve plus glow margin) as blit pairs, or None if blitting the bbox is cheaper."""
    import pygame
    n, m = config.CURVE_TILE, config.CORE_DILATE + config.GLOW_DILATE + 1
    local = points - np.array(bbox.topleft, dtype=np.float32)
    tx, ty = -(-bbox.w // n), -(-bbox.h // n)
    keys = []
    for dx in (-m, m):
        for dy in (-m, m):
            i = np.floor((local[:, 0] + dx) / n).astype(np.int64)
            j = np.floor((local[:, 1] + dy) / n).astype(np.int64)
            ok = (i >= 0) & (i < tx) & (j >= 0) & (j < ty)
            keys.append(j[ok] * tx + i[ok])
    flat = np.unique(np.concatenate(keys))
    ids = [(int(k % tx), int(k // tx)) for k in flat]
    if len(ids) > config.CURVE_TILE_MAX_FILL * tx * ty:
        return None
    out = []
    for i, j in ids:
        area = pygame.Rect(i * n, j * n, n, n).clip(pygame.Rect(0, 0, bbox.w, bbox.h))
        out.append(((bbox.x + area.x, bbox.y + area.y), area))
    return out


def _render_layer(curves: list, surf=None):
    """Draw many (points, colour) curves into one SRCALPHA surface at ALPHA_QUEUED (core line only).

    Returns (surface, tiles): tiles are the occupied CURVE_TILE squares as (dest, area) blit pairs,
    or None when blitting the whole surface is cheaper.
    """
    import pygame
    w, h, n = view.W, view.H, config.CURVE_TILE
    if surf is None or surf.get_size() != (w, h):
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
    pts = np.concatenate([p for p, _ in curves])
    packed = np.array([surf.map_rgb((*c, config.ALPHA_QUEUED)) for _, c in curves], dtype=np.uint32)
    vals = np.repeat(packed, [len(p) for p, _ in curves])
    r = config.CORE_DILATE
    ix, iy = np.rint(pts[:, 0]).astype(np.int64), np.rint(pts[:, 1]).astype(np.int64)
    ok = (ix >= r) & (ix < w - r) & (iy >= r) & (iy < h - r)        # keep every stamp inside the surface
    ix, iy, vals = ix[ok], iy[ok], vals[ok]
    flat = np.zeros(w * h, dtype=np.uint32)                          # [x, y] order, like surfarray
    base = ix * h + iy
    for dx in range(-r, r + 1):
        for dy in range(-r, r + 1):
            flat[base + dx * h + dy] = vals
    buf = pygame.surfarray.pixels2d(surf)
    buf[:] = flat.reshape(w, h)
    del buf
    tx, ty = -(-w // n), -(-h // n)
    occ = np.zeros((tx, ty), dtype=bool)
    for dx in (-r, r):
        for dy in (-r, r):
            occ[np.clip(ix + dx, 0, w - 1) // n, np.clip(iy + dy, 0, h - 1) // n] = True
    if occ.sum() > config.CURVE_TILE_MAX_FILL * tx * ty:
        return surf, None
    tiles = []
    for i, j in zip(*np.nonzero(occ)):
        area = pygame.Rect(int(i) * n, int(j) * n, n, n).clip(pygame.Rect(0, 0, w, h))
        tiles.append((area.topleft, area))
    return surf, tiles


def _read_color(value) -> tuple[int, int, int] | None:
    """A saved [r, g, b] list -> tuple, or None when missing or malformed."""
    try:
        r, g, b = (int(c) for c in value)
    except (TypeError, ValueError):
        return None
    return (r, g, b) if all(0 <= c <= 255 for c in (r, g, b)) else None


# --- migration of the pre-rename save (save/formulas.json, key "formulas") ----------------------
LEGACY_SAVE_NAME = "formulas.json"
LEGACY_KEY = "formulas"


def migrate_legacy_save(new_path: Path) -> bool:
    """One-time migration: if `new_path` is missing and a legacy formulas.json sits next to it, write
    the equations.json equivalent (the old file stays in place). Returns True when it migrated."""
    legacy = new_path.with_name(LEGACY_SAVE_NAME)
    if new_path.exists() or legacy == new_path or not legacy.exists():
        return False
    try:
        data = json.loads(legacy.read_text(encoding="utf-8"))
        if LEGACY_KEY in data and "equations" not in data:
            data["equations"] = data.pop(LEGACY_KEY)
        new_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = new_path.with_name(new_path.name + ".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(new_path)
        return True
    except (OSError, ValueError, TypeError):
        return False


class EquationManager:
    """Ordered list of equations; the first MAX_ACTIVE enabled ones fire."""

    def __init__(self, save_path: Path | None = None) -> None:
        self.save_path = save_path
        self.entries: list[EquationEntry] = []
        self._t = 0.0
        self._rr = 0
        self._frame = 0
        self.store = VariableStore()            # the equations' variables (auto-created / auto-removed)
        self._layer = None                      # the shared queued-curve layer (pygame.Surface)
        self._layer_tiles: list | None = None
        self._layer_sig: tuple | None = None
        self._layer_age = 1e9                   # seconds since the layer was last refreshed
        self._undo: list[tuple[EquationEntry, int, dict]] = []   # (entry, index, its removed variables)

    # --- list operations -------------------------------------------------
    def _free_color(self) -> tuple[int, int, int]:
        """First unused auto colour (the palette without Black/Graphite, which hide on the dark
        background); once all are used, the least-used one (cycling)."""
        counts = {c: 0 for c in config.CURVE_PALETTE_AUTO}
        for e in self.entries:
            if e.color in counts:
                counts[e.color] += 1
        return min(config.CURVE_PALETTE_AUTO, key=lambda c: counts[c])

    def set_color(self, i: int, color: tuple[int, int, int]) -> None:
        """Give row i a new curve colour (the surface re-renders; saved)."""
        e = self.entries[i]
        e.color = tuple(int(c) for c in color)
        e.surface, e.tiles, e.stale = None, None, None
        self.save()

    def _check_name(self, parsed: ParsedEquation, skip: int | None = None) -> None:
        """Equation names are unique (case-insensitive); `skip` is a row being re-parsed."""
        if parsed.name is None:
            return
        low = parsed.name.lower()
        for j, e in enumerate(self.entries):
            if j != skip and e.parsed.name is not None and e.parsed.name.lower() == low:
                raise EquationError(f"Name '{parsed.name}' already used")

    @property
    def variables(self) -> dict:
        """{name: {"value", "playing"}} as saved."""
        return self.store.to_dict()

    def _check_vars(self, parsed: ParsedEquation, skip: int | None = None) -> None:
        """Raise when the variables of all equations (with `parsed` replacing row `skip`) exceed the limit."""
        used = set(parsed.variables)
        for j, e in enumerate(self.entries):
            if j != skip:
                used |= e.parsed.variables
        if len(used) > config.MAX_VARIABLES:
            raise EquationError(f"Too many variables ({config.MAX_VARIABLES})")

    def _sync_vars(self, quiet: bool = False) -> None:
        """Create the variables the equations use (disabled ones count) and drop the unused ones."""
        used: list[str] = []
        for e in self.entries:
            used.extend(sorted(e.parsed.variables))
        self.store.sync(used, quiet)

    def _rebuild(self, e: EquationEntry, keep_surface: bool = False) -> None:
        step = config.GRID_STEP_T if (e.parsed.uses_t or e.var_dirty) else config.GRID_STEP
        e.var_dirty = False
        e.curve = build_curve(e.parsed.func, self._t, step, vars=self.store.values)
        if keep_surface and e.surface is not None:
            e.stale = self._frame               # keep showing the old curve; draw re-renders next frame
        else:
            e.surface, e.tiles = None, None

    def _append(self, text: str, enabled: bool = True, color=None, build: bool = True,
                sync: bool = True) -> EquationEntry:
        """Parse and append; build=False leaves the curve for update() to build progressively.

        sync=False (loading) leaves the variable store alone; the loader syncs once at the end.
        """
        if len(self.entries) >= config.MAX_ROWS:
            raise EquationError(f"Sidebar full ({config.MAX_ROWS}) - delete one first")
        parsed = parse_equation(text)
        self._check_name(parsed)
        self._check_vars(parsed)
        e = EquationEntry(parsed.text, enabled, color or self._free_color(), parsed)
        self.entries.append(e)
        if sync:
            self._sync_vars()
        if build:
            self._rebuild(e)
        return e

    def add(self, text: str) -> EquationEntry:
        """Parse and append an equation; raises EquationError on bad text or a full list."""
        e = self._append(text)
        self.save()
        return e

    def replace(self, i: int, text: str) -> None:
        """Re-parse row i in place, keeping its colour, position and on/off state."""
        parsed = parse_equation(text)
        self._check_name(parsed, skip=i)
        self._check_vars(parsed, skip=i)
        e = self.entries[i]
        e.text, e.parsed = parsed.text, parsed
        e.pulse_timer, e.flash, e.rebuild_timer = config.FIRST_PULSE_DELAY, 0.0, 0.0
        self._sync_vars()
        self._rebuild(e)
        self.save()

    def delete(self, i: int) -> None:
        """Remove row i; the entry (and the variables only it used) is remembered for undo_delete()."""
        before = dict(self.store.vars)
        entry = self.entries.pop(i)
        self._sync_vars()
        removed = {n: v for n, v in before.items() if n not in self.store.vars}
        self._undo.append((entry, i, removed))
        del self._undo[:-config.UNDO_MAX]
        self.save()

    @property
    def can_undo(self) -> bool:
        """True when a deleted equation can be brought back."""
        return bool(self._undo)

    def undo_delete(self) -> EquationEntry | None:
        """Re-insert the most recently deleted equation at its old row (clamped), with its variables.

        Returns the entry, or None when there is nothing to undo or it cannot come back (list full: it
        stays on the stack; name or variable clash with newer equations: it is dropped).
        """
        if not self._undo:
            return None
        entry, index, removed = self._undo[-1]
        if len(self.entries) >= config.MAX_ROWS:
            return None
        self._undo.pop()
        try:
            self._check_name(entry.parsed)
            self._check_vars(entry.parsed)
        except EquationError:
            return None
        self.entries.insert(min(index, len(self.entries)), entry)
        had = set(self.store.vars)
        self._sync_vars(quiet=True)
        for name, var in removed.items():           # variables that came back keep their old value / state
            if name not in had and name in self.store.vars:
                self.store.vars[name] = var
                self.store.values[name] = var.value
        entry.curve, entry.surface, entry.tiles, entry.stale = None, None, None, None
        entry.var_dirty, entry.rebuild_timer = False, 0.0
        self.save()
        return entry

    def move(self, src: int, dst: int) -> None:
        """Move row src so it ends up at index dst."""
        self.entries.insert(dst, self.entries.pop(src))
        self.save()

    def toggle(self, i: int) -> None:
        self.entries[i].enabled = not self.entries[i].enabled
        self.save()

    def on_resize(self) -> None:
        """The view changed: active curves rebuild now, the rest progressively (2 per frame)."""
        active = self.active()
        for e in self.entries:
            if any(e is a for a in active):
                self._rebuild(e)
            else:
                e.curve, e.surface, e.tiles, e.stale = None, None, None, None
        self._layer = self._layer_sig = None

    # --- persistence -----------------------------------------------------
    def save(self) -> None:
        """Write {"version":2,"equations":[{text,enabled,color}],"variables":{name:{value,playing}}}.

        No-op without a save_path."""
        if self.save_path is None:
            return
        data = {"version": 2,
                "equations": [{"text": e.text, "enabled": e.enabled, "color": list(e.color)}
                             for e in self.entries],
                "variables": self.store.to_dict()}
        try:
            self.save_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.save_path.with_name(self.save_path.name + ".tmp")
            tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
            tmp.replace(self.save_path)
        except OSError:
            pass                        # a failed save must never crash the game

    def load(self) -> None:
        """Replace entries from disk (v1 and v2); unreadable files and unparsable entries are skipped.

        Active curves build at once; queued ones build progressively in update().
        """
        self.entries = []
        self._undo.clear()
        self.store.sync([], quiet=True)
        if self.save_path is None:
            return
        if not self.save_path.exists():
            migrate_legacy_save(self.save_path)
        if not self.save_path.exists():
            return
        try:
            data = json.loads(self.save_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        self.apply_data(data)

    def apply_data(self, data: dict) -> None:
        """Replace the list from a save-shaped dict {"equations": [{text, enabled, color}], "variables": {...}}.

        Used by load() and by savegame.restore(). Unparsable entries are skipped; no file is written (call
        save() for that). Variable `dir` (the ping-pong direction) is restored when present.
        """
        self.entries = []
        self._undo.clear()
        self.store.sync([], quiet=True)
        try:
            rows = data["equations"] if "equations" in data else data[LEGACY_KEY]
            for row in rows:
                try:
                    self._append(str(row["text"]), bool(row.get("enabled", True)),
                                 _read_color(row.get("color")), build=False, sync=False)
                except (EquationError, KeyError, TypeError, AttributeError):
                    continue
            self._sync_vars(quiet=True)
            self.store.load_values(data.get("variables"))
            for name, row in (data.get("variables") or {}).items():
                if name in self.store.vars and isinstance(row, dict):
                    self.store.vars[name].dir = -1 if row.get("dir") == -1 else 1
        except (ValueError, KeyError, TypeError, AttributeError):
            return
        finally:
            self._sync_vars(quiet=True)
            self.store.drain_changed()
            for e in self.active():
                if e.curve is None:
                    self._rebuild(e)

    # --- state -----------------------------------------------------------
    def active(self) -> list[EquationEntry]:
        return [e for e in self.entries if e.enabled][:config.MAX_ACTIVE]

    def status(self, e: EquationEntry) -> str:
        """'off' | 'queued' | 'offscreen' | 'active'."""
        if not e.enabled:
            return "off"
        if not any(e is a for a in self.active()):
            return "queued"
        if e.curve is not None and len(e.curve.points) == 0:
            return "offscreen"
        return "active"

    # --- per-frame -------------------------------------------------------
    def _build_pending(self, active: list[EquationEntry]) -> None:
        """Active entries without a curve build now; queued ones QUEUED_BUILD_PER_FRAME per frame."""
        for e in active:
            if e.curve is None:
                self._rebuild(e)
        budget = config.QUEUED_BUILD_PER_FRAME
        for e in self.entries:
            if budget <= 0:
                break
            if e.enabled and e.curve is None:
                self._rebuild(e)
                budget -= 1

    def _is_dirty(self, e: EquationEntry) -> bool:
        """An active curve animates when it uses t or a variable that changed since its last build."""
        return e.parsed.uses_t or e.var_dirty

    def _rebuild_dirty(self, active: list[EquationEntry], dt: float) -> None:
        """Dirty active curves rebuild at most T_REBUILD_HZ each, REBUILDS_PER_FRAME per frame, round-robin."""
        due = 1.0 / config.T_REBUILD_HZ
        for e in active:
            if self._is_dirty(e):
                e.rebuild_timer += dt
        n, done = len(active), 0
        for k in range(n):
            i = (self._rr + k) % n
            e = active[i]
            if self._is_dirty(e) and e.rebuild_timer >= due:
                e.rebuild_timer = 0.0
                self._rebuild(e, keep_surface=True)
                self._rr = (i + 1) % n
                done += 1
                if done >= config.REBUILDS_PER_FRAME:
                    break

    def update(self, dt: float, game_t: float, swarm: Swarm, player_pos: np.ndarray,
               base_dmg: float | None = None, cooldown: float | None = None) -> int:
        """Rebuild one due t-curve, fire pulses on active equations; returns enemies killed.

        base_dmg / cooldown are the upgrade stats (defaults: the config start values).
        The killed enemies' summed max hp is left in `swarm.last_removed_max_hp`.
        """
        period = config.PULSE_PERIOD if cooldown is None else max(cooldown, config.COOLDOWN_MIN)
        self._t = game_t
        self._frame += 1
        self._layer_age += dt
        self.store.update(dt)
        changed = self.store.drain_changed()
        if changed:
            for e in self.entries:
                if e.parsed.variables & changed:
                    e.var_dirty = True
        active = self.active()
        self._build_pending(active)
        self._rebuild_dirty(active, dt)
        for e in self.entries:
            e.flash = max(0.0, e.flash - dt)
        for e in active:
            e.pulse_timer -= dt
            if e.pulse_timer > 0:
                continue
            e.pulse_timer += period
            e.flash = config.PULSE_FADE
            if e.curve is not None and len(e.curve.points):
                swarm.damage_where(e.curve.hit_mask, pulse_damage(e.curve.length_units, base_dmg),
                                   player_pos)
        return swarm.remove_dead()

    def _draw_queued_layer(self, screen, active: list[EquationEntry]) -> None:
        """Queued curves live in ONE surface, re-rendered at most once per QUEUED_LAYER_PERIOD when dirty."""
        act = {id(a) for a in active}
        queued = [e for e in self.entries
                  if e.enabled and e.curve is not None and id(e) not in act and len(e.curve.points)]
        sig = (view.W, view.H, tuple((id(e), e.color, id(e.curve)) for e in queued))
        if sig != self._layer_sig and (self._layer_age >= config.QUEUED_LAYER_PERIOD
                                       or self._layer_sig is None):
            self._layer_sig, self._layer_age = sig, 0.0
            if queued:
                self._layer, self._layer_tiles = _render_layer(
                    [(e.curve.points, e.color) for e in queued], self._layer)
            else:
                self._layer = self._layer_tiles = None
        if self._layer is None:
            return
        if self._layer_tiles is None:
            screen.blit(self._layer, (0, 0))
        else:
            for dest, area in self._layer_tiles:
                screen.blit(self._layer, dest, area)

    def draw(self, screen) -> None:
        """Blit the shared queued layer, then each active curve (surfaces render lazily, so tests stay headless)."""
        active = self.active()
        self._draw_queued_layer(screen, active)
        act = {id(a) for a in active}
        for e in self.entries:
            if id(e) not in act:
                if e.surface is not None:                # only active entries own a surface
                    e.surface, e.tiles, e.stale = None, None, None
                continue
            if e.curve is None or len(e.curve.points) == 0:
                continue
            if e.surface is None or (e.stale is not None and e.stale < self._frame):
                e.stale = None
                e.bbox = _bbox(e.curve.points)           # the surface covers only the curve's bbox
                shifted = e.curve.points - np.array(e.bbox.topleft, dtype=np.float32)
                e.surface = render_curve(shifted, e.color, (max(e.bbox.w, 1), max(e.bbox.h, 1)))
                e.tiles = _tiles(e.curve.points, e.bbox)
            k = min(e.flash / config.PULSE_FADE, 1.0)
            alpha = config.ALPHA_IDLE + (config.ALPHA_PULSE - config.ALPHA_IDLE) * k
            e.surface.set_alpha(int(alpha))
            if e.tiles is None:
                screen.blit(e.surface, e.bbox.topleft)
            else:
                for dest, area in e.tiles:
                    screen.blit(e.surface, dest, area)
