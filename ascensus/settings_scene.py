"""The Settings page: vertical tabs, scrolling rows of label / value / [-] [+] / reset, Reset tab / all."""
from __future__ import annotations

from typing import Callable

import pygame

from . import config, display, settings, view
from .scenes import Scene
from .settings import Setting
from .ui.keyfield import KeyField
from .ui.widgets import Button, IconButton, NumberField, ScrollArea, Tabs, draw_text, fmt_number, get_font

LIVE_KEYS = frozenset({"FULLSCREEN_START", "WINDOW_FRACTION", "UNIT_PX", "GRID_STEP"})   # apply at once
BTN = 30                                                      # square [-] / [+] / reset buttons


def note_text(s: Setting) -> str:
    """The small line under a label: the setting's note plus '(next run)' when it only affects a new run."""
    tail = "(next run)" if s.next_run and s.key not in LIVE_KEYS else ""
    return f"{s.note} {tail}".strip()


def fit_text(text: str, size: int, max_w: int) -> str:
    """Shorten `text` with '..' until it is at most max_w pixels wide."""
    font = get_font(size)
    if font.size(text)[0] <= max_w:
        return text
    while text and font.size(text + "..")[0] > max_w:
        text = text[:-1]
    return text.rstrip() + ".."


def draw_switch(surf: pygame.Surface, rect: pygame.Rect, on: bool) -> None:
    """A pill toggle switch with a round knob (primitives only)."""
    pygame.draw.rect(surf, config.SWITCH_ON_COLOR if on else config.SWITCH_OFF_COLOR, rect,
                     border_radius=rect.h // 2)
    r = rect.h // 2 - 3
    x = rect.right - rect.h // 2 if on else rect.left + rect.h // 2
    pygame.draw.circle(surf, config.TEXT_COLOR, (x, rect.centery), r)


class SettingsScene(Scene):
    """Edit the registry in `settings`. `back` is a zero-argument callable returning the Scene to go to."""

    def __init__(self, back: Callable[[], Scene]) -> None:
        super().__init__()
        self.back = back
        self.tab_names = settings.tabs()
        self.tabs = Tabs(pygame.Rect(0, 0, 10, 10), self.tab_names)
        self.area = ScrollArea(pygame.Rect(0, 0, 10, 10))
        self.back_btn = Button(pygame.Rect(0, 0, *config.PAGE_BACK_SIZE), "Back", size=config.BODY_FONT + 2)
        self.reset_tab_btn = Button(pygame.Rect(0, 0, 150, 40), "Reset tab", size=config.BODY_FONT + 2)
        self.reset_all_btn = Button(pygame.Rect(0, 0, 150, 40), "Reset all", size=config.BODY_FONT + 2)
        self.fields: dict[str, NumberField] = {}
        self.minus: dict[str, IconButton] = {}
        self.plus: dict[str, IconButton] = {}
        self.reset_btn: dict[str, IconButton] = {}
        self.value_rect: dict[str, pygame.Rect] = {}          # switch (bool) or cycle button (choice)
        self.keyfields: dict[str, KeyField] = {}              # key-binding rows (kind "key")
        for s in settings.SETTINGS:
            dummy = pygame.Rect(0, 0, 10, 10)
            self.minus[s.key], self.plus[s.key] = IconButton(dummy, "minus"), IconButton(dummy, "plus")
            self.reset_btn[s.key] = IconButton(dummy, "reset")
            self.value_rect[s.key] = pygame.Rect(dummy)
            if s.kind in ("int", "float"):
                self.fields[s.key] = NumberField(dummy, settings.get(s.key), s.kind == "int", s.min, s.max)
            elif s.kind == "key":
                self.keyfields[s.key] = KeyField(dummy, str(settings.get(s.key)))
        self.on_resize()

    # -- model ---------------------------------------------------------------------------------------
    @property
    def tab(self) -> str:
        return self.tab_names[self.tabs.selected]

    def rows(self) -> list[Setting]:
        """The Setting rows of the selected tab."""
        return settings.settings_for(self.tab)

    def select_tab(self, name: str) -> None:
        self.tabs.selected = self.tab_names.index(name)
        self._tab_changed()

    def _tab_to_next(self, key: str) -> None:
        """Tab: apply the edit and start editing the next numeric row of this tab (wraps around)."""
        keys = [s.key for s in self.rows() if s.key in self.fields]
        f = self.fields[key]
        if f._apply():
            self.set_value(key, f.value)
        else:
            f._end()
        if keys:
            nxt = self.fields[keys[(keys.index(key) + 1) % len(keys)]] if key in keys else self.fields[keys[0]]
            nxt.focus()

    def _tab_changed(self) -> None:
        fk = self.focused_key()
        if fk is not None and self.fields[fk]._apply():      # leaving the tab commits a valid edit
            self.set_value(fk, self.fields[fk].value)
        for f in self.fields.values():
            f.focused = False
        for kf in self.keyfields.values():
            kf.cancel()
        self.area.set_content_height(len(self.rows()) * config.SET_ROW_H)
        self.area.set_scroll(0)
        self._sync_fields()

    def focused_key(self) -> str | None:
        """The key of the number field being edited, if any."""
        return next((k for k, f in self.fields.items() if f.focused), None)

    def _sync_fields(self) -> None:
        for key, f in self.fields.items():
            if not f.focused:
                f.set_value(settings.get(key))
        for key, kf in self.keyfields.items():
            kf.name = str(settings.get(key))

    def _snapshot(self) -> dict[str, object]:
        return {s.key: settings.get(s.key) for s in settings.SETTINGS}

    def _commit(self, before: dict[str, object]) -> list[str]:
        """After a change: save, refresh the fields and apply display settings live. Returns changed keys."""
        changed = [k for k, v in before.items() if settings.get(k) != v]
        if not changed:
            return changed
        settings.save()
        self._sync_fields()
        if "FULLSCREEN_START" in changed:
            display.set_display(config.FULLSCREEN_START)
        elif "WINDOW_FRACTION" in changed and not display.fullscreen:
            display.set_display(False)
        if LIVE_KEYS.intersection(changed):
            self.on_resize()                      # the page itself follows the new size / zoom
        return changed

    def set_value(self, key: str, value) -> None:
        """Apply a typed value (clamped by the registry) and persist."""
        before = self._snapshot()
        settings.set_value(key, value)
        self._commit(before)

    def nudge(self, key: str, direction: int) -> None:
        """The [-] / [+] buttons (toggle for bool, cycle for choice)."""
        s = settings.find(key)
        before = self._snapshot()
        settings.nudge(key, direction)
        self._commit(before)

    def reset_one(self, key: str) -> None:
        before = self._snapshot()
        settings.reset(key)
        self._commit(before)

    def reset_current_tab(self) -> None:
        before = self._snapshot()
        settings.reset_tab(self.tab)
        self._commit(before)

    def reset_everything(self) -> None:
        before = self._snapshot()
        settings.reset_all()
        self._commit(before)

    def leave(self) -> None:
        for f in self.fields.values():
            f.focused = False
        for kf in self.keyfields.values():
            kf.cancel()
        settings.save()
        self.next_scene = self.back()

    # -- layout --------------------------------------------------------------------------------------
    def on_resize(self) -> None:
        m, head = config.PAGE_MARGIN, config.PAGE_HEADER_H
        W, H = view.W, view.H
        longest = max(get_font(config.TAB_FONT).size(n)[0] for n in self.tab_names)
        tab_w = min(longest + 2 * config.TAB_PAD, int(W * 0.34))
        self.tabs.set_rect(pygame.Rect(m, head, tab_w, H - head - m))
        x0 = m + tab_w + m
        bottom = config.SET_BOTTOM_H
        self.area.set_rect(pygame.Rect(x0, head, max(W - m - x0, 100), max(H - head - bottom - m, 60)))
        self.back_btn.rect.topright = (W - m, m)
        self.reset_all_btn.rect.topright = (W - m, self.area.rect.bottom + 12)
        self.reset_tab_btn.rect.topright = (self.reset_all_btn.rect.left - 12, self.area.rect.bottom + 12)
        self.area.set_content_height(len(self.rows()) * config.SET_ROW_H)
        self._sync_fields()

    def layout_row(self, i: int, s: Setting) -> dict[str, pygame.Rect]:
        """Screen rects of row i's parts (scroll applied): row, minus, field/value, plus, reset."""
        rh = config.SET_ROW_H
        a = self.area
        row = a.offset_rect(pygame.Rect(0, i * rh, a.rect.w, rh))
        right = row.right - config.SCROLLBAR_W - 12
        cy = row.centery
        reset = pygame.Rect(right - BTN, cy - BTN // 2, BTN, BTN)
        plus = pygame.Rect(reset.left - 8 - BTN, cy - BTN // 2, BTN, BTN)
        field = pygame.Rect(plus.left - 4 - config.SET_FIELD_W, cy - config.SET_CTRL_H // 2,
                            config.SET_FIELD_W, config.SET_CTRL_H)
        minus = pygame.Rect(field.left - 4 - BTN, cy - BTN // 2, BTN, BTN)
        out = {"row": row, "reset": reset, "plus": plus, "field": field, "minus": minus}
        if s.kind == "bool":
            w, h = config.SET_SWITCH_SIZE
            out["switch"] = pygame.Rect(plus.right - w, cy - h // 2, w, h)
        elif s.kind in ("choice", "key"):
            out["cycle"] = pygame.Rect(minus.left, cy - config.SET_CTRL_H // 2,
                                       plus.right - minus.left, config.SET_CTRL_H)
        return out

    def row_rects(self, key: str) -> dict[str, pygame.Rect]:
        """Screen rects for the row of `key` on the current tab (for tests and the smoke run)."""
        for i, s in enumerate(self.rows()):
            if s.key == key:
                return self.layout_row(i, s)
        raise KeyError(key)

    def _place(self) -> None:
        """Move the persistent widgets to where their rows are right now."""
        for i, s in enumerate(self.rows()):
            r = self.layout_row(i, s)
            self.minus[s.key].set_rect(r["minus"])
            self.plus[s.key].set_rect(r["plus"])
            self.reset_btn[s.key].set_rect(r["reset"])
            self.reset_btn[s.key].enabled = not settings.is_default(s.key)
            self.value_rect[s.key] = r.get("switch") or r.get("cycle") or r["field"]
            if s.key in self.fields:
                self.fields[s.key].set_rect(r["field"])
            if s.key in self.keyfields:
                self.keyfields[s.key].set_rect(r["cycle"])

    # -- events --------------------------------------------------------------------------------------
    def listening_key(self) -> str | None:
        """The key of the key-binding row waiting for a key press, if any."""
        return next((k for k, kf in self.keyfields.items() if kf.listening), None)

    def _bind_key(self, key: str, e: pygame.event.Event) -> bool:
        """Feed an event to a key-binding row; True when the event is used up (key presses always are)."""
        kf = self.keyfields[key]
        name = kf.handle_event(e)
        if name is not None:
            self.set_value(key, name)
        return e.type in (pygame.KEYDOWN, pygame.TEXTINPUT)

    def handle_event(self, e: pygame.event.Event) -> None:
        self._place()
        lk = self.listening_key()
        if lk is not None and e.type in (pygame.KEYDOWN, pygame.TEXTINPUT):
            self._bind_key(lk, e)                              # the next key press is the binding (Esc cancels)
            return
        fk = self.focused_key()
        if fk is not None and e.type in (pygame.KEYDOWN, pygame.TEXTINPUT):
            if e.type == pygame.KEYDOWN and e.key == pygame.K_TAB:
                self._tab_to_next(fk)
            elif self.fields[fk].handle_event(e):              # Enter: apply
                self.set_value(fk, self.fields[fk].value)
            return                                             # Esc only cancels the edit
        if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
            self.leave()
            return
        if self.back_btn.handle_event(e):
            self.leave()
            return
        if self.reset_tab_btn.handle_event(e):
            self.reset_current_tab()
            return
        if self.reset_all_btn.handle_event(e):
            self.reset_everything()
            return
        if self.tabs.handle_event(e):
            self._tab_changed()
            return
        self.area.handle_event(e, mouse_pos=getattr(e, "pos", None))
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            self._click(e)
        elif e.type == pygame.MOUSEWHEEL:
            self._place()

    def _click(self, e: pygame.event.Event) -> None:
        inside = self.area.contains(e.pos)
        for s in self.rows():
            if s.key in self.keyfields:
                if inside or self.keyfields[s.key].listening:
                    self._bind_key(s.key, e)     # click toggles listening; a click elsewhere cancels
        for s in self.rows():                    # only the visible tab's fields: hidden ones keep stale rects
            f = self.fields.get(s.key)
            if f is not None and (f.focused or (inside and f.rect.collidepoint(e.pos))):
                if f.handle_event(e):
                    self.set_value(s.key, f.value)
        if not inside:
            return
        for s in self.rows():
            k = s.key
            if self.reset_btn[k].handle_event(e):
                self.reset_one(k)
                return
            if s.kind in ("int", "float"):
                for btn, d in ((self.minus[k], -1), (self.plus[k], +1)):
                    if btn.handle_event(e):
                        self.nudge(k, d)
                        return
            elif s.kind == "key":
                continue                                       # handled above
            elif self.value_rect[k].collidepoint(e.pos):
                self.nudge(k, +1)                              # toggle switch / cycle choice
                return

    def update(self, dt: float) -> None:
        for f in self.fields.values():
            if f.focused:
                f.update(dt)

    # -- drawing -------------------------------------------------------------------------------------
    def draw(self, screen: pygame.Surface) -> None:
        self._place()
        screen.fill(config.BG_COLOR)
        m = config.PAGE_MARGIN
        draw_text(screen, "Settings", config.PAGE_TITLE_FONT, config.ACCENT_COLOR, (m, m), "topleft")
        self.back_btn.draw(screen)
        self.tabs.draw(screen)
        old = self.area.begin_clip(screen)
        for i, s in enumerate(self.rows()):
            if self.area.visible(i * config.SET_ROW_H, config.SET_ROW_H):
                self._draw_row(screen, i, s)
        self.area.end_clip(screen, old)
        self.area.draw_scrollbar(screen)
        self.reset_tab_btn.draw(screen)
        self.reset_all_btn.draw(screen)

    def _draw_row(self, screen: pygame.Surface, i: int, s: Setting) -> None:
        r = self.layout_row(i, s)
        row, k = r["row"], s.key
        pygame.draw.line(screen, config.BUTTON_FILL, (row.left, row.bottom - 1), (row.right - 8, row.bottom - 1))
        ctrl_left = (r.get("switch") or r.get("cycle") or r["minus"]).left
        max_w = ctrl_left - row.left - 16
        draw_text(screen, s.label, config.SET_LABEL_FONT, config.TEXT_COLOR, (row.left + 4, row.top + 8),
                  max_w=max_w, min_size=14)
        note = note_text(s)
        if note:
            draw_text(screen, note, config.SET_NOTE_FONT, config.DIM_TEXT_COLOR, (row.left + 4, row.top + 34),
                      max_w=max_w, min_size=12)
        self.reset_btn[k].draw(screen)
        if s.kind == "bool":
            draw_switch(screen, r["switch"], bool(settings.get(k)))
        elif s.kind == "key":
            self.keyfields[k].draw(screen)
        elif s.kind == "choice":
            pygame.draw.rect(screen, config.INPUT_FILL, r["cycle"], border_radius=6)
            pygame.draw.rect(screen, config.INPUT_BORDER, r["cycle"], width=2, border_radius=6)
            draw_text(screen, str(settings.get(k)), config.NUMBER_FIELD_FONT, config.TEXT_COLOR,
                      r["cycle"].center, "center")
        else:
            self.minus[k].draw(screen)
            self.fields[k].draw(screen)
            self.plus[k].draw(screen)

    def value_text(self, key: str) -> str:
        """The value as the row shows it (for tests)."""
        s = settings.find(key)
        v = settings.get(key)
        if s.kind in ("int", "float"):
            return fmt_number(v, s.kind == "int")
        return str(v)
