"""Enemy swarm as numpy struct-of-arrays, difficulty curve and spawn timer."""
from __future__ import annotations

import math

import numpy as np
import pygame

from ascensus import config, view
from ascensus.ui.widgets import draw_text


def _center() -> np.ndarray:
    """Screen position of the player (read at call time so resizing works)."""
    return np.array((view.W / 2, view.H / 2))


_FIELDS = ("pos", "hp", "max_hp", "dmg", "speed", "flash", "radius", "boss")


def difficulty(game_t: float) -> tuple[float, float, float, float]:
    """(hp, damage, speed, spawn_interval) after game_t seconds of game time."""
    m = game_t / 60.0
    hp = config.ENEMY_HP_BASE * (1 + config.ENEMY_HP_PER_MIN * m)
    dmg = config.ENEMY_DMG_BASE * (1 + config.ENEMY_DMG_PER_MIN * m)
    speed = min(config.ENEMY_SPEED_BASE * (1 + config.ENEMY_SPEED_PER_MIN * m),
                config.ENEMY_SPEED_MAX)
    interval = max(config.SPAWN_MIN_INTERVAL, 1.0 / (1 + config.SPAWN_RATE_PER_MIN * m))
    return hp, dmg, speed, interval


class Spawner:
    """Time accumulator: update() returns how many enemies to spawn this step."""

    def __init__(self) -> None:
        self.acc = 0.0
        self.bosses_spawned = 0

    def update(self, dt: float, game_t: float) -> int:
        self.acc += dt
        interval = difficulty(game_t)[3]
        n = int(self.acc // interval)
        self.acc -= n * interval
        return n

    def bosses_due(self, game_t: float) -> int:
        """How many bosses should spawn now (one per BOSS_INTERVAL of game time, 5:00, 10:00, ...)."""
        n = max(int(game_t // config.BOSS_INTERVAL) - self.bosses_spawned, 0)
        self.bosses_spawned += n
        return n

    def to_dict(self) -> dict:
        """Saved state: the spawn accumulator and how many bosses have spawned (the boss timer)."""
        return {"acc": self.acc, "bosses_spawned": self.bosses_spawned}

    def load_dict(self, data: dict) -> None:
        """Restore from to_dict(); raises ValueError / KeyError / TypeError on bad data."""
        acc, bosses = float(data["acc"]), int(data["bosses_spawned"])
        if not math.isfinite(acc) or acc < 0 or bosses < 0:
            raise ValueError("bad spawner state")
        self.acc, self.bosses_spawned = acc, bosses


class Swarm:
    """All enemies (and bosses); world positions in pixels."""

    def __init__(self, rng: np.random.Generator | None = None) -> None:
        self.rng = rng or np.random.default_rng()
        self.pos = np.zeros((0, 2))
        self.hp = np.zeros(0)
        self.max_hp = np.zeros(0)
        self.dmg = np.zeros(0)
        self.speed = np.zeros(0)
        self.flash = np.zeros(0)
        self.radius = np.zeros(0)
        self.boss = np.zeros(0, dtype=bool)
        self.last_removed_max_hp = 0.0       # summed max hp of the last remove_dead() batch
        self.last_removed_bosses = 0         # bosses in the last remove_dead() batch
        self.damage_dealt = 0.0              # stats: hp actually removed by pulses
        self.bosses_killed = 0               # stats
        self._scratch: tuple[np.ndarray, ...] | None = None

    def __len__(self) -> int:
        return len(self.hp)

    def normal_count(self) -> int:
        """Enemies that count toward the max-alive cap (bosses are exempt)."""
        return len(self) - int(self.boss.sum())

    def _add(self, p: np.ndarray, hp: float, dmg: float, speed: float,
             radius: float, boss: bool) -> None:
        self.pos = np.vstack((self.pos, p))
        self.hp = np.append(self.hp, hp)
        self.max_hp = np.append(self.max_hp, hp)
        self.dmg = np.append(self.dmg, dmg)
        self.speed = np.append(self.speed, speed)
        self.flash = np.append(self.flash, 0.0)
        self.radius = np.append(self.radius, radius)
        self.boss = np.append(self.boss, boss)

    def _spawn_point(self, player_pos: np.ndarray, extra: float = 0.0) -> np.ndarray:
        ang = self.rng.uniform(0, 2 * math.pi)
        dist = math.hypot(view.W, view.H) / 2 + config.ENEMY_SPAWN_MARGIN + extra
        return player_pos + dist * np.array((math.cos(ang), math.sin(ang)))

    def spawn(self, player_pos: np.ndarray, game_t: float) -> bool:
        """Add one enemy just off-screen at a random angle (no-op at the cap)."""
        if self.normal_count() >= config.ENEMY_MAX_ALIVE:
            return False
        hp, dmg, speed, _ = difficulty(game_t)
        self._add(self._spawn_point(player_pos), hp, dmg, speed, config.ENEMY_RADIUS, False)
        return True

    def spawn_boss(self, player_pos: np.ndarray, game_t: float) -> None:
        """Add a boss just off-screen (not counted toward the cap)."""
        hp, dmg, speed, _ = difficulty(game_t)
        self._add(self._spawn_point(player_pos, config.BOSS_RADIUS), hp * config.BOSS_HP_MULT,
                  dmg * config.BOSS_DMG_MULT, speed * config.BOSS_SPEED_MULT,
                  config.BOSS_RADIUS, True)

    def update(self, dt: float, player_pos: np.ndarray) -> None:
        """Chase the player, separate overlapping enemies, push them out of the player."""
        if not len(self):
            return
        d = player_pos - self.pos
        n = np.maximum(np.hypot(d[:, 0], d[:, 1]), 1e-6)
        self.pos += d / n[:, None] * (self.speed * dt)[:, None]
        self.flash = np.maximum(self.flash - dt, 0.0)
        self._separate()
        self._push_out_of_player(player_pos)

    def _scratch_views(self, n: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """n x n views of reusable buffers (avoids allocating large temporaries every frame)."""
        if self._scratch is None or self._scratch[0].shape[0] < n:
            cap = max(n, 256)
            self._scratch = (np.empty((cap, cap)), np.empty((cap, cap)), np.empty((cap, cap)),
                             np.empty((cap, cap), dtype=bool))
        return tuple(a[:n, :n] for a in self._scratch)

    def _separate(self) -> None:
        """Pairwise numpy separation: overlapping pairs move apart, weighted by mass ~ r^2.

        One n x n broad phase finds the near pairs; SEPARATION_ITERS passes then run on those pairs only.
        """
        n = len(self)
        if n < 2:
            return
        r, mass = self.radius, self.radius ** 2
        dx, dy, d2, near = self._scratch_views(n)
        x, y = self.pos[:, 0], self.pos[:, 1]
        np.subtract(x[:, None], x[None, :], out=dx)
        np.subtract(y[:, None], y[None, :], out=dy)
        np.multiply(dx, dx, out=d2)
        np.multiply(dy, dy, out=dy)
        d2 += dy
        np.add(r[:, None], r[None, :], out=dx)                # dx now holds r_i + r_j + margin, squared
        dx += config.SEPARATION_MARGIN
        dx *= dx
        np.less(d2, dx, out=near)
        ii, jj = np.nonzero(near)
        keep = ii != jj
        ii, jj = ii[keep], jj[keep]
        if not len(ii):
            return
        reach = r[ii] + r[jj]
        share = mass[jj] / (mass[ii] + mass[jj])
        for _ in range(config.SEPARATION_ITERS):
            ddx = self.pos[ii, 0] - self.pos[jj, 0]
            ddy = self.pos[ii, 1] - self.pos[jj, 1]
            dist = np.hypot(ddx, ddy)
            same = dist < 1e-6                       # exactly coincident: split along the x axis
            ddx = np.where(same, np.where(ii > jj, 1.0, -1.0), ddx)
            push = np.maximum(reach - dist, 0.0) * share / np.where(same, 1.0, dist)
            self.pos[:, 0] += np.bincount(ii, push * ddx, minlength=n)
            self.pos[:, 1] += np.bincount(ii, push * ddy, minlength=n)

    def _away_from(self, idx: np.ndarray, player_pos: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Unit vectors from the player to enemies `idx` (+x when exactly on top) and distances."""
        d = self.pos[idx] - player_pos
        dist = np.hypot(d[:, 0], d[:, 1])
        zero = dist < 1e-6
        d[zero] = (1.0, 0.0)
        dist = np.where(zero, 1.0, dist)
        return d / dist[:, None], dist

    def _push_out_of_player(self, player_pos: np.ndarray) -> None:
        """Enemies overlapping the player are moved out to r_p + r_e (the player never moves)."""
        d = self.pos - player_pos
        reach = config.PLAYER_RADIUS + self.radius
        inside = np.flatnonzero(np.hypot(d[:, 0], d[:, 1]) < reach)
        if len(inside):
            unit, _ = self._away_from(inside, player_pos)
            self.pos[inside] = player_pos + unit * reach[inside][:, None]

    def _touching(self, player_pos: np.ndarray, r: float) -> np.ndarray:
        d = self.pos - player_pos
        return np.hypot(d[:, 0], d[:, 1]) <= r + self.radius + config.CONTACT_SLOP

    def contact_damage(self, player_pos: np.ndarray, r: float) -> float:
        """Max damage among enemies touching a player circle of radius r (0 if none)."""
        if not len(self):
            return 0.0
        touching = self._touching(player_pos, r)
        return float(self.dmg[touching].max()) if touching.any() else 0.0

    def knockback(self, player_pos: np.ndarray, r: float) -> int:
        """Shove every touching enemy KNOCKBACK_DIST px straight away from the player."""
        if not len(self):
            return 0
        idx = np.flatnonzero(self._touching(player_pos, r))
        if len(idx):
            unit, _ = self._away_from(idx, player_pos)
            self.pos[idx] += unit * config.KNOCKBACK_DIST
        return len(idx)

    def damage_where(self, hit_mask: np.ndarray, dmg: float, player_pos: np.ndarray) -> int:
        """Damage every enemy whose screen cell is set in hit_mask; returns the count hit.

        Bosses use their whole bounding box: any set cell inside it counts.
        """
        if not len(self):
            return 0
        s = (self.pos - player_pos + _center()).astype(np.int32)
        rows, cols = hit_mask.shape
        cx, cy = s[:, 0] // config.HIT_CELL, s[:, 1] // config.HIT_CELL
        ok = (s[:, 0] >= 0) & (s[:, 1] >= 0) & (cx < cols) & (cy < rows)
        hit = np.zeros(len(self), dtype=bool)
        hit[ok] = hit_mask[cy[ok], cx[ok]]
        for i in np.flatnonzero(self.boss):
            r, cell = self.radius[i], config.HIT_CELL
            x0 = max(int(s[i, 0] - r) // cell, 0)
            x1 = min(int(s[i, 0] + r) // cell, cols - 1)
            y0 = max(int(s[i, 1] - r) // cell, 0)
            y1 = min(int(s[i, 1] + r) // cell, rows - 1)
            hit[i] = x0 <= x1 and y0 <= y1 and bool(hit_mask[y0:y1 + 1, x0:x1 + 1].any())
        self.damage_dealt += float(np.minimum(self.hp[hit], dmg).sum())
        self.hp[hit] -= dmg
        self.flash[hit] = config.ENEMY_FLASH
        return int(hit.sum())

    def remove_dead(self) -> int:
        """Drop enemies with hp <= 0 (boolean-mask compression); returns how many died.

        `last_removed_max_hp` is set to the summed max hp of the enemies just removed (for XP).
        """
        keep = self.hp > 0
        dead = len(self) - int(keep.sum())
        self.last_removed_max_hp = float(self.max_hp[~keep].sum()) if dead else 0.0
        self.last_removed_bosses = int(self.boss[~keep].sum()) if dead else 0
        if dead:
            self.bosses_killed += int(self.boss[~keep].sum())
            for name in _FIELDS:
                setattr(self, name, getattr(self, name)[keep])
        return dead

    def to_dict(self) -> dict:
        """The enemy arrays as plain lists (boss flags included) plus the stats counters."""
        out: dict = {name: getattr(self, name).tolist() for name in _FIELDS}
        out["damage_dealt"] = float(self.damage_dealt)
        out["bosses_killed"] = int(self.bosses_killed)
        return out

    def load_dict(self, data: dict) -> None:
        """Replace the enemies from to_dict(); raises ValueError / KeyError / TypeError on bad data.

        Nothing changes when the data is malformed (all arrays are built before any is assigned).
        """
        arrays: dict[str, np.ndarray] = {}
        for name in _FIELDS:
            arrays[name] = np.array(data[name], dtype=bool if name == "boss" else float)
        n = len(arrays["hp"])
        if n == 0 and arrays["pos"].size == 0:
            arrays["pos"] = np.zeros((0, 2))
        if arrays["pos"].shape != (n, 2) or any(len(arrays[name]) != n for name in _FIELDS):
            raise ValueError("enemy arrays differ in length")
        if not all(np.isfinite(arrays[name]).all() for name in _FIELDS if name != "boss"):
            raise ValueError("non-finite enemy value")
        damage, killed = float(data.get("damage_dealt", 0.0)), int(data.get("bosses_killed", 0))
        for name in _FIELDS:
            setattr(self, name, arrays[name])
        self.damage_dealt, self.bosses_killed = damage, killed
        self.last_removed_max_hp, self.last_removed_bosses = 0.0, 0

    def draw(self, screen: pygame.Surface, player_pos: np.ndarray) -> None:
        """Draw on-screen enemies (darker as hp drops, white while flashing) with red hp numbers."""
        if not len(self):
            return
        s = self.pos - player_pos + _center()
        m = self.radius + config.ENEMY_CULL_MARGIN
        vis = np.flatnonzero((s[:, 0] > -m) & (s[:, 0] < view.W + m)
                             & (s[:, 1] > -m) & (s[:, 1] < view.H + m))
        if not len(vis):
            return
        k = config.ENEMY_DARKEST + (1 - config.ENEMY_DARKEST) * np.clip(self.hp[vis] / self.max_hp[vis], 0.0, 1.0)
        base = np.where(self.boss[vis, None], config.BOSS_COLOR, config.ENEMY_COLOR)
        cols = (base * k[:, None]).astype(np.int32).tolist()
        flashing = (self.flash[vis] > 0).tolist()
        xs, ys = s[vis, 0].astype(np.int32).tolist(), s[vis, 1].astype(np.int32).tolist()
        rs = self.radius[vis].astype(np.int32).tolist()
        hps = np.ceil(self.hp[vis]).astype(np.int64).tolist()
        bosses = self.boss[vis].tolist()
        text_col = config.ENEMY_HP_TEXT_COLOR
        for col, fl, x, y, r, hp, boss in zip(cols, flashing, xs, ys, rs, hps, bosses):
            pygame.draw.circle(screen, config.ENEMY_FLASH_COLOR if fl else col, (x, y), r)
            draw_text(screen, str(hp), config.BOSS_HP_FONT if boss else config.ENEMY_HP_FONT,
                      text_col, (x, y + r + 1), "midtop")
