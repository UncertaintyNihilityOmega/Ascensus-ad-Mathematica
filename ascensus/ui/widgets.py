"""Font cache (pygame.freetype), fitted text drawing and a simple Button (pygame's built-in font only)."""
from __future__ import annotations

import pygame
import pygame.freetype

from .. import config
from . import icons


class Font:
    """pygame.freetype wrapper with the small pygame.font API the game uses (size/render/get_height).

    SDL_ttf spaces small text badly ("Pi xel s"); freetype draws the same built-in font correctly.
    `size` keeps the old pygame.font pixel meaning (scaled by config.FONT_SCALE).
    """

    def __init__(self, size: int, bold: bool = False) -> None:
        if not pygame.freetype.get_init():
            pygame.freetype.init()
        self.ft = pygame.freetype.Font(None, size * config.FONT_SCALE)
        self.ft.strong = bold
        self.ft.origin = True            # render_to's position is the baseline, not the bbox top-left
        self.height = self.ft.get_sized_height()
        self.ascent = self.ft.get_sized_ascender()

    def size(self, text: str) -> tuple[int, int]:
        """(advance width, line height) of `text`."""
        if not text:
            return 0, self.height
        r = self.ft.get_rect(text)
        return max(r.x, 0) + r.width, self.height

    def get_height(self) -> int:
        return self.height

    get_linesize = get_height

    def render(self, text: str, antialias: bool, color: tuple[int, ...]) -> pygame.Surface:
        """A per-pixel-alpha surface of the full line height, so baselines line up across strings."""
        w = max(self.size(text)[0], 1)
        surf = pygame.Surface((w, self.height), pygame.SRCALPHA)
        if text:
            self.ft.render_to(surf, (0, self.ascent), text, tuple(color)[:3])
        return surf


_fonts: dict[tuple[int, bool], Font] = {}
_text_cache: dict[tuple, pygame.Surface] = {}
overflow_count = 0                      # times a text had to be truncated even at its minimum size
overflow_log: list[str] = []
audit_rects: list | None = None          # QA: when a list, draw_text appends (text, rect, surface clip, surface size)


def reset_overflow() -> None:
    """Zero the overflow counter (the QA audit test calls this before rendering a page)."""
    global overflow_count
    overflow_count = 0
    overflow_log.clear()


def get_font(size: int, bold: bool = False) -> Font:
    """Cached built-in font of the given pixel size."""
    key = (size, bold)
    if key not in _fonts:
        _fonts[key] = Font(size, bold)
    return _fonts[key]


def wrap_text(text: str, size: int, max_w: int, bold: bool = False) -> list[str]:
    """Greedy word wrap to `max_w` pixels; a word wider than the line is split by characters."""
    font = get_font(size, bold)
    lines: list[str] = []
    cur = ""
    for word in text.split(" "):
        trial = f"{cur} {word}" if cur else word
        if font.size(trial)[0] <= max_w:
            cur = trial
            continue
        if cur:
            lines.append(cur)
        cur = word
        while font.size(cur)[0] > max_w and len(cur) > 1:      # hard split
            i = len(cur) - 1
            while i > 1 and font.size(cur[:i])[0] > max_w:
                i -= 1
            lines.append(cur[:i])
            cur = cur[i:]
    lines.append(cur)
    return lines


def truncate(text: str, size: int, max_w: int, bold: bool = False) -> str:
    """Cut `text` and add '...' so it is at most max_w wide."""
    font = get_font(size, bold)
    if font.size(text)[0] <= max_w:
        return text
    while text and font.size(text + "...")[0] > max_w:
        text = text[:-1]
    return text.rstrip() + "..."


def _line_image(text: str, size: int, color: tuple[int, ...], bold: bool) -> pygame.Surface:
    key = (text, size, tuple(color), bold)
    img = _text_cache.get(key)
    if img is None:
        if len(_text_cache) >= config.TEXT_CACHE_MAX:
            _text_cache.clear()
        img = _text_cache[key] = get_font(size, bold).render(text, True, color)
    return img


