"""Collapsible equation sidebar: rows, on/off switch, pencil (edit) and trash (delete) icons, drag reorder."""
from __future__ import annotations

import pygame

from ascensus import config, view
from ascensus.core.equations import EquationManager
from ascensus.ui import icons
from ascensus.ui.colorpicker import CustomRow
from ascensus.ui.inputbox import InputBox
from ascensus.ui.widgets import NumberField, Slider, draw_icon, draw_text, fmt_number, get_font

TAGS = {"queued": "queued", "off": "off", "offscreen": "off-screen"}


class Sidebar:
    """Left panel. handle_event returns True when the event was consumed."""

    def __init__(self, manager: EquationManager, input_box: InputBox) -> None:
        self.manager = manager
        self.input = input_box
        self.on_delete = None                    # optional callback(entry) after Del removed a row (undo toast)
        self.collapsed = False
        self.press_idx: int | None = None        # row pressed on its body (drag candidate)
        self.press_pos = (0, 0)
        self.drag_idx: int | None = None         # row being dragged once past the threshold
        self.drag_target = 0
        self.mouse_y = 0
        self.scroll = 0.0                        # equations section: px scrolled from the top
        self.var_scroll = 0.0                    # variables section: px scrolled from the top
        self._slider = Slider(pygame.Rect(0, 0, 10, 10), config.VAR_MIN, config.VAR_MAX, 0.0,
                              config.VAR_STEP)   # shared by all rows; re-aimed at the row in use
        self.var_drag: str | None = None         # variable whose slider is being dragged
        lim = config.VAR_VALUE_LIMIT
        self.var_field = NumberField(pygame.Rect(0, 0, config.VAR_BOX_W, config.VAR_BOX_H), 0.0,
                                     lo=-lim, hi=lim)    # shared value box; follows the edited row
        self.var_edit: str | None = None         # variable whose value box is being edited
        self._row_cache: dict[tuple, pygame.Surface] = {}   # rendered row images
        self.picker_idx: int | None = None       # row whose colour popup is open
        self.picker_rect = pygame.Rect(0, 0, 0, 0)
        self.custom = CustomRow()                # the popup's Custom row (hue / brightness strips, hex box)
        self.tab_rect = pygame.Rect(0, config.SIDEBAR_TAB_Y, *config.SIDEBAR_TAB_SIZE)
        self.collapse_rect = pygame.Rect(config.SIDEBAR_W - config.SIDEBAR_PAD - config.SIDEBAR_COLLAPSE_SIZE,
                                         config.SIDEBAR_PAD * 2, config.SIDEBAR_COLLAPSE_SIZE,
                                         config.SIDEBAR_COLLAPSE_SIZE)
        self._hover = pygame.Surface((config.SIDEBAR_W - 2 * 4, config.SIDEBAR_ROW_H - 2), pygame.SRCALPHA)
        self._hover.fill(config.SIDEBAR_HOVER_COLOR)
        self.on_resize()

    def on_resize(self) -> None:
        """The panel is as tall as the window: rebuild its rect and background."""
        self.panel_rect = pygame.Rect(0, 0, config.SIDEBAR_W, view.H)
        self._panel = pygame.Surface(self.panel_rect.size, pygame.SRCALPHA)
        self._panel.fill(config.SIDEBAR_COLOR)

    @property
    def dragging(self) -> bool:
        return self.drag_idx is not None

    # --- geometry --------------------------------------------------------
    @property
    def value_focused(self) -> bool:
        """True while a variable's value box is being typed in (the scene slows time like typing)."""
        return self.var_field.focused

    def variable_names(self) -> list[str]:
        """Rows of the VARIABLES section (empty means equations get the whole panel)."""
        return self.manager.store.names()

    def eq_rect(self) -> pygame.Rect:
        """Visible viewport of the equations list (below the header strip)."""
        top = config.SIDEBAR_HEADER_H
        full = view.H - top
        h = int(full * (1 - config.SIDEBAR_VARS_FRACTION)) if self.variable_names() else full
        return pygame.Rect(0, top, config.SIDEBAR_W, max(h, 0))

    def var_rect(self) -> pygame.Rect | None:
        """Viewport of the VARIABLES list, or None when there are no variables."""
        if not self.variable_names():
            return None
        eq = self.eq_rect()
        top = eq.bottom + config.SIDEBAR_SECTION_H
        return pygame.Rect(0, top, config.SIDEBAR_W, max(view.H - top, 0))

    def content_h(self) -> int:
        return len(self.manager.entries) * config.SIDEBAR_ROW_H

    def var_content_h(self) -> int:
        return len(self.variable_names()) * config.VAR_ROW_H

    def var_max_scroll(self) -> float:
        vr = self.var_rect()
        return float(max(0, self.var_content_h() - (vr.height if vr else 0)))

    def scroll_vars(self, rows: float) -> None:
        """Scroll the variables list by a number of rows (positive = down), clamped."""
        self.var_scroll = max(0.0, min(self.var_max_scroll(), self.var_scroll + rows * config.VAR_ROW_H))

    def var_row_rect(self, i: int) -> pygame.Rect:
        """Screen rect of variable row i (may lie outside the viewport)."""
        vr = self.var_rect() or pygame.Rect(0, 0, config.SIDEBAR_W, 0)
        return pygame.Rect(0, int(vr.top + i * config.VAR_ROW_H - self.var_scroll),
                           config.SIDEBAR_W, config.VAR_ROW_H)

    @staticmethod
    def _var_parts(row: pygame.Rect) -> dict[str, pygame.Rect]:
        """Name, slider, value box and play button of a variable row drawn at `row`."""
        pad, cy = config.SIDEBAR_PAD, row.centery
        right = config.SIDEBAR_W - pad - 6
        play = pygame.Rect(right - config.VAR_BTN, cy - config.VAR_BTN // 2, config.VAR_BTN, config.VAR_BTN)
        box = pygame.Rect(play.left - 4 - config.VAR_BOX_W, cy - config.VAR_BOX_H // 2,
                          config.VAR_BOX_W, config.VAR_BOX_H)
        name = pygame.Rect(pad + 4, row.y, config.VAR_NAME_W, row.h)
        sx = name.right + 2
        return {"name": name, "slider": pygame.Rect(sx, row.y, max(box.left - 6 - sx, 10), row.h),
                "box": box, "play": play}

    def var_rects(self, i: int) -> dict[str, pygame.Rect]:
        """Clickable parts of variable row i: name, slider, box, play."""
        return self._var_parts(self.var_row_rect(i))

    def _var_row_at(self, pos: tuple[int, int]) -> int | None:
        vr = self.var_rect()
        if vr is None or not vr.collidepoint(pos):
            return None
        i = int((pos[1] - vr.top + self.var_scroll) // config.VAR_ROW_H)
        return i if 0 <= i < len(self.variable_names()) else None

    def max_scroll(self) -> float:
        return float(max(0, self.content_h() - self.eq_rect().height))

    def _clamp_scroll(self) -> None:
        self.scroll = max(0.0, min(self.max_scroll(), self.scroll))

    def scroll_rows(self, rows: float) -> None:
        """Scroll the equations list by a number of rows (positive = down), clamped."""
        self.scroll += rows * config.SIDEBAR_ROW_H
        self._clamp_scroll()

    def row_rect(self, i: int) -> pygame.Rect:
        """Screen rect of row/slot i, shifted by the scroll offset (may lie outside the viewport)."""
        return pygame.Rect(0, int(self.eq_rect().top + i * config.SIDEBAR_ROW_H - self.scroll),
                           config.SIDEBAR_W, config.SIDEBAR_ROW_H)

    def rects(self, i: int) -> dict[str, pygame.Rect]:
        """Clickable parts of row i: swatch, switch, edit, delete (the rest of the row is the drag area)."""
        return self._parts(self.row_rect(i))

    @staticmethod
    def _parts(row: pygame.Rect) -> dict[str, pygame.Rect]:
        """The clickable parts for a row drawn at `row`."""
        pad = config.SIDEBAR_PAD
        bh = config.SIDEBAR_BTN_H
        dele = pygame.Rect(row.right - pad - config.SIDEBAR_DEL_W, row.centery - bh // 2,
                           config.SIDEBAR_DEL_W, bh)
        edit = pygame.Rect(dele.left - 4 - config.SIDEBAR_EDIT_W, dele.top, config.SIDEBAR_EDIT_W, bh)
        sw, sh = config.SIDEBAR_SWITCH_SIZE
        switch = pygame.Rect(edit.left - 4 - sw, row.centery - sh // 2, sw, sh)
        s = config.SIDEBAR_SWATCH
        swatch = pygame.Rect(pad + 22, row.centery - s // 2, s, s)
        return {"swatch": swatch, "switch": switch, "edit": edit, "delete": dele}

    def _row_at(self, pos: tuple[int, int]) -> int | None:
        """Row under a screen point (inside the equations viewport), or None."""
        eq = self.eq_rect()
        if not eq.collidepoint(pos):
            return None
        i = int((pos[1] - eq.top + self.scroll) // config.SIDEBAR_ROW_H)
        return i if 0 <= i < len(self.manager.entries) else None

    def _slot_at(self, y: int) -> int:
        n = len(self.manager.entries)
        i = int((y - self.eq_rect().top + self.scroll) // config.SIDEBAR_ROW_H)
        return max(0, min(n - 1, i))

    def _picker_cell(self, k: int) -> pygame.Rect:
        c, g, p = config.PICKER_CELL, config.PICKER_GAP, config.PICKER_PAD
        col, row = k % config.PICKER_COLS, k // config.PICKER_COLS
        return pygame.Rect(self.picker_rect.x + p + col * (c + g), self.picker_rect.y + p + row * (c + g), c, c)

    def _custom_top(self) -> int:
        """y of the Custom row inside the popup (below the swatch grid and a separator line)."""
        c, g, p = config.PICKER_CELL, config.PICKER_GAP, config.PICKER_PAD
        rows = -(-len(config.CURVE_PALETTE_20) // config.PICKER_COLS)
        return self.picker_rect.y + p + rows * c + (rows - 1) * g + config.PICKER_SEP + 2

    def open_picker(self, i: int) -> None:
        """Open the colour popup (20 swatches + Custom row) for row i, under its swatch, inside the window."""
        n = len(config.CURVE_PALETTE_20)
        cols, rows = config.PICKER_COLS, -(-n // config.PICKER_COLS)
        c, g, p = config.PICKER_CELL, config.PICKER_GAP, config.PICKER_PAD
        w = 2 * p + cols * c + (cols - 1) * g
        h = 2 * p + rows * c + (rows - 1) * g + config.PICKER_SEP + 2 + CustomRow.height()
        sw = self.rects(i)["swatch"]
        x = max(0, min(view.W - w, sw.left))
        y = sw.bottom + 4
        if y + h > view.H:
            y = max(0, sw.top - 4 - h)
        self.picker_idx, self.picker_rect = i, pygame.Rect(x, y, w, h)
        self.custom.hex.blur()
        self.custom.set_rect(pygame.Rect(x + p, self._custom_top(), w - 2 * p, CustomRow.height()))
        if i < len(self.manager.entries):
            self.custom.set_color(self.manager.entries[i].color)
        self.input.blur()                          # one text focus at a time

    def close_picker(self) -> None:
        """Close the colour popup (dropping an unfinished hex edit)."""
        if self.picker_idx is not None and self.custom.hex.focused and not self.input.focused:
            try:
                pygame.key.stop_text_input()
            except pygame.error:
                pass
        self.custom.hex.blur()
        for strip in (self.custom.hue_strip, self.custom.val_strip):
            strip.dragging = False
        self.picker_idx = None

    def picker_hover(self, pos: tuple[int, int]) -> int | None:
        """Index of the palette swatch under `pos` while the popup is open, else None."""
        if self.picker_idx is None or not self.picker_rect.collidepoint(pos):
            return None
        for k in range(len(config.CURVE_PALETTE_20)):
            if self._picker_cell(k).collidepoint(pos):
                return k
        return None

    def picker_tooltip(self, pos: tuple[int, int]) -> str | None:
        """Name of the palette colour under `pos` (the hover tooltip), or None."""
        k = self.picker_hover(pos)
        return config.CURVE_PALETTE_NAMES[k] if k is not None else None

    def _apply_color(self, color: tuple[int, int, int]) -> None:
        if self.picker_idx is not None and self.picker_idx < len(self.manager.entries):
            self.manager.set_color(self.picker_idx, color)

    def _picker_event(self, e: pygame.event.Event) -> None:
        """The popup is modal: every event lands here first and is consumed."""
        cus = self.custom
        if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE and not cus.hex.focused:
            self.close_picker()
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            self._picker_click(e.pos)
        elif e.type == pygame.MOUSEWHEEL:
            self.close_picker()
        elif e.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONUP, pygame.KEYDOWN, pygame.TEXTINPUT):
            color = cus.handle_event(e)
            if color is not None:
                self._apply_color(color)

    def _picker_click(self, pos: tuple[int, int]) -> None:
        """A click while the popup is open: pick a swatch, use the Custom row, or close it (always consumed)."""
        if self.picker_rect.collidepoint(pos):
            k = self.picker_hover(pos)
            if k is not None:
                self._apply_color(config.CURVE_PALETTE_20[k])
                self.close_picker()
                return
            color = self.custom.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1))
            if color is not None:
                self._apply_color(color)
            return                                # on the Custom row or the padding: stay open
        self.close_picker()

    # --- events ----------------------------------------------------------
    def update(self, real_dt: float) -> None:
        """Per frame: keep the scroll in range and auto-scroll while a drag is near a section edge."""
        self._clamp_scroll()
        self.scroll_vars(0)
        self.var_field.update(real_dt)
        if self.var_edit is not None and self.var_edit not in self.manager.store:
            self.var_field._end()                # its equation went away mid-edit
            self._after_field()
        if self.var_drag is not None and self.var_drag not in self.manager.store:
            self.var_drag = None
        if not self.dragging:
            return
        eq, zone = self.eq_rect(), config.SIDEBAR_EDGE_SCROLL_ZONE
        if self.mouse_y < eq.top + zone:
            k = min(1.0, (eq.top + zone - self.mouse_y) / zone)
            self.scroll -= config.SIDEBAR_EDGE_SCROLL_SPEED * k * real_dt
        elif self.mouse_y > eq.bottom - zone:
            k = min(1.0, (self.mouse_y - (eq.bottom - zone)) / zone)
            self.scroll += config.SIDEBAR_EDGE_SCROLL_SPEED * k * real_dt
        self._clamp_scroll()
        self.drag_target = self._slot_at(self.mouse_y)

    def _after_field(self) -> None:
        """Tidy up once the value box lost focus (Enter, Esc, click elsewhere)."""
        if self.var_field.focused:
            return
        self.var_edit = None
        if not self.input.focused:
            try:
                pygame.key.stop_text_input()
            except pygame.error:
                pass

    def _aim_slider(self, i: int, name: str) -> Slider:
        """Point the shared slider at variable row i (range and step read from config at use time)."""
        sl = self._slider
        sl.lo, sl.hi, sl.step = config.VAR_MIN, config.VAR_MAX, config.VAR_STEP
        sl.set_rect(self.var_rects(i)["slider"])
        sl.value = self.manager.store.get(name).value
        return sl

    def _handle_vars(self, e: pygame.event.Event) -> bool | None:
        """VARIABLES section events: slider, value box, play, wheel. True/False = decided, None = not mine."""
        store, f = self.manager.store, self.var_field
        if f.focused and e.type in (pygame.KEYDOWN, pygame.KEYUP, pygame.TEXTINPUT):
            if e.type != pygame.KEYUP and f.handle_event(e) and self.var_edit in store:
                store.set_value(self.var_edit, f.value)          # Enter applied
            self._after_field()
            return True                                          # typing owns the keyboard
        if self.var_drag is not None and e.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONUP):
            names = self.variable_names()
            if self.var_drag in names:
                sl = self._aim_slider(names.index(self.var_drag), self.var_drag)
                sl.dragging = True
                if sl.handle_event(e):
                    store.set_value(self.var_drag, sl.value)
            if e.type == pygame.MOUSEBUTTONUP and e.button == 1:
                self.var_drag = None
                self._slider.dragging = False
            return True
        if e.type == pygame.MOUSEWHEEL:
            vr = self.var_rect()
            pos = getattr(e, "pos", None) or pygame.mouse.get_pos()
            if vr is not None and vr.collidepoint(pos):
                self.scroll_vars(-e.y * config.SIDEBAR_SCROLL_ROWS)
                return True
            return None
        if e.type != pygame.MOUSEBUTTONDOWN or e.button != 1:
            return None
        if f.focused and not f.rect.collidepoint(e.pos):
            f.handle_event(e)                                    # a click elsewhere cancels the edit
            self._after_field()
        i = self._var_row_at(e.pos)
        if i is None:
            return None
        name = self.variable_names()[i]
        parts = self.var_rects(i)
        if parts["box"].collidepoint(e.pos):
            f.set_rect(parts["box"])
            self.input.blur()                                    # one text focus at a time
            if self.var_edit != name:
                f.set_value(store.get(name).value)
                self.var_edit = name
            f.handle_event(e)
        elif parts["play"].collidepoint(e.pos):
            store.toggle_play(name)
        elif parts["slider"].collidepoint(e.pos):
            store.set_playing(name, False)                       # grabbing the slider takes over
            sl = self._aim_slider(i, name)
            if sl.handle_event(e):
                store.set_value(name, sl.value)
            self.var_drag = name if sl.dragging else None
        return True

    def handle_event(self, e: pygame.event.Event) -> bool:
        if self.picker_idx is not None:                      # the colour popup is modal: it sees events first
            self._picker_event(e)
            if self.picker_idx is not None or e.type != pygame.MOUSEWHEEL:
                return True                                  # (a wheel notch closes it and scrolls on)
        if not self.collapsed:
            done = self._handle_vars(e)
            if done is not None:
                return done
        if e.type == pygame.MOUSEWHEEL:
            pos = getattr(e, "pos", None) or pygame.mouse.get_pos()
            if self.collapsed or not self.eq_rect().collidepoint(pos):
                return False
            self.scroll_rows(-e.y * config.SIDEBAR_SCROLL_ROWS)
            return True
        if e.type not in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION):
            return False
        self._clamp_scroll()
        inside = (self.tab_rect if self.collapsed else self.panel_rect).collidepoint(e.pos)
        if self.press_idx is not None or self.dragging:
            if e.type == pygame.MOUSEMOTION:
                self._motion(e.pos)
                return True
            if e.type == pygame.MOUSEBUTTONUP and e.button == 1:
                self._release()
                return True
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and inside:
            self._press(e.pos)
        return inside

    def _press(self, pos: tuple[int, int]) -> None:
        if self.collapsed:
            self.collapsed = False
            return
        if self.collapse_rect.collidepoint(pos):
            self.collapsed = True
            return
        i = self._row_at(pos)
        if i is None:
            return
        parts = self.rects(i)
        if parts["swatch"].inflate(config.SWATCH_HIT - config.SIDEBAR_SWATCH,
                                    config.SWATCH_HIT - config.SIDEBAR_SWATCH).collidepoint(pos):
            self.open_picker(i)
        elif parts["switch"].collidepoint(pos):
            self.manager.toggle(i)
        elif parts["edit"].collidepoint(pos):
            self.input.set_text(self.manager.entries[i].text, i)
        elif parts["delete"].collidepoint(pos):
            self._delete(i)
        else:
            self.press_idx, self.press_pos, self.mouse_y = i, pos, pos[1]

    def _delete(self, i: int) -> None:
        entry = self.manager.entries[i]
        self.manager.delete(i)
        if self.on_delete is not None:
            self.on_delete(entry)
        ei = self.input.edit_index
        if ei == i:
            self.input.clear()
        elif ei is not None and ei > i:
            self.input.edit_index = ei - 1

    def _motion(self, pos: tuple[int, int]) -> None:
        self.mouse_y = pos[1]
        if self.drag_idx is None:
            dx, dy = pos[0] - self.press_pos[0], pos[1] - self.press_pos[1]
            if dx * dx + dy * dy <= config.DRAG_THRESHOLD ** 2:
                return
            self.drag_idx = self.press_idx
        self.drag_target = self._slot_at(pos[1])

    def _release(self) -> None:
        src, dst = self.drag_idx, self.drag_target
        self.press_idx = self.drag_idx = None
        if src is None or src == dst:
            return
        self.manager.move(src, dst)
        ei = self.input.edit_index              # keep the edited row's index in step
        if ei is not None:
            if ei == src:
                self.input.edit_index = dst
            elif src < ei <= dst:
                self.input.edit_index = ei - 1
            elif dst <= ei < src:
                self.input.edit_index = ei + 1

    # --- drawing ---------------------------------------------------------
    def draw(self, screen: pygame.Surface) -> None:
        if self.collapsed:
            self._draw_arrow_button(screen, self.tab_rect, pointing_right=True)
            return
        screen.blit(self._panel, (0, 0))
        pad = config.SIDEBAR_PAD
        draw_text(screen, "EQUATIONS", config.SIDEBAR_TITLE_FONT, config.TEXT_COLOR, (pad + 4, pad + 2))
        n = len(self.manager.active())
        draw_text(screen, f"active {n}/{config.MAX_ACTIVE}", config.SIDEBAR_SMALL_FONT,
                  config.DIM_TEXT_COLOR, (pad + 4, pad + 28))
        self._draw_arrow_button(screen, self.collapse_rect, pointing_right=False)
        self._clamp_scroll()
        entries = self.manager.entries
        mouse = pygame.mouse.get_pos()
        eq = self.eq_rect()
        old_clip = screen.get_clip()
        screen.set_clip(eq)
        slots = list(range(len(entries)))
        if self.dragging:
            slots.remove(self.drag_idx)
            slots.insert(self.drag_target, self.drag_idx)   # the gap opens at drag_target
        first = max(0, int(self.scroll // config.SIDEBAR_ROW_H))
        last = min(len(slots), first + eq.height // config.SIDEBAR_ROW_H + 2)
        for slot in range(first, last):                      # only the visible rows are drawn
            i = slots[slot]
            if i != self.drag_idx:
                self._draw_row(screen, i, self.row_rect(slot), mouse, ghost=False)
        if self.dragging:
            y = self.mouse_y - config.SIDEBAR_ROW_H // 2
            row = self.row_rect(0)
            row.y = max(eq.top, min(eq.bottom - config.SIDEBAR_ROW_H, y))
            self._draw_row(screen, self.drag_idx, row, mouse, ghost=True)
        self._draw_scrollbar(screen, eq)
        screen.set_clip(old_clip)
        self._draw_variables(screen)

    def draw_popups(self, screen: pygame.Surface) -> None:
        """The colour popup: the scene calls this LAST so it sits on top of everything."""
        if self.picker_idx is not None and not self.collapsed:
            self._draw_picker(screen, pygame.mouse.get_pos())

    def _draw_variables(self, screen: pygame.Surface) -> None:
        """VARIABLES section: title strip, then clipped rows (name, slider, value box, play/pause)."""
        vr = self.var_rect()
        if vr is None:
            return
        names = self.variable_names()
        strip = pygame.Rect(0, vr.top - config.SIDEBAR_SECTION_H, config.SIDEBAR_W, config.SIDEBAR_SECTION_H)
        pygame.draw.line(screen, config.BUTTON_BORDER, strip.topleft, strip.topright)
        draw_text(screen, f"VARIABLES {len(names)}", config.SIDEBAR_SMALL_FONT, config.TEXT_COLOR,
                  (config.SIDEBAR_PAD + 4, strip.centery), "midleft")
        self.scroll_vars(0)
        mouse = pygame.mouse.get_pos()
        old_clip = screen.get_clip()
        screen.set_clip(vr)
        first = max(0, int(self.var_scroll // config.VAR_ROW_H))
        last = min(len(names), first + vr.height // config.VAR_ROW_H + 2)
        for i in range(first, last):
            self._draw_var_row(screen, i, names[i], mouse)
        total = self.var_content_h()
        if total > vr.height:                                    # thin scrollbar
            thumb = max(config.SIDEBAR_SCROLLBAR_MIN, int(vr.height * vr.height / total))
            y = vr.top + int((vr.height - thumb) * self.var_scroll / max(self.var_max_scroll(), 1))
            bar = pygame.Surface((config.SIDEBAR_SCROLLBAR_W, thumb), pygame.SRCALPHA)
            bar.fill(config.SIDEBAR_SCROLLBAR_COLOR)
            screen.blit(bar, (vr.right - config.SIDEBAR_SCROLLBAR_W - 1, y))
        screen.set_clip(old_clip)

    def _draw_var_row(self, screen: pygame.Surface, i: int, name: str, mouse: tuple[int, int]) -> None:
        """One variable row: name, slider, value box (the focused one is the shared NumberField), play/pause."""
        var = self.manager.store.get(name)
        parts = self.var_rects(i)
        draw_text(screen, _fit(name, config.SIDEBAR_TEXT_FONT, parts["name"].w), config.SIDEBAR_TEXT_FONT,
                  config.TEXT_COLOR, parts["name"].midleft, "midleft")
        sl = self._aim_slider(i, name)
        sl.dragging = name == self.var_drag
        sl.draw(screen)
        box = parts["box"]
        if self.var_field.focused and self.var_edit == name:
            self.var_field.set_rect(box)
            self.var_field.draw(screen)
        else:
            hover = box.collidepoint(mouse)
            pygame.draw.rect(screen, config.INPUT_FILL, box, border_radius=6)
            pygame.draw.rect(screen, config.ACCENT_COLOR if hover else config.INPUT_BORDER, box,
                             width=2, border_radius=6)
            draw_text(screen, _fit(fmt_number(var.value), config.SIDEBAR_SMALL_FONT, box.w - 12),
                      config.SIDEBAR_SMALL_FONT, config.TEXT_COLOR, (box.left + 6, box.centery), "midleft")
        play = parts["play"]
        hover = play.collidepoint(mouse)
        pygame.draw.rect(screen, config.BUTTON_HOVER_FILL if hover else config.BUTTON_FILL, play, border_radius=5)
        pygame.draw.rect(screen, config.ACCENT_COLOR if (hover or var.playing) else config.BUTTON_BORDER,
                         play, width=1, border_radius=5)
        draw_icon(screen, "pause" if var.playing else "play", play,
                  config.ACCENT_COLOR if var.playing else config.TEXT_COLOR)

    def _draw_scrollbar(self, screen: pygame.Surface, area: pygame.Rect) -> None:
        """Thin scroll indicator at the section's right edge (only when the content overflows)."""
        total, span = self.content_h(), area.height
        if total <= span:
            return
        thumb = max(config.SIDEBAR_SCROLLBAR_MIN, int(span * span / total))
        y = area.top + int((span - thumb) * self.scroll / max(self.max_scroll(), 1))
        bar = pygame.Surface((config.SIDEBAR_SCROLLBAR_W, thumb), pygame.SRCALPHA)
        bar.fill(config.SIDEBAR_SCROLLBAR_COLOR)
        screen.blit(bar, (area.right - config.SIDEBAR_SCROLLBAR_W - 1, y))

    def _draw_picker(self, screen: pygame.Surface, mouse: tuple[int, int]) -> None:
        """The popup: 5 x 4 named swatches (current one outlined), a separator, the Custom row, a hover tooltip."""
        pygame.draw.rect(screen, config.PICKER_FILL, self.picker_rect, border_radius=6)
        pygame.draw.rect(screen, config.PICKER_BORDER, self.picker_rect, width=2, border_radius=6)
        cur = None
        if self.picker_idx is not None and self.picker_idx < len(self.manager.entries):
            cur = self.manager.entries[self.picker_idx].color
        for k, color in enumerate(config.CURVE_PALETTE_20):
            r = self._picker_cell(k)
            pygame.draw.rect(screen, color, r, border_radius=3)
            if color == (0, 0, 0) or color == config.PICKER_FILL:
                pygame.draw.rect(screen, config.PICKER_BORDER, r, width=1, border_radius=3)    # keep Black visible
            if color == cur:
                pygame.draw.rect(screen, config.TEXT_COLOR, r.inflate(4, 4), width=2, border_radius=4)
            elif r.collidepoint(mouse):
                pygame.draw.rect(screen, config.ACCENT_COLOR, r.inflate(4, 4), width=1, border_radius=4)
        p = config.PICKER_PAD
        y = self._custom_top() - config.PICKER_SEP // 2 - 1
        pygame.draw.line(screen, config.PICKER_BORDER, (self.picker_rect.left + p, y), (self.picker_rect.right - p, y))
        self.custom.draw(screen)
        name = self.picker_tooltip(mouse)
        if name is not None:
            cell = self._picker_cell(self.picker_hover(mouse))
            font = config.PICKER_TIP_FONT
            w, h = get_font(font).size(name)
            pad = config.PICKER_TIP_PAD
            tip = pygame.Rect(0, 0, w + 2 * pad, h + 2 * pad)
            tip.midtop = (cell.centerx, cell.bottom + 6)
            if tip.bottom > view.H:
                tip.midbottom = (cell.centerx, cell.top - 6)
            tip.clamp_ip(pygame.Rect(0, 0, view.W, view.H))
            pygame.draw.rect(screen, config.PICKER_TIP_FILL, tip, border_radius=4)
            pygame.draw.rect(screen, config.PICKER_BORDER, tip, width=1, border_radius=4)
            draw_text(screen, name, font, config.TEXT_COLOR, tip.center, "center")

    def _draw_arrow_button(self, screen: pygame.Surface, rect: pygame.Rect, pointing_right: bool) -> None:
        hover = rect.collidepoint(pygame.mouse.get_pos())
        if self.collapsed:
            pygame.draw.rect(screen, config.SIDEBAR_COLOR[:3], rect, border_top_right_radius=8,
                             border_bottom_right_radius=8)
        pygame.draw.rect(screen, config.ACCENT_COLOR if hover else config.BUTTON_BORDER, rect,
                         width=2, border_radius=6)
        cx, cy, d = rect.centerx, rect.centery, 6
        s = 1 if pointing_right else -1
        col = config.ACCENT_COLOR if hover else config.TEXT_COLOR
        pygame.draw.lines(screen, col, False, [(cx - s * d // 2, cy - d), (cx + s * d // 2, cy),
                                               (cx - s * d // 2, cy + d)], 3)

    def _draw_row(self, screen: pygame.Surface, i: int, row: pygame.Rect,
                  mouse: tuple[int, int], ghost: bool) -> None:
        """Blit the row's cached image (rendered once per text/colour/status), then hover effects."""
        e = self.manager.entries[i]
        status = self.manager.status(e)
        key = (e.text, e.color, status, e.enabled)
        img = self._row_cache.get(key)
        if img is None:
            if len(self._row_cache) >= config.TEXT_CACHE_MAX // 2:
                self._row_cache.clear()
            img = self._row_cache[key] = pygame.Surface((config.SIDEBAR_W, config.SIDEBAR_ROW_H),
                                                        pygame.SRCALPHA)
            self._paint_row(img, e, status, pygame.Rect(0, 0, config.SIDEBAR_W, config.SIDEBAR_ROW_H))
        if ghost or (row.collidepoint(mouse) and not self.dragging):
            screen.blit(self._hover, (4, row.y + 1))
        screen.blit(img, row.topleft)
        if row.collidepoint(mouse) and not self.dragging:
            parts = self._parts(row)
            for name, icon_name, base in (("edit", "pencil", config.TEXT_COLOR),
                                          ("delete", "trash", config.DANGER_COLOR)):
                r = parts[name]
                if r.collidepoint(mouse):
                    pygame.draw.rect(screen, config.BUTTON_HOVER_FILL, r, border_radius=4)
                    pygame.draw.rect(screen, base, r, width=1, border_radius=4)
                    self._blit_icon(screen, icon_name, r, base)

    def _paint_row(self, screen: pygame.Surface, e, status: str, row: pygame.Rect) -> None:
        """Paint a row's static parts (handle, swatch, text, tag, switch, pencil / trash icons) onto `row`."""
        dim = status in ("off", "queued")
        pad = config.SIDEBAR_PAD
        cy = row.centery
        for k in (-4, 0, 4):                                         # drag handle: 3 short lines
            pygame.draw.line(screen, config.DIM_TEXT_COLOR, (pad + 2, cy + k), (pad + 14, cy + k), 2)
        sw = config.SIDEBAR_SWATCH
        swatch = pygame.Rect(pad + 22, cy - sw // 2, sw, sw)
        pygame.draw.rect(screen, tuple(c // 3 for c in e.color) if dim else e.color, swatch, border_radius=2)

        parts = self._parts(row)
        text_left = swatch.right + 8
        text_w = parts["switch"].left - 6 - text_left
        color = config.DIM_TEXT_COLOR if dim else config.TEXT_COLOR
        tag = TAGS.get(status)
        ty = cy - 8 if tag else cy
        body = e.text
        if e.parsed.name:                                            # bold name in the curve colour
            name_color = tuple(c // 3 for c in e.color) if dim else e.color
            nr = _draw_bold(screen, e.parsed.name, config.SIDEBAR_TEXT_FONT, name_color, (text_left, ty))
            text_left = nr.right + config.SIDEBAR_NAME_GAP
            text_w = parts["switch"].left - 6 - text_left
            body = e.parsed.source
        draw_text(screen, _fit(body, config.SIDEBAR_TEXT_FONT, max(text_w, 0)), config.SIDEBAR_TEXT_FONT,
                  config.DIM_TEXT_COLOR if e.parsed.name else color, (text_left, ty), "midleft")
        if tag:
            draw_text(screen, tag, config.SIDEBAR_TAG_FONT, config.DIM_TEXT_COLOR,
                      (text_left, cy + 12), "midleft")

        self._draw_switch(screen, parts["switch"], e.enabled)
        for name, icon_name, base in (("edit", "pencil", config.TEXT_COLOR),
                                      ("delete", "trash", config.DANGER_COLOR)):
            self._blit_icon(screen, icon_name, parts[name], base)

    @staticmethod
    def _blit_icon(screen: pygame.Surface, name: str, rect: pygame.Rect, color: tuple[int, ...]) -> None:
        """Centre the pencil / trash icon in a button rect (the hit rect stays the whole button)."""
        img = icons.icon(name, min(config.SIDEBAR_BTN_ICON, rect.h - 4), color)
        screen.blit(img, img.get_rect(center=rect.center))

    @staticmethod
    def _draw_switch(screen: pygame.Surface, r: pygame.Rect, on: bool) -> None:
        pygame.draw.rect(screen, config.SWITCH_ON_COLOR if on else config.SWITCH_OFF_COLOR, r,
                         border_radius=r.height // 2)
        kr = r.height // 2 - 2
        kx = r.right - r.height // 2 if on else r.left + r.height // 2
        pygame.draw.circle(screen, config.TEXT_COLOR, (kx, r.centery), kr)


_bold_cache: dict[tuple, pygame.Surface] = {}


def _draw_bold(screen: pygame.Surface, text: str, size: int, color: tuple[int, ...],
               pos: tuple[int, int]) -> pygame.Rect:
    """Draw bold built-in-font text with its midleft at pos; returns the drawn rect."""
    key = (text, size, tuple(color))
    img = _bold_cache.get(key)
    if img is None:
        if len(_bold_cache) >= config.TEXT_CACHE_MAX:
            _bold_cache.clear()
        img = _bold_cache[key] = get_font(size, bold=True).render(text, True, color)
    rect = img.get_rect(midleft=pos)
    screen.blit(img, rect)
    return rect


_fit_cache: dict[tuple, str] = {}


def _fit(text: str, size: int, width: int) -> str:
    """Truncate text with '...' so it renders within `width` pixels (cached)."""
    key = (text, size, width)
    out = _fit_cache.get(key)
    if out is None:
        if len(_fit_cache) >= config.TEXT_CACHE_MAX:
            _fit_cache.clear()
        out = _fit_cache[key] = _fit_uncached(text, size, width)
    return out


def _fit_uncached(text: str, size: int, width: int) -> str:
    font = get_font(size)
    if font.size(text)[0] <= width:
        return text
    while text and font.size(text + "...")[0] > width:
        text = text[:-1]
    return text + "..."
