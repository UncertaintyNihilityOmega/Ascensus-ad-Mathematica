"""The Saves page: a grid of slot cards (thumbnail, run time, date, kills, Save / Delete).

Opened from the main menu (game=None: loading only) or from Pause (game given: Save is enabled and loading
asks first because the current run is lost). `back` is a zero-argument callable returning the Scene the Back
button leads to. Loading puts the restored GameScene into `next_scene`.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

import pygame

from . import config, view
from .equations import USE_CONFIG, resolve_save_path
from .savegame import SlotInfo, SlotStore, restore
from .scenes import Scene
from .stats import mmss
from .ui.widgets import Button, draw_text

ASPECT = config.THUMB_SIZE[0] / config.THUMB_SIZE[1]


def grid_shape(width: int) -> tuple[int, int]:
    """(columns, rows) of the slot grid: 3 x 2, or 2 x 3 when the window is narrower than SAVES_NARROW_W."""
    cols = 3 if width >= config.SAVES_NARROW_W else 2
    return cols, -(-config.SAVE_SLOTS // cols)


def shadow_text(surf: pygame.Surface, text: str, size: int, color: tuple[int, ...], pos: tuple[int, int],
                anchor: str = "topleft", **kw) -> pygame.Rect:
    """draw_text with a dark 2 px drop shadow (readable on top of thumbnails)."""
    x, y = pos
    draw_text(surf, text, size, config.SAVES_SHADOW, (x + 2, y + 2), anchor, **kw)
    return draw_text(surf, text, size, color, pos, anchor, **kw)


def _draw_button(surf: pygame.Surface, rect: pygame.Rect, label: str, enabled: bool, armed: bool = False) -> None:
    hover = enabled and rect.collidepoint(pygame.mouse.get_pos())
    fill = config.BUTTON_HOVER_FILL if hover else config.BUTTON_FILL
    border = config.DANGER_COLOR if armed else (config.ACCENT_COLOR if hover else config.BUTTON_BORDER)
    if not enabled:
        fill, border = config.BG_COLOR, config.BUTTON_FILL
    pygame.draw.rect(surf, fill, rect, border_radius=6)
    pygame.draw.rect(surf, border, rect, width=2, border_radius=6)
    color = config.DANGER_COLOR if armed else (config.TEXT_COLOR if enabled else config.DIM_TEXT_COLOR)
    draw_text(surf, label, config.SAVES_BTN_FONT, color, rect.center, "center",
              max_w=rect.w - 10, min_size=config.MIN_TEXT_SIZE)


class SavesScene(Scene):
    """Slots 1..6 as cards. `game` is the paused GameScene (or None from the main menu)."""

    def __init__(self, game, back: Callable[[], Scene], store: SlotStore | None = None,
                 save_path: Path | None | str = USE_CONFIG) -> None:
        super().__init__()
        self.game = game
        self.back = back
        self.store = store if store is not None else SlotStore()
        self.save_path = resolve_save_path(save_path)
        self.back_btn = Button(pygame.Rect(0, 0, *config.PAGE_BACK_SIZE), "Back", size=config.BODY_FONT + 2)
        self.infos: list[SlotInfo | None] = []
        self._images: dict[int, pygame.Surface | None] = {}        # slot -> thumbnail png (loaded lazily)
        self._scaled: dict[tuple[int, int, int], pygame.Surface] = {}
        self.armed: tuple[int, float] | None = None                # (slot, seconds left) Delete awaiting 2nd click
        self.dialog: tuple[str, int] | None = None                 # ("load" | "overwrite", slot)
        self.note: tuple[str, bool, float] | None = None           # (text, is_error, seconds left)
        self.cards: list[pygame.Rect] = []
        self.dialog_rects: dict[str, pygame.Rect] = {}
        self.refresh()
        self.on_resize()

    # -- model ---------------------------------------------------------------------------------------
    def refresh(self) -> None:
        """Re-read the slot files."""
        self.infos = self.store.list()
        self._images.clear()
        self._scaled.clear()

    def _say(self, text: str, error: bool = False) -> None:
        self.note = (text, error, config.SAVES_NOTE_TIME)

    def save_slot(self, slot: int) -> bool:
        """Write the current run into `slot` (the caller has confirmed any overwrite)."""
        if self.game is None:
            return False
        ok = self.store.save_game(slot, self.game)
        self.refresh()
        self._say(f"Saved to slot {slot}" if ok else f"Could not save slot {slot}", not ok)
        return ok

    def delete_slot(self, slot: int) -> None:
        self.store.delete(slot)
        self.armed = None
        self.refresh()

    def load_slot(self, slot: int) -> bool:
        """Restore the slot and ask the main loop to switch to it; False (with a note) when unreadable."""
        data = self.store.load(slot)
        try:
            if data is None:
                raise ValueError("empty slot")
            scene = restore(data, save_path=self.save_path)
        except ValueError:
            self._say(f"Could not load slot {slot}", True)
            return False
        self.next_scene = scene
        return True

    def leave(self) -> None:
        self.next_scene = self.back()

    # -- layout --------------------------------------------------------------------------------------
    def on_resize(self) -> None:
        m, gap = config.PAGE_MARGIN, config.SAVES_GAP
        W, H = view.W, view.H
        self.back_btn.rect.topright = (W - m, m)
        cols, rows = grid_shape(W)
        top = config.PAGE_HEADER_H
        cw = (W - 2 * m - (cols - 1) * gap) // cols
        ch = (H - top - m - (rows - 1) * gap) // rows
        self.cards = [pygame.Rect(m + (i % cols) * (cw + gap), top + (i // cols) * (ch + gap), cw, ch)
                      for i in range(config.SAVE_SLOTS)]
        self._scaled.clear()
        bw, bh = 360, 190
        box = pygame.Rect(0, 0, min(bw, W - 20), bh)
        box.center = (W // 2, H // 2)
        half = (box.w - 3 * config.SAVES_PAD * 2) // 2
        y = box.bottom - config.SAVES_PAD * 2 - config.SAVES_BTN_H
        self.dialog_rects = {"box": box,
                             "ok": pygame.Rect(box.left + 12, y, half, config.SAVES_BTN_H),
                             "cancel": pygame.Rect(box.right - 12 - half, y, half, config.SAVES_BTN_H)}

    def card_parts(self, i: int) -> dict[str, pygame.Rect]:
        """Rects of card i (0-based): card, thumb (16:9, fitted), save, delete."""
        card, pad, bh = self.cards[i], config.SAVES_PAD, config.SAVES_BTN_H
        area = pygame.Rect(card.x + pad, card.y + pad, card.w - 2 * pad, max(card.h - 3 * pad - bh, 1))
        tw, th = (area.w, int(area.w / ASPECT)) if area.w / ASPECT <= area.h else (int(area.h * ASPECT), area.h)
        thumb = pygame.Rect(0, 0, max(tw, 1), max(th, 1))
        thumb.center = area.center
        half = (card.w - 3 * pad) // 2
        y = card.bottom - pad - bh
        return {"card": card, "thumb": thumb,
                "save": pygame.Rect(card.x + pad, y, half, bh),
                "delete": pygame.Rect(card.right - pad - half, y, half, bh)}

    # -- events --------------------------------------------------------------------------------------
    def handle_event(self, e: pygame.event.Event) -> None:
        if self.dialog is not None:
            self._dialog_event(e)
            return
        if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
            self.leave()
            return
        if self.back_btn.handle_event(e):
            self.leave()
            return
        if not (e.type == pygame.MOUSEBUTTONDOWN and e.button == 1):
            return
        armed = self.armed[0] if self.armed else None
        self.armed = None                                       # any click elsewhere cancels a pending delete
        for i in range(config.SAVE_SLOTS):
            slot, parts, info = i + 1, self.card_parts(i), self.infos[i]
            if parts["save"].collidepoint(e.pos) and self.game is not None:
                if info is None:
                    self.save_slot(slot)
                else:
                    self.dialog = ("overwrite", slot)
                return
            if parts["delete"].collidepoint(e.pos) and info is not None:
                if armed == slot:
                    self.delete_slot(slot)
                else:
                    self.armed = (slot, config.DELETE_CONFIRM_TIME)
                return
            if parts["thumb"].collidepoint(e.pos) and info is not None:
                if self.game is None:
                    self.load_slot(slot)
                else:
                    self.dialog = ("load", slot)
                return

    def _dialog_event(self, e: pygame.event.Event) -> None:
        kind, slot = self.dialog
        if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
            self.dialog = None
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            if self.dialog_rects["ok"].collidepoint(e.pos):
                self.dialog = None
                self.save_slot(slot) if kind == "overwrite" else self.load_slot(slot)
            elif self.dialog_rects["cancel"].collidepoint(e.pos):
                self.dialog = None

    def update(self, dt: float) -> None:
        if self.armed is not None:
            slot, left = self.armed
            self.armed = (slot, left - dt) if left - dt > 0 else None
        if self.note is not None:
            text, error, left = self.note
            self.note = (text, error, left - dt) if left - dt > 0 else None

    # -- drawing -------------------------------------------------------------------------------------
    def _thumb_image(self, slot: int, size: tuple[int, int]) -> pygame.Surface | None:
        """The slot's thumbnail scaled to `size` (cached), or None when it has no png."""
        if slot not in self._images:
            info = self.infos[slot - 1]
            try:
                self._images[slot] = pygame.image.load(str(info.thumb)) if info and info.thumb else None
            except (pygame.error, OSError):
                self._images[slot] = None
        img = self._images[slot]
        if img is None:
            return None
        key = (slot, *size)
        if key not in self._scaled:
            self._scaled[key] = pygame.transform.smoothscale(img, size)
        return self._scaled[key]

    def draw(self, screen: pygame.Surface) -> None:
        screen.fill(config.BG_COLOR)
        m = config.PAGE_MARGIN
        title = draw_text(screen, "Saves", config.PAGE_TITLE_FONT, config.ACCENT_COLOR, (m, m))
        self.back_btn.draw(screen)
        hint = "Click a save to load it" if self.game is None else "Save the run, or click a save to load it"
        text, color = hint, config.DIM_TEXT_COLOR
        if self.note is not None:
            text, color = self.note[0], config.DANGER_COLOR if self.note[1] else config.ACCENT_COLOR
        draw_text(screen, text, config.BODY_FONT, color, (title.right + 24, title.centery), "midleft",
                  max_w=max(self.back_btn.rect.left - title.right - 48, 60), min_size=config.MIN_TEXT_SIZE)
        for i in range(config.SAVE_SLOTS):
            self._draw_card(screen, i)
        if self.dialog is not None:
            self._draw_dialog(screen)

    def _draw_card(self, screen: pygame.Surface, i: int) -> None:
        slot, parts, info = i + 1, self.card_parts(i), self.infos[i]
        card, thumb, pad = parts["card"], parts["thumb"], config.SAVES_PAD
        pygame.draw.rect(screen, config.BUTTON_FILL, card, border_radius=8)
        pygame.draw.rect(screen, config.BUTTON_BORDER, card, width=2, border_radius=8)
        img = self._thumb_image(slot, thumb.size) if info else None
        if img is not None:
            screen.blit(img, thumb)
        else:
            pygame.draw.rect(screen, config.INPUT_FILL, thumb)
        hover = info is not None and self.dialog is None and thumb.collidepoint(pygame.mouse.get_pos())
        pygame.draw.rect(screen, config.ACCENT_COLOR if hover else config.BUTTON_BORDER, thumb, width=2)
        if info is None:
            draw_text(screen, "Empty", config.BUTTON_FONT, config.DIM_TEXT_COLOR, thumb.center, "center",
                      max_w=thumb.w - 12, min_size=config.MIN_TEXT_SIZE)
            draw_text(screen, f"Slot {slot}", config.SAVES_SMALL_FONT, config.DIM_TEXT_COLOR,
                      (thumb.left + 8, thumb.top + 6), max_w=max(thumb.w // 2, 20), min_size=config.MIN_TEXT_SIZE)
        else:
            shadow_text(screen, mmss(info.game_t), config.SAVES_TIME_FONT, config.TEXT_COLOR,
                        (thumb.left + 8, thumb.top + 4), max_w=int(thumb.w * 0.62), min_size=20)
            shadow_text(screen, f"Slot {slot}", config.SAVES_SMALL_FONT, config.DIM_TEXT_COLOR,
                        (thumb.right - 8, thumb.top + 8), "topright", max_w=int(thumb.w * 0.3),
                        min_size=config.MIN_TEXT_SIZE)
            lh = config.SAVES_SMALL_FONT
            shadow_text(screen, f"{info.kills} kills", config.SAVES_SMALL_FONT, config.TEXT_COLOR,
                        (thumb.left + 8, thumb.bottom - 6), "bottomleft", max_w=thumb.w - 16,
                        min_size=config.MIN_TEXT_SIZE)
            shadow_text(screen, info.date_text(), config.SAVES_SMALL_FONT, config.DIM_TEXT_COLOR,
                        (thumb.left + 8, thumb.bottom - 6 - lh), "bottomleft", max_w=thumb.w - 16,
                        min_size=config.MIN_TEXT_SIZE)
        enabled = self.game is not None
        _draw_button(screen, parts["save"], "Save", enabled)
        armed = self.armed is not None and self.armed[0] == slot
        _draw_button(screen, parts["delete"], "Sure?" if armed else "Delete", info is not None, armed)

    def _draw_dialog(self, screen: pygame.Surface) -> None:
        kind, slot = self.dialog
        dim = pygame.Surface((view.W, view.H), pygame.SRCALPHA)
        dim.fill((0, 0, 0, config.PAUSE_DIM_ALPHA))
        screen.blit(dim, (0, 0))
        box = self.dialog_rects["box"]
        pygame.draw.rect(screen, config.BUTTON_FILL, box, border_radius=10)
        pygame.draw.rect(screen, config.ACCENT_COLOR, box, width=2, border_radius=10)
        if kind == "load":
            head, body, ok = f"Load slot {slot}?", "Current run will be lost", "Load"
        else:
            head, body, ok = f"Overwrite slot {slot}?", "The saved run will be replaced", "Overwrite"
        w = box.w - 24
        draw_text(screen, head, config.SUBTITLE_FONT, config.TEXT_COLOR, (box.centerx, box.top + 38), "center",
                  max_w=w, min_size=config.MIN_TEXT_SIZE)
        draw_text(screen, body, config.BODY_FONT, config.DANGER_COLOR if kind == "load" else config.DIM_TEXT_COLOR,
                  (box.centerx, box.top + 80), "center", max_w=w, min_size=config.MIN_TEXT_SIZE)
        _draw_button(screen, self.dialog_rects["ok"], ok, True)
        _draw_button(screen, self.dialog_rects["cancel"], "Cancel", True)