def draw_text(surf: pygame.Surface, text: str, size: int, color: tuple[int, ...],
              pos: tuple[int, int], anchor: str = "topleft", *, max_w: int | None = None,
              wrap: bool = False, min_size: int | None = None, bold: bool = False) -> pygame.Rect:
    """Render text with its `anchor` point (a pygame Rect attribute name) at `pos`.

    With `max_w` the text is fitted: first the font shrinks down to `min_size` (default 70 % of
    `size`), then it wraps onto several lines (`wrap=True`) or is cut with '...'. A cut at the
    minimum size is counted in `overflow_count` (the QA audit test asserts it stays 0).
    """
    global overflow_count
    lines = [text]
    if max_w is not None and get_font(size, bold).size(text)[0] > max_w:
        lo = min_size if min_size is not None else max(config.MIN_TEXT_SIZE, int(size * 0.7))
        lo = min(lo, size)
        while size > lo and get_font(size, bold).size(text)[0] > max_w:
            size -= 1
        if get_font(size, bold).size(text)[0] > max_w:
            if wrap:
                lines = wrap_text(text, size, max_w, bold)
            else:
                lines = [truncate(text, size, max_w, bold)]
                overflow_count += 1
                overflow_log.append(text)
    if len(lines) == 1:
        img = _line_image(lines[0], size, color, bold)
        rect = img.get_rect(**{anchor: pos})
        surf.blit(img, rect)
        if audit_rects is not None:
            audit_rects.append((lines[0], rect.copy(), surf.get_clip().copy(), surf.get_size()))
        return rect
    lh = get_font(size, bold).get_linesize()
    imgs = [_line_image(t, size, color, bold) for t in lines]
    block = pygame.Rect(0, 0, max(i.get_width() for i in imgs), lh * len(lines))
    setattr(block, anchor, pos)
    for k, img in enumerate(imgs):
        r = img.get_rect(top=block.top + k * lh)
        if "right" in anchor:
            r.right = block.right
        elif "left" in anchor:
            r.left = block.left
        else:
            r.centerx = block.centerx
        surf.blit(img, r)
    if audit_rects is not None:
        audit_rects.append((" ".join(lines), block.copy(), surf.get_clip().copy(), surf.get_size()))
    return block


class Button:
    """Rectangular text button; handle_event returns True when left-clicked."""

    def __init__(self, rect: pygame.Rect, label: str, size: int = config.BUTTON_FONT,
                 color: tuple[int, int, int] = config.TEXT_COLOR) -> None:
        self.rect = pygame.Rect(rect)
        self.label = label
        self.size = size
        self.color = color

    def handle_event(self, e: pygame.event.Event) -> bool:
        return (e.type == pygame.MOUSEBUTTONDOWN and e.button == 1
                and self.rect.collidepoint(e.pos))

    def draw(self, surf: pygame.Surface) -> None:
        hover = self.rect.collidepoint(pygame.mouse.get_pos())
        fill = config.BUTTON_HOVER_FILL if hover else config.BUTTON_FILL
        pygame.draw.rect(surf, fill, self.rect, border_radius=8)
        border = config.ACCENT_COLOR if hover else config.BUTTON_BORDER
        pygame.draw.rect(surf, border, self.rect, width=2, border_radius=8)
        draw_text(surf, self.label, self.size, self.color, self.rect.center, "center",
                  max_w=self.rect.w - 16, min_size=max(config.MIN_TEXT_SIZE, int(self.size * 0.6)))


# ---------------------------------------------------------------------------------------------------
# Reusable page widgets (settings, library, achievements). Every widget takes its layout from the
# pygame.Rect it is given; on a window resize the scene just calls set_rect() / builds new rects.
# handle_event() never draws and draw() never changes state, so scenes can call them in any order.
# ---------------------------------------------------------------------------------------------------
def fmt_number(v: float, is_int: bool = False) -> str:
    """Compact number text: 3 -> '3', 0.50 -> '0.5', 2.0 -> '2', 0.05 -> '0.05'."""
    if is_int:
        return str(int(round(v)))
    text = f"{v:.6f}".rstrip("0").rstrip(".")
    return "0" if text in ("", "-0") else text


def _caret_on(blink: float) -> bool:
    return (blink % (2 * config.CURSOR_BLINK)) < config.CURSOR_BLINK


