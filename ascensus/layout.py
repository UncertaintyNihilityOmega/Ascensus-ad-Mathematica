"""Bottom-of-screen layout shared by the input box and the upgrades panel (they must never overlap)."""
from __future__ import annotations

import pygame

from . import config


def game_layout(left_edge: int, w: int, h: int) -> tuple[pygame.Rect, int]:
    """Place the input box and the upgrades panel for a w x h view.

    `left_edge` is the right edge of the sidebar (its panel, or its collapsed tab). The input box is
    centred in the free space between the sidebar and the panel and is at least INPUT_MIN_W wide. If
    that space is too small the panel stacks ABOVE the input box instead (the box then uses all the
    room right of the sidebar). Returns (input rect, bottom y of the upgrades panel).
    """
    iw, ih = config.INPUT_SIZE
    m, gap = config.HUD_MARGIN, config.LAYOUT_GAP
    y = h - config.INPUT_BOTTOM_MARGIN - ih
    panel_left = w - m - config.UPG_PANEL_W
    free_l, free_r = left_edge + gap, panel_left - gap
    if free_r - free_l >= config.INPUT_MIN_W:                      # side by side
        width = min(iw, free_r - free_l)
        return pygame.Rect(free_l + (free_r - free_l - width) // 2, y, width, ih), h - m
    free_r = w - m                                                 # stacked: panel above the box
    width = max(min(iw, free_r - free_l), 100)
    rect = pygame.Rect(free_l + (free_r - free_l - width) // 2, y, width, ih)
    return rect, rect.top - config.INPUT_ERROR_GAP - gap
