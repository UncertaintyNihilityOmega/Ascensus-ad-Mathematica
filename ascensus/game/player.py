"""The player: a circle at the window centre; the world position moves."""
from __future__ import annotations

import math

import numpy as np
import pygame

from ascensus import config, view
from ascensus.ui.widgets import draw_text


class Player:
    """World position, HP and post-hit invulnerability."""

    def __init__(self) -> None:
        self.pos = np.zeros(2)
        self.max_hp = float(config.PLAYER_HP)
        self.hp = self.max_hp
        self.iframes = 0.0
        self.facing = np.array((1.0, 0.0))     # last non-zero move direction (unit vector)
        self.dash_left = 0.0                   # seconds of dash remaining
        self.dash_cd = 0.0
        self.dash_count = 0                    # dashes performed (for later stats)
        d = (config.PLAYER_RADIUS + config.PLAYER_RING_EXTRA) * 2
        self._ring = pygame.Surface((d, d), pygame.SRCALPHA)
        c = d // 2
        for i, r in enumerate((c - 1, c - 3, c - 5)):
            col = (*config.PLAYER_RING_COLOR, config.PLAYER_RING_ALPHA // (i + 1))
            pygame.draw.circle(self._ring, col, (c, c), r, 2)

    @property
    def alive(self) -> bool:
        return self.hp > 0

    @property
    def dashing(self) -> bool:
        return self.dash_left > 0

    def start_dash(self) -> bool:
        """Dash toward the facing direction (ignored mid-dash or while on cooldown)."""
        if self.dashing or self.dash_cd > 0 or not self.alive:
            return False
        self.dash_left = config.DASH_TIME
        self.dash_cd = config.DASH_COOLDOWN
        self.dash_count += 1
        return True

    def face(self, vec: tuple[float, float]) -> None:
        """Turn toward a (dx, dy) vector (any length, ignored when zero or mid-dash)."""
        n = math.hypot(vec[0], vec[1])
        if n > 0 and not self.dashing:
            self.facing = np.array((vec[0], vec[1])) / n

    def update(self, dt: float, direction: tuple[float, float],
               face: tuple[float, float] | None = None) -> None:
        """Move along a (dx, dy) screen direction (y down); diagonals are normalized.

        `face` (Mouse mode: toward the cursor) overrides the facing the walk would set.
        A dash overrides walking; the player regenerates slowly and never exceeds max HP.
        """
        dx, dy = direction
        n = math.hypot(dx, dy)
        if n > 0:
            self.facing = np.array((dx, dy)) / n
        if face is not None:
            self.face(face)
        if self.dashing:
            step = min(dt, self.dash_left)
            self.pos += self.facing * (config.DASH_DIST / config.DASH_TIME) * step
            self.dash_left = max(0.0, self.dash_left - dt)
        elif n > 0:
            self.pos += self.facing * config.PLAYER_SPEED * dt
        self.dash_cd = max(0.0, self.dash_cd - dt)
        self.iframes = max(0.0, self.iframes - dt)
        if self.alive:
            self.hp = min(self.max_hp, self.hp + config.PLAYER_REGEN_PER_MIN / 60.0 * dt)

    def raise_max_hp(self, amount: float) -> None:
        """Max HP upgrade: raise the cap by `amount` and heal that much (never above the cap)."""
        self.max_hp += amount
        self.hp = min(self.max_hp, self.hp + amount)

    def take_damage(self, amount: float) -> bool:
        """Apply a hit unless invulnerable (i-frames or dashing); returns True if it landed."""
        if amount <= 0 or self.iframes > 0 or self.dashing or not self.alive:
            return False
        self.hp = max(0.0, self.hp - amount)
        self.iframes = config.PLAYER_IFRAMES
        return True

    def draw(self, screen: pygame.Surface) -> None:
        center = view.center()
        ring_r = config.PLAYER_RADIUS + config.PLAYER_RING_EXTRA - 3     # the middle ring
        if not (self.iframes > 0 and int(self.iframes * config.PLAYER_BLINK_HZ * 2) % 2 == 1):
            screen.blit(self._ring, self._ring.get_rect(center=center))
            pygame.draw.circle(screen, config.PLAYER_COLOR, center, config.PLAYER_RADIUS)
            f = self.facing
            base = np.array(center) + f * ring_r
            tip = base + f * config.PLAYER_NOTCH_LEN
            w = np.array((-f[1], f[0])) * config.PLAYER_NOTCH_HALF
            pygame.draw.polygon(screen, config.PLAYER_RING_COLOR,
                                [tuple(tip), tuple(base + w), tuple(base - w)])
        draw_text(screen, str(math.ceil(self.hp)), config.PLAYER_HP_FONT, config.PLAYER_HP_TEXT_COLOR,
                  (center[0], center[1] + ring_r + config.PLAYER_NOTCH_LEN + 2), "midtop")