class Tabs:
    """A vertical or horizontal list of text tabs. `selected` is the active index.

    Vertical tabs stack from rect.top, each rect.w wide and TAB_ITEM_H tall; horizontal tabs flow
    left to right, sized to their label. handle_event() returns True when a click CHANGED the tab.
    """

    def __init__(self, rect: pygame.Rect, labels: list[str], vertical: bool = True,
                 size: int = config.TAB_FONT, selected: int = 0) -> None:
        self.rect = pygame.Rect(rect)
        self.labels = list(labels)
        self.vertical = vertical
        self.size = size
        self.selected = selected

    def set_rect(self, rect: pygame.Rect) -> None:
        """Move/resize the tab strip (call from on_resize)."""
        self.rect = pygame.Rect(rect)

    def item_rects(self) -> list[pygame.Rect]:
        """One screen rect per label."""
        out: list[pygame.Rect] = []
        pos = self.rect.top if self.vertical else self.rect.left
        for label in self.labels:
            if self.vertical:
                r = pygame.Rect(self.rect.left, pos, self.rect.w, config.TAB_ITEM_H)
                pos += config.TAB_ITEM_H + config.TAB_GAP
            else:
                w = get_font(self.size).size(label)[0] + 2 * config.TAB_PAD
                r = pygame.Rect(pos, self.rect.top, w, self.rect.h)
                pos += w + config.TAB_GAP
            out.append(r)
        return out

    def handle_event(self, e: pygame.event.Event) -> bool:
        """Left click selects a tab; True if the selection changed."""
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            for i, r in enumerate(self.item_rects()):
                if r.collidepoint(e.pos):
                    changed = i != self.selected
                    self.selected = i
                    return changed
        return False

    def draw(self, surf: pygame.Surface) -> None:
        mouse = pygame.mouse.get_pos()
        for i, (r, label) in enumerate(zip(self.item_rects(), self.labels)):
            active = i == self.selected
            if active:
                fill = config.TAB_ACTIVE_FILL
            else:
                fill = config.BUTTON_HOVER_FILL if r.collidepoint(mouse) else config.BUTTON_FILL
            pygame.draw.rect(surf, fill, r, border_radius=6)
            if active:
                pygame.draw.rect(surf, config.ACCENT_COLOR, r, width=2, border_radius=6)
            color = config.ACCENT_COLOR if active else config.TEXT_COLOR
            if self.vertical:
                draw_text(surf, label, self.size, color, (r.left + config.TAB_PAD, r.centery), "midleft")
            else:
                draw_text(surf, label, self.size, color, r.center, "center")


