"""Save games: snapshot(game) <-> restore(data), thumbnails, and the slot files (SlotStore).

A save is plain JSON ("version": 1). The RNG is not saved (a restored run gets a new seed) and neither is
the profile (bests and achievements live in save/profile.json). Restoring also makes the saved equations the
current list (written to the game's equations file).
"""
from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pygame

from . import config, view
from .equations import USE_CONFIG, resolve_save_path
from .curvefield import render_curve

AUTO = "autosave"                          # the slot key of the autosave (the others are 1..SAVE_SLOTS)
_REQUIRED = ("game_t", "kills", "player", "swarm", "spawner", "upgrades", "equations", "variables")


# --- snapshot / restore ------------------------------------------------------------------------------
def snapshot(game) -> dict:
    """Everything needed to continue the run, as JSON-ready lists and numbers (see restore)."""
    p = game.player
    player = {"pos": np.asarray(p.pos, dtype=float).tolist(), "hp": float(p.hp), "max_hp": float(p.max_hp),
              "facing": np.asarray(p.facing, dtype=float).tolist(),
              "iframes": float(getattr(p, "iframes", 0.0)), "dash_left": float(getattr(p, "dash_left", 0.0)),
              "dash_cd": float(getattr(p, "dash_cd", 0.0)), "dash_count": int(getattr(p, "dash_count", 0))}
    store = game.equations.store
    return {
        "version": config.SAVE_VERSION,
        "game_t": float(game.game_t),
        "kills": int(game.kills),
        "boss_banner": float(getattr(game, "boss_banner", 0.0)),
        "speed": float(getattr(game, "speed", 1)),
        "player": player,
        "swarm": game.swarm.to_dict(),
        "spawner": game.spawner.to_dict(),
        "stats": {"bosses_killed": int(game.swarm.bosses_killed), "damage_dealt": float(game.swarm.damage_dealt),
                  "dashes": player["dash_count"], "equations_cast": int(game.equations_cast)},
        "upgrades": game.upgrades.to_dict(),
        "equations": [{"text": e.text, "enabled": bool(e.enabled), "color": list(e.color)}
                      for e in game.equations.entries],
        "variables": {n: {"value": float(v.value), "playing": bool(v.playing), "dir": int(v.dir)}
                      for n, v in store.vars.items()},
    }


def _finite(x, lo: float | None = None) -> float:
    """float(x), which must be finite (and >= lo when given); ValueError otherwise."""
    v = float(x)
    if not math.isfinite(v) or (lo is not None and v < lo):
        raise ValueError(f"bad number {x!r}")
    return v


def restore(data: dict, save_path: Path | None | str = USE_CONFIG, profile=None):
    """Build a GameScene continuing the saved run; raises ValueError when `data` is not a valid save.

    `save_path` is where the restored equations are written (None: nowhere); `profile` as for GameScene.
    """
    from .scenes import GameScene                         # lazy: scenes may import this module

    if not isinstance(data, dict) or data.get("version") != config.SAVE_VERSION:
        raise ValueError("unsupported save version")
    if any(k not in data for k in _REQUIRED):
        raise ValueError("incomplete save")
    try:
        game = GameScene(seed=None, save_path=None, profile=profile)    # fresh rng seed; no equations read
        game.game_t = _finite(data["game_t"], 0.0)
        game.kills = int(data["kills"])
        game.boss_banner = max(_finite(data.get("boss_banner", 0.0)), 0.0)
        stats = data.get("stats", {})
        game.equations_cast = int(stats.get("equations_cast", 0))
        pl, p = data["player"], game.player
        p.pos = np.array([_finite(c) for c in pl["pos"]], dtype=float).reshape(2)
        p.max_hp = _finite(pl["max_hp"], 1.0)
        p.hp = min(_finite(pl["hp"]), p.max_hp)
        facing = np.array([_finite(c) for c in pl["facing"]], dtype=float).reshape(2)
        n = float(np.hypot(*facing))
        if n < 1e-9:
            facing = np.array((1.0, 0.0))
        elif abs(n - 1.0) > 1e-6:
            facing = facing / n                                 # keep exact values when already a unit vector
        p.facing = facing
        for name in ("iframes", "dash_left", "dash_cd"):       # optional: absent in older saves
            if hasattr(p, name):
                setattr(p, name, _finite(pl.get(name, 0.0), 0.0))
        p.dash_count = int(stats.get("dashes", pl.get("dash_count", 0)))
        game.swarm.load_dict(data["swarm"])
        game.swarm.bosses_killed = int(stats.get("bosses_killed", game.swarm.bosses_killed))
        game.swarm.damage_dealt = float(stats.get("damage_dealt", game.swarm.damage_dealt))
        game.spawner.load_dict(data["spawner"])
        game.upgrades.load_dict(data["upgrades"])
        game._auto_prev = game.upgrades.auto                    # no "auto_on" achievement event on load
        if hasattr(game, "speed"):                              # the time-speed multiplier (P19)
            try:
                speed = _finite(data.get("speed", 1), 0.0)
                game.speed = int(speed) if speed.is_integer() and speed >= 1 else 1   # SPEED_STEPS are ints
            except AttributeError:                              # read-only property: leave it
                pass
    except (KeyError, TypeError, ValueError, IndexError, AttributeError) as err:
        raise ValueError(f"corrupt save: {err}") from err
    game.equations.apply_data({"equations": data["equations"], "variables": data["variables"]})
    game.equations.save_path = resolve_save_path(save_path)
    game.equations.save()
    return game


