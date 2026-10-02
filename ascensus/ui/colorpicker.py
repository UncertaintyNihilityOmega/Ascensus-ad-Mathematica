"""The 'Custom' row of the sidebar's colour popup: hue strip, brightness strip, preview swatch, #RRGGBB box.

Pure widgets (they only need pygame to draw): the sidebar owns the popup and applies the colours that
`CustomRow.handle_event` returns. Strips apply on click and on release (not on every drag step), the
hex box applies with Enter.
"""
from __future__ import annotations

import colorsys

import pygame

from ascensus import config
from ascensus.ui.widgets import draw_text

Color = tuple[int, int, int]
HEX_DIGITS = "0123456789abcdefABCDEF"


def hsv_to_rgb(h: float, s: float, v: float) -> Color:
    """HSV in 0..1 to an (r, g, b) tuple of ints."""
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, min(max(s, 0.0), 1.0), min(max(v, 0.0), 1.0))
    return int(round(r * 255)), int(round(g * 255)), int(round(b * 255))


def rgb_to_hsv(color: Color) -> tuple[float, float, float]:
    """(r, g, b) ints to HSV in 0..1."""
    return colorsys.rgb_to_hsv(*(c / 255 for c in color[:3]))


def to_hex(color: Color) -> str:
    """'#RRGGBB' text of a colour."""
    return "#{:02X}{:02X}{:02X}".format(*(int(c) for c in color[:3]))


def parse_hex(text: str) -> Color | None:
    """'#RRGGBB', 'RRGGBB' or '#RGB' (any case, surrounding spaces ok) to a colour, else None."""
    t = text.strip().lstrip("#")
    if len(t) == 3:
        t = "".join(c * 2 for c in t)
    if len(t) != 6 or any(c not in HEX_DIGITS for c in t):
        return None
    return int(t[0:2], 16), int(t[2:4], 16), int(t[4:6], 16)


class Strip:
    """A horizontal gradient strip with a marker; `kind` is 'hue' or 'value'. Click or drag sets `pos` (0..1)."""

    def __init__(self, kind: str) -> None:
        self.kind = kind
        self.rect = pygame.Rect(0, 0, 10, 10)
        self.pos = 0.0
        self.dragging = False
        self._cache: dict[tuple, pygame.Surface] = {}

    def pos_at(self, x: int) -> float:
        """Strip position (0..1) under screen x."""
        return min(max((x - self.rect.left) / max(self.rect.w - 1, 1), 0.0), 1.0)

    def _image(self, hue: float, sat: float) -> pygame.Surface:
        key = (self.rect.size, int(hue * 360) if self.kind == "value" else 0, int(sat * 100))
        img = self._cache.get(key)
        if img is None:
            if len(self._cache) > 48:
                self._cache.clear()
            img = self._cache[key] = pygame.Surface(self.rect.size)
            for x in range(self.rect.w):
                t = x / max(self.rect.w - 1, 1)
                col = hsv_to_rgb(t, 1.0, 1.0) if self.kind == "hue" else hsv_to_rgb(hue, sat, t)
                pygame.draw.line(img, col, (x, 0), (x, self.rect.h))
        return img

    def draw(self, surf: pygame.Surface, hue: float = 0.0, sat: float = 1.0) -> None:
        """Gradient (the value strip fades black to the current hue/saturation) plus the marker."""
        surf.blit(self._image(hue, sat), self.rect)
        pygame.draw.rect(surf, config.PICKER_BORDER, self.rect, width=1)
        mx = self.rect.left + int(self.pos * (self.rect.w - 1))
        mark = pygame.Rect(mx - 2, self.rect.top - 2, 5, self.rect.h + 4)
        pygame.draw.rect(surf, config.TEXT_COLOR, mark, width=2, border_radius=2)


class HexField:
    """A small '#RRGGBB' text box: click to type, Enter applies (via CustomRow), Esc drops the edit."""

    def __init__(self) -> None:
        self.rect = pygame.Rect(0, 0, 10, 10)
        self.text = "#FFFFFF"
        self.focused = False
        self.invalid = False
        self._fresh = False

    def focus(self) -> None:
        self.focused, self.invalid, self._fresh = True, False, True
        try:
            pygame.key.start_text_input()
        except pygame.error:
            pass

    def blur(self) -> None:
        self.focused = self.invalid = False