class Slider:
    """Horizontal slider over [lo, hi] with optional snap `step` (0 = continuous).

    Click or drag moves the knob; handle_event() returns True when `value` changed. The knob is
    kept inside the rect, so the rect can be exactly the row cell it lives in.
    """

    def __init__(self, rect: pygame.Rect, lo: float, hi: float, value: float, step: float = 0.0) -> None:
        self.rect = pygame.Rect(rect)
        self.lo, self.hi, self.step = float(lo), float(hi), float(step)
        self.dragging = False
        self.value = value                      # property: clamped and snapped

    @property
    def value(self) -> float:
        return self._value

    @value.setter
    def value(self, v: float) -> None:
        v = min(max(float(v), self.lo), self.hi)
        if self.step > 0:
            v = self.lo + round((v - self.lo) / self.step) * self.step
            v = round(min(max(v, self.lo), self.hi), 10)
        self._value = v

    def set_rect(self, rect: pygame.Rect) -> None:
        self.rect = pygame.Rect(rect)

    def _x_range(self) -> tuple[int, int]:
        return self.rect.left + config.SLIDER_KNOB_R, self.rect.right - config.SLIDER_KNOB_R

    def _x_to_value(self, x: float) -> float:
        a, b = self._x_range()
        frac = 0.0 if b <= a else (x - a) / (b - a)
        return self.lo + min(max(frac, 0.0), 1.0) * (self.hi - self.lo)

    def knob_x(self) -> int:
        """Screen x of the knob centre."""
        a, b = self._x_range()
        span = self.hi - self.lo
        return int(round(a + (0.0 if span <= 0 else (self._value - self.lo) / span) * (b - a)))

    def handle_event(self, e: pygame.event.Event) -> bool:
        old = self._value
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and self.rect.collidepoint(e.pos):
            self.dragging = True
            self.value = self._x_to_value(e.pos[0])
        elif e.type == pygame.MOUSEMOTION and self.dragging:
            self.value = self._x_to_value(e.pos[0])
        elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
            self.dragging = False
        return self._value != old

    def draw(self, surf: pygame.Surface) -> None:
        cy, kx = self.rect.centery, self.knob_x()
        a, b = self._x_range()
        th = config.SLIDER_TRACK_H
        pygame.draw.rect(surf, config.SWITCH_OFF_COLOR, (a, cy - th // 2, b - a, th), border_radius=th // 2)
        pygame.draw.rect(surf, config.ACCENT_COLOR, (a, cy - th // 2, kx - a, th), border_radius=th // 2)
        hover = self.dragging or self.rect.collidepoint(pygame.mouse.get_pos())
        pygame.draw.circle(surf, config.TEXT_COLOR if hover else config.ACCENT_COLOR,
                           (kx, cy), config.SLIDER_KNOB_R)


class NumberField:
    """Click-to-type numeric box. Typed text is applied with Enter, dropped with Esc.

    - `value` is the applied number (clamped to lo/hi when given; rounded when is_int).
    - `focused` is True while editing: the scene should let Esc/Enter reach the field first
      (e.g. do not treat Esc as "Back" while focused) and may slow time like the input box does.
    - handle_event() returns True only when Enter (or a click elsewhere) applied a valid value (read `.value`).
    - The first typed character replaces the old text; clicking elsewhere applies a valid edit (and drops an invalid one).
    - Call update(dt) each frame for the caret blink (optional).
    """

    def __init__(self, rect: pygame.Rect, value: float = 0.0, is_int: bool = False,
                 lo: float | None = None, hi: float | None = None,
                 size: int = config.NUMBER_FIELD_FONT) -> None:
        self.rect = pygame.Rect(rect)
        self.is_int, self.lo, self.hi, self.size = is_int, lo, hi, size
        self.focused = False
        self.text = ""
        self.invalid = False
        self._fresh = False
        self._blink = 0.0
        self._value = 0.0
        self.set_value(value)

    @property
    def value(self) -> float:
        return self._value

    def set_value(self, v: float) -> None:
        """Set the applied value (clamped); does not touch an edit in progress."""
        v = float(v)
        if self.lo is not None:
            v = max(v, self.lo)
        if self.hi is not None:
            v = min(v, self.hi)
        self._value = float(round(v)) if self.is_int else v

    def set_rect(self, rect: pygame.Rect) -> None:
        self.rect = pygame.Rect(rect)

    def display_text(self) -> str:
        """The text shown: the edit buffer while focused, else the formatted value."""
        return self.text if self.focused else fmt_number(self._value, self.is_int)

    def focus(self) -> None:
        """Start editing (the scene uses this for Tab)."""
        if not self.focused:
            self._begin()

    def _begin(self) -> None:
        self.focused, self.invalid, self._fresh, self._blink = True, False, True, 0.0
        self.text = fmt_number(self._value, self.is_int)
        try:
            pygame.key.start_text_input()
        except pygame.error:
            pass

    def _end(self) -> None:
        self.focused, self.invalid = False, False

    def _apply(self) -> bool:
        try:
            v = float(self.text.strip())
        except ValueError:
            v = float("nan")
        if v != v or v in (float("inf"), float("-inf")):
            self.invalid = True
            return False
        self.set_value(v)
        self._end()
        return True

    def update(self, dt: float) -> None:
        self._blink += dt

    def handle_event(self, e: pygame.event.Event) -> bool:
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            if self.rect.collidepoint(e.pos):
                if not self.focused:
                    self._begin()
            elif self.focused:
                ok = self._apply()             # a click elsewhere commits the edit
                if not ok:
                    self._end()
                return ok
        elif not self.focused:
            return False
        elif e.type == pygame.TEXTINPUT:
            if self._fresh:
                self.text, self._fresh = "", False
            ok = [c for c in e.text if c in "0123456789.-+eE"]
            self.text = (self.text + "".join(ok))[:config.NUMBER_FIELD_MAX_CHARS]
            self.invalid, self._blink = False, 0.0
        elif e.type == pygame.KEYDOWN:
            if e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                return self._apply()
            if e.key == pygame.K_ESCAPE:
                self._end()
            elif e.key == pygame.K_BACKSPACE:
                self.text = "" if self._fresh else self.text[:-1]
                self._fresh, self.invalid, self._blink = False, False, 0.0
        return False

    def draw(self, surf: pygame.Surface) -> None:
        hover = self.rect.collidepoint(pygame.mouse.get_pos())
        pygame.draw.rect(surf, config.INPUT_FILL, self.rect, border_radius=6)
        if self.invalid:
            border = config.DANGER_COLOR
        elif self.focused:
            border = config.INPUT_BORDER_FOCUS
        else:
            border = config.ACCENT_COLOR if hover else config.INPUT_BORDER
        pygame.draw.rect(surf, border, self.rect, width=2, border_radius=6)
        text = self.display_text()
        pad = 8
        right = self.rect.left + pad
        if text:
            right = draw_text(surf, text, self.size, config.TEXT_COLOR,
                              (self.rect.left + pad, self.rect.centery), "midleft").right
        if self.focused and _caret_on(self._blink):
            pygame.draw.line(surf, config.TEXT_COLOR, (right + 2, self.rect.top + 6),
                             (right + 2, self.rect.bottom - 7), 2)


class ScrollArea:
    """A clipped viewport onto taller content, scrolled with the wheel while hovered.

    Typical use (content laid out in content space, y from 0 to content_h):
        area.set_content_height(len(rows) * ROW_H)
        area.handle_event(e)                    # wheel, scrollbar drag
        pos = area.to_content(e.pos)            # for clicks, if area.contains(e.pos)
        old = area.begin_clip(surf)             # clip drawing to the viewport
        for i, row in enumerate(rows):
            y = area.to_screen_y(i * ROW_H)     # or area.origin()[1] + i * ROW_H
            if area.visible(i * ROW_H, ROW_H): ...
        area.end_clip(surf, old)
        area.draw_scrollbar(surf)
    One wheel notch scrolls SCROLL_ROWS_PER_NOTCH rows of SCROLL_ROW_PX pixels.
    """

    def __init__(self, rect: pygame.Rect, content_h: int = 0, row_px: int | None = None) -> None:
        self.rect = pygame.Rect(rect)
        self.content_h = int(content_h)
        self.row_px = config.SCROLL_ROW_PX if row_px is None else row_px
        self.scroll = 0.0
        self._drag_dy: float | None = None      # mouse-to-thumb-top offset while dragging the bar

    # -- geometry ------------------------------------------------------------------------------------
    @property
    def max_scroll(self) -> float:
        return float(max(self.content_h - self.rect.h, 0))

    def set_rect(self, rect: pygame.Rect) -> None:
        """Resize the viewport (call from on_resize); the scroll offset is re-clamped."""
        self.rect = pygame.Rect(rect)
        self.set_scroll(self.scroll)

    def set_content_height(self, h: int) -> None:
        self.content_h = int(h)
        self.set_scroll(self.scroll)

    def set_scroll(self, y: float) -> None:
        self.scroll = min(max(float(y), 0.0), self.max_scroll)

    def scroll_to(self, content_y: float, height: float = 0.0) -> None:
        """Scroll the least amount that makes [content_y, content_y + height] visible."""
        if content_y < self.scroll:
            self.set_scroll(content_y)
        elif content_y + height > self.scroll + self.rect.h:
            self.set_scroll(content_y + height - self.rect.h)

    # -- coordinate helpers --------------------------------------------------------------------------
    def contains(self, pos: tuple[int, int]) -> bool:
        """True if a screen position is inside the viewport (ignore clicks on clipped rows)."""
        return self.rect.collidepoint(pos)

    def to_content(self, pos: tuple[int, int]) -> tuple[int, int]:
        """Screen position -> content coordinates."""
        return pos[0] - self.rect.x, int(pos[1] - self.rect.y + self.scroll)

    def to_screen_y(self, content_y: float) -> int:
        return int(round(self.rect.y + content_y - self.scroll))

    def origin(self) -> tuple[int, int]:
        """Screen position of content point (0, 0): add content coordinates to draw."""
        return self.rect.x, int(round(self.rect.y - self.scroll))

    def offset_rect(self, r: pygame.Rect) -> pygame.Rect:
        """A content-space rect moved to where it currently appears on screen."""
        ox, oy = self.origin()
        return r.move(ox, oy)

    def visible(self, content_y: float, height: float) -> bool:
        return content_y + height > self.scroll and content_y < self.scroll + self.rect.h

    def begin_clip(self, surf: pygame.Surface) -> pygame.Rect:
        """Clip drawing to the viewport; pass the returned value to end_clip()."""
        old = surf.get_clip()
        surf.set_clip(self.rect.clip(old))
        return old

    def end_clip(self, surf: pygame.Surface, old: pygame.Rect) -> None:
        surf.set_clip(old)

    # -- input / drawing -----------------------------------------------------------------------------
    def _thumb(self) -> pygame.Rect | None:
        if self.max_scroll <= 0:
            return None
        h = self.rect.h
        th = max(int(h * h / self.content_h), config.SCROLLBAR_MIN_THUMB)
        ty = self.rect.top + int((h - th) * self.scroll / self.max_scroll)
        return pygame.Rect(self.rect.right - config.SCROLLBAR_W, ty, config.SCROLLBAR_W, th)

    def handle_event(self, e: pygame.event.Event, mouse_pos: tuple[int, int] | None = None) -> bool:
        """Wheel while hovered (mouse_pos defaults to the real mouse) and scrollbar dragging.

        Returns True when the scroll offset changed."""
        old = self.scroll
        if e.type == pygame.MOUSEWHEEL:
            pos = pygame.mouse.get_pos() if mouse_pos is None else mouse_pos
            if self.rect.collidepoint(pos):
                self.set_scroll(self.scroll - e.y * config.SCROLL_ROWS_PER_NOTCH * self.row_px)
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            thumb = self._thumb()
            if thumb is not None and thumb.inflate(10, 0).collidepoint(e.pos):
                self._drag_dy = e.pos[1] - thumb.top
        elif e.type == pygame.MOUSEMOTION and self._drag_dy is not None:
            thumb = self._thumb()
            room = self.rect.h - (thumb.h if thumb else 0)
            if room > 0:
                self.set_scroll((e.pos[1] - self._drag_dy - self.rect.top) / room * self.max_scroll)
        elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
            self._drag_dy = None
        return self.scroll != old

    def draw_scrollbar(self, surf: pygame.Surface) -> None:
        """Thin scrollbar on the right edge (nothing when the content fits)."""
        thumb = self._thumb()
        if thumb is not None:
            pygame.draw.rect(surf, config.SCROLLBAR_COLOR, thumb, border_radius=config.SCROLLBAR_W // 2)


def draw_icon(surf: pygame.Surface, kind: str, rect: pygame.Rect, color: tuple[int, ...]) -> None:
    """Blit the tinted icon `kind` (any name from ui/icons.py: plus, minus, reset, play, pause, ...) centred in `rect`."""
    side = max(min(rect.w, rect.h) - config.ICON_INSET, 4)
    img = icons.icon(kind, side, color)
    surf.blit(img, img.get_rect(center=rect.center))


class IconButton:
    """Small square button showing a draw_icon() kind; handle_event() returns True on a left click."""

    def __init__(self, rect: pygame.Rect, kind: str) -> None:
        self.rect = pygame.Rect(rect)
        self.kind = kind
        self.enabled = True

    def set_rect(self, rect: pygame.Rect) -> None:
        self.rect = pygame.Rect(rect)

    def handle_event(self, e: pygame.event.Event) -> bool:
        return (self.enabled and e.type == pygame.MOUSEBUTTONDOWN and e.button == 1
                and self.rect.collidepoint(e.pos))

    def draw(self, surf: pygame.Surface) -> None:
        hover = self.enabled and self.rect.collidepoint(pygame.mouse.get_pos())
        pygame.draw.rect(surf, config.BUTTON_HOVER_FILL if hover else config.BUTTON_FILL, self.rect,
                         border_radius=5)
        pygame.draw.rect(surf, config.ACCENT_COLOR if hover else config.BUTTON_BORDER, self.rect,
                         width=1, border_radius=5)
        draw_icon(surf, self.kind, self.rect, config.TEXT_COLOR if self.enabled else config.DIM_TEXT_COLOR)