# --- thumbnails ----------------------------------------------------------------------------------------
def render_thumbnail(game, size: tuple[int, int] | None = None) -> pygame.Surface:
    """Grid plus the active curves (no enemies, no UI) at the screen size, cropped to the thumbnail's
    aspect ratio around the centre and smoothscaled to `size` (default config.THUMB_SIZE)."""
    tw, th = size or config.THUMB_SIZE
    surf = pygame.Surface((view.W, view.H), 0, 32)
    surf.fill(config.BG_COLOR)
    if getattr(game, "show_grid", True):
        for color, p0, p1 in getattr(game, "grid_lines", ()):
            pygame.draw.line(surf, color, p0, p1)
        for img, pos in getattr(game, "grid_labels", ()):
            surf.blit(img, pos)
    for e in game.equations.active():
        if e.curve is not None and len(e.curve.points):
            layer = render_curve(e.curve.points, e.color)
            layer.set_alpha(config.ALPHA_PULSE)
            surf.blit(layer, (0, 0))
    w, h = surf.get_size()
    cw, ch = (min(w, int(h * tw / th)), h) if w * th > h * tw else (w, min(h, int(w * th / tw)))
    crop = surf.subsurface(pygame.Rect((w - cw) // 2, (h - ch) // 2, max(cw, 1), max(ch, 1)))
    return pygame.transform.smoothscale(crop, (tw, th))


# --- slot files ----------------------------------------------------------------------------------------
@dataclass
class SlotInfo:
    """What the Saves page and the Continue button need to know about a save file."""
    slot: int | str
    game_t: float
    kills: int
    saved_at: float                  # epoch seconds
    thumb: Path | None               # the png, when it exists

    def date_text(self) -> str:
        """'2026-10-02 14:33' in local time."""
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(self.saved_at))


class SlotStore:
    """save/slots/slot1..6.json (+ .png) and autosave.json (+ .png). Missing or corrupt files read as empty.

    Slots are numbered 1..config.SAVE_SLOTS; the autosave has the key AUTO. Nothing here raises on bad files
    or a read-only folder: reads give None / empty, writes give False.
    """

    def __init__(self, path: Path | str | None = None) -> None:
        self.dir = Path(path) if path is not None else config.SLOTS_PATH

    # -- paths ------------------------------------------------------------------------------------------
    def _stem(self, slot: int | str) -> str:
        if slot == AUTO:
            return AUTO
        if isinstance(slot, int) and 1 <= slot <= config.SAVE_SLOTS:
            return f"slot{slot}"
        raise ValueError(f"bad slot {slot!r}")

    def json_path(self, slot: int | str) -> Path:
        return self.dir / f"{self._stem(slot)}.json"

    def thumb_path(self, slot: int | str) -> Path:
        return self.dir / f"{self._stem(slot)}.png"

    # -- reading ----------------------------------------------------------------------------------------
    def load(self, slot: int | str) -> dict | None:
        """The save dict of a slot (for restore()), or None when missing, unreadable or not a save."""
        try:
            data = json.loads(self.json_path(slot).read_text(encoding="utf-8"))
            if (isinstance(data, dict) and data.get("version") == config.SAVE_VERSION
                    and all(k in data for k in _REQUIRED)):
                float(data["game_t"]), int(data["kills"])
                return data
        except (OSError, ValueError, TypeError):
            pass
        return None

    def info(self, slot: int | str) -> SlotInfo | None:
        """Summary of a slot, or None when it is empty or corrupt."""
        data = self.load(slot)
        if data is None:
            return None
        thumb = self.thumb_path(slot)
        try:
            saved_at = float(data.get("saved_at") or self.json_path(slot).stat().st_mtime)
        except (OSError, TypeError, ValueError):
            saved_at = 0.0
        return SlotInfo(slot, float(data["game_t"]), int(data["kills"]), saved_at,
                        thumb if thumb.exists() else None)

    def list(self) -> list[SlotInfo | None]:
        """One entry per slot 1..SAVE_SLOTS: its SlotInfo, or None when empty."""
        return [self.info(i) for i in range(1, config.SAVE_SLOTS + 1)]

    # -- writing ----------------------------------------------------------------------------------------
    def save(self, slot: int | str, data: dict, thumb: pygame.Surface | None = None) -> bool:
        """Write the save (stamped with `saved_at`) and its thumbnail; False when the disk refused."""
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            path = self.json_path(slot)
            tmp = path.with_name(path.name + ".tmp")
            tmp.write_text(json.dumps({**data, "saved_at": time.time()}, separators=(",", ":")), encoding="utf-8")
            tmp.replace(path)
            png = self.thumb_path(slot)
            if thumb is not None:
                pygame.image.save(thumb, str(png))
            else:
                png.unlink(missing_ok=True)
            return True
        except (OSError, ValueError, pygame.error):
            return False

    def save_game(self, slot: int | str, game) -> bool:
        """snapshot + thumbnail of `game` into a slot."""
        try:
            return self.save(slot, snapshot(game), render_thumbnail(game))
        except (ValueError, pygame.error):
            return False

    def delete(self, slot: int | str) -> None:
        """Remove a slot's files (no error when they are not there)."""
        for path in (self.json_path(slot), self.thumb_path(slot)):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass

    # -- the autosave -----------------------------------------------------------------------------------
    def autosave(self, game) -> bool:
        """Write the autosave of `game`."""
        return self.save_game(AUTO, game)

    def has_autosave(self) -> bool:
        return self.load(AUTO) is not None

    def autosave_info(self) -> SlotInfo | None:
        return self.info(AUTO)

    def load_autosave(self) -> dict | None:
        return self.load(AUTO)

    def delete_autosave(self) -> None:
        self.delete(AUTO)