class CustomRow:
    """Hue strip + brightness strip + preview swatch + hex box, laid out in a rect handed to `set_rect`."""

    def __init__(self) -> None:
        self.hue, self.sat, self.val = 0.0, 1.0, 1.0
        self.hue_strip, self.val_strip = Strip("hue"), Strip("value")
        self.hex = HexField()
        self.preview = pygame.Rect(0, 0, 10, 10)
        self.set_color((255, 255, 255))

    @staticmethod
    def height() -> int:
        """Total height of the row (two strips, a gap, the preview/hex line)."""
        return 2 * config.PICKER_STRIP_H + config.PICKER_STRIP_GAP + config.PICKER_SEP + config.PICKER_PREVIEW

    @property
    def color(self) -> Color:
        return hsv_to_rgb(self.hue, self.sat, self.val)

    def set_rect(self, rect: pygame.Rect) -> None:
        """Lay the parts out inside `rect` (width is free, height is `height()`)."""
        h = config.PICKER_STRIP_H
        self.hue_strip.rect = pygame.Rect(rect.x, rect.y, rect.w, h)
        self.val_strip.rect = pygame.Rect(rect.x, rect.y + h + config.PICKER_STRIP_GAP, rect.w, h)
        y = self.val_strip.rect.bottom + config.PICKER_SEP
        p = config.PICKER_PREVIEW
        self.preview = pygame.Rect(rect.x, y, p, p)
        self.hex.rect = pygame.Rect(self.preview.right + 6, y, max(rect.right - self.preview.right - 6, 20), p)

    def set_color(self, color: Color) -> None:
        """Show `color` (from a row or from outside): sets hue/saturation/brightness, strip markers and hex."""
        self.hue, self.sat, self.val = rgb_to_hsv(color)
        if self.sat < 0.02:                  # grays have no hue: keep the old strip position
            self.hue = self.hue_strip.pos
        self._sync(hex_text=True)

    def _sync(self, hex_text: bool) -> None:
        self.hue_strip.pos, self.val_strip.pos = self.hue, self.val
        if hex_text and not self.hex.focused:
            self.hex.text = to_hex(self.color)

    # --- events ----------------------------------------------------------------------------------
    def handle_event(self, e: pygame.event.Event) -> Color | None:
        """Feed any event; returns a colour to apply (strip click/release, Enter in the hex box) or None."""
        hs, vs = self.hue_strip, self.val_strip
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            if self.hex.rect.collidepoint(e.pos):
                if not self.hex.focused:
                    self.hex.focus()
                return None
            self.hex.blur()
            for strip in (hs, vs):
                if strip.rect.inflate(0, 4).collidepoint(e.pos):
                    strip.dragging = True
                    return self._strip_to(strip, e.pos[0])
        elif e.type == pygame.MOUSEMOTION and (hs.dragging or vs.dragging):
            self._strip_to(hs if hs.dragging else vs, e.pos[0])          # live preview, applied on release
        elif e.type == pygame.MOUSEBUTTONUP and e.button == 1 and (hs.dragging or vs.dragging):
            strip = hs if hs.dragging else vs
            hs.dragging = vs.dragging = False
            return self._strip_to(strip, e.pos[0])
        elif self.hex.focused and e.type in (pygame.TEXTINPUT, pygame.KEYDOWN):
            return self._hex_key(e)
        return None

    def _strip_to(self, strip: Strip, x: int) -> Color:
        strip.pos = strip.pos_at(x)
        if strip is self.hue_strip:
            self.hue, self.sat = strip.pos, 1.0              # a rainbow pick is always vivid
        else:
            self.val = strip.pos
        self._sync(hex_text=True)
        return self.color

    def _hex_key(self, e: pygame.event.Event) -> Color | None:
        hx = self.hex
        if e.type == pygame.TEXTINPUT:
            if hx._fresh:
                hx.text, hx._fresh = "", False
            hx.text = (hx.text + "".join(c for c in e.text if c in HEX_DIGITS + "#"))[:config.PICKER_HEX_MAX]
            hx.invalid = False
        elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            col = parse_hex(hx.text)
            if col is None:
                hx.invalid = True
                return None
            hx.blur()
            self.set_color(col)
            return self.color
        elif e.key == pygame.K_BACKSPACE:
            hx.text, hx._fresh, hx.invalid = ("" if hx._fresh else hx.text[:-1]), False, False
        elif e.key == pygame.K_ESCAPE:
            hx.blur()
            self._sync(hex_text=True)
        return None

    # --- drawing ---------------------------------------------------------------------------------
    def draw(self, surf: pygame.Surface) -> None:
        self.hue_strip.draw(surf)
        self.val_strip.draw(surf, self.hue, self.sat)
        pygame.draw.rect(surf, self.color, self.preview, border_radius=3)
        pygame.draw.rect(surf, config.PICKER_BORDER, self.preview, width=1, border_radius=3)
        hx = self.hex
        pygame.draw.rect(surf, config.INPUT_FILL, hx.rect, border_radius=4)
        border = config.DANGER_COLOR if hx.invalid else (config.ACCENT_COLOR if hx.focused else config.INPUT_BORDER)
        pygame.draw.rect(surf, border, hx.rect, width=2, border_radius=4)
        text = hx.text + ("|" if hx.focused and not hx._fresh else "")
        draw_text(surf, text, config.PICKER_HEX_FONT, config.TEXT_COLOR if hx.focused else config.DIM_TEXT_COLOR,
                  (hx.rect.left + 6, hx.rect.centery), "midleft", max_w=hx.rect.w - 10)
