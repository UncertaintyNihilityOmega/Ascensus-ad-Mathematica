"""Equation text input: focus, cursor editing, error line and edit-mode label."""
from __future__ import annotations

import pygame

from .. import config, view
from .widgets import draw_text, get_font


_fallback_clip = ""      # used when pygame.scrap is unavailable (no display, headless runs)


def get_clipboard() -> str:
    """System clipboard text via pygame.scrap; falls back to the in-app clipboard on any failure."""
    try:
        if not pygame.scrap.get_init():
            pygame.scrap.init()
        text = pygame.scrap.get_text()
        if isinstance(text, bytes):
            text = text.decode("utf-8", "ignore")
        return _fallback_clip if text is None else text.replace("\x00", "")
    except Exception:
        return _fallback_clip


def set_clipboard(text: str) -> None:
    """Copy text to the system clipboard (and the in-app fallback); failures are ignored."""
    global _fallback_clip
    _fallback_clip = text
    try:
        if not pygame.scrap.get_init():
            pygame.scrap.init()
        pygame.scrap.put_text(text)
    except Exception:
        pass


def clean_paste(text: str) -> str:
    """Newlines and tabs become single spaces; non-printable characters are dropped."""
    text = text.replace("\r\n", " ").replace("\r", " ").replace("\n", " ").replace("\t", " ")
    return "".join(c for c in text if c.isprintable())


class InputBox:
    """handle_event returns 'submit', 'cancel' or None; the owner decides what submit means."""

    def __init__(self) -> None:
        self.rect = pygame.Rect(0, 0, 0, 0)
        self.on_resize()
        self.text = ""
        self.cursor = 0
        self.anchor: int | None = None        # other end of the selection (cursor is one end)
        self.focused = False
        self.edit_index: int | None = None
        self.error = ""
        self.error_timer = 0.0
        self.blink = 0.0

    def on_resize(self) -> None:
        """Re-centre the box at the bottom of the current view."""
        w, h = config.INPUT_SIZE
        self.rect = pygame.Rect((view.W - w) // 2, view.H - config.INPUT_BOTTOM_MARGIN - h, w, h)

    def focus(self) -> None:
        if not self.focused:
            self.focused = True
            self.blink = 0.0
            pygame.key.start_text_input()

    def blur(self) -> None:
        if self.focused:
            self.focused = False
            pygame.key.stop_text_input()

    def set_text(self, text: str, edit_index: int | None = None) -> None:
        """Load text (the sidebar's Edit uses this) and focus; edit_index None = normal add."""
        self.text, self.cursor, self.edit_index = text, len(text), edit_index
        self.anchor = None
        self.error, self.error_timer = "", 0.0
        self.focus()

    def clear(self) -> None:
        """Empty the box, leave edit mode and unfocus (after a successful submit)."""
        self.text, self.cursor, self.edit_index, self.anchor = "", 0, None, None
        self.blur()

    # --- selection / clipboard -------------------------------------------
    def selection(self) -> tuple[int, int] | None:
        """(start, end) of the selected text, or None when nothing is selected."""
        if self.anchor is None:
            return None
        a, b = sorted((min(self.anchor, len(self.text)), min(self.cursor, len(self.text))))
        return (a, b) if a != b else None

    def _insert(self, chars: str) -> None:
        """Replace the selection (if any) with chars, respecting MAX_EQUATION_LEN."""
        sel = self.selection()
        if sel:
            self.text = self.text[:sel[0]] + self.text[sel[1]:]
            self.cursor = sel[0]
        self.anchor = None
        room = config.MAX_EQUATION_LEN - len(self.text)
        chars = chars[:max(room, 0)]
        self.text = self.text[:self.cursor] + chars + self.text[self.cursor:]
        self.cursor += len(chars)

    def _move(self, pos: int, extend: bool) -> None:
        """Move the cursor; with extend the selection grows from where it started."""
        if extend:
            if self.anchor is None:
                self.anchor = self.cursor
        else:
            self.anchor = None
        self.cursor = max(0, min(len(self.text), pos))

    def _clipboard_key(self, k: int) -> None:
        """Ctrl+A / C / X / V."""
        sel = self.selection()
        if k == pygame.K_a:
            self.anchor, self.cursor = 0, len(self.text)
        elif k in (pygame.K_c, pygame.K_x):
            set_clipboard(self.text[sel[0]:sel[1]] if sel else self.text)
            if k == pygame.K_x and sel:
                self._insert("")
        elif k == pygame.K_v:
            self._insert(clean_paste(get_clipboard()))

    def show_error(self, msg: str) -> None:
        self.error, self.error_timer = msg, config.ERROR_SHOW_TIME

    def update(self, real_dt: float) -> None:
        self.blink = (self.blink + real_dt) % (2 * config.CURSOR_BLINK)
        self.error_timer = max(0.0, self.error_timer - real_dt)
        if self.error_timer == 0.0:
            self.error = ""

    def handle_event(self, e: pygame.event.Event) -> str | None:
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and self.rect.collidepoint(e.pos):
            self.focus()
            return None
        if not self.focused:
            if e.type == pygame.KEYDOWN and e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.focus()                # this Enter only focuses; it never submits
            return None
        if e.type == pygame.TEXTINPUT:
            self._insert("".join(c for c in e.text if c.isprintable()))
            self.blink = 0.0
        elif e.type == pygame.KEYDOWN:
            return self._key(e.key, getattr(e, "mod", 0))
        return None

    def _key(self, k: int, mod: int = 0) -> str | None:
        self.blink = 0.0
        if mod & pygame.KMOD_CTRL and k in (pygame.K_a, pygame.K_c, pygame.K_x, pygame.K_v):
            self._clipboard_key(k)
            return None
        shift, sel = bool(mod & pygame.KMOD_SHIFT), self.selection()
        if k in (pygame.K_RETURN, pygame.K_KP_ENTER):
            return "submit"
        if k == pygame.K_ESCAPE:
            if self.edit_index is not None:
                self.text, self.cursor, self.edit_index = "", 0, None
            self.anchor = None
            self.blur()
            return "cancel"
        if k in (pygame.K_BACKSPACE, pygame.K_DELETE) and sel:
            self._insert("")
        elif k == pygame.K_BACKSPACE and self.cursor > 0:
            self.text = self.text[:self.cursor - 1] + self.text[self.cursor:]
            self.cursor -= 1
        elif k == pygame.K_DELETE:
            self.text = self.text[:self.cursor] + self.text[self.cursor + 1:]
        elif k == pygame.K_LEFT:
            self._move(sel[0] if sel and not shift else self.cursor - 1, shift)
        elif k == pygame.K_RIGHT:
            self._move(sel[1] if sel and not shift else self.cursor + 1, shift)
        elif k == pygame.K_HOME:
            self._move(0, shift)
        elif k == pygame.K_END:
            self._move(len(self.text), shift)
        return None

    def draw(self, screen: pygame.Surface) -> None:
        r = self.rect
        pygame.draw.rect(screen, config.INPUT_FILL, r, border_radius=6)
        border = config.INPUT_BORDER_FOCUS if self.focused else config.INPUT_BORDER
        pygame.draw.rect(screen, border, r, width=2, border_radius=6)
        gap = config.INPUT_ERROR_GAP
        if self.edit_index is not None:
            draw_text(screen, f"Editing #{self.edit_index + 1}", config.INPUT_LABEL_FONT,
                      config.ACCENT_COLOR, (r.left, r.top - 4), "bottomleft")
            gap += config.INPUT_LABEL_FONT
        if self.error:
            draw_text(screen, self.error, config.INPUT_ERROR_FONT, config.DANGER_COLOR,
                      (r.centerx, r.top - gap), "midbottom")
        font = get_font(config.INPUT_FONT)
        inner = r.inflate(-2 * config.INPUT_PAD, -4)
        if not self.text and not self.focused:
            draw_text(screen, config.INPUT_PLACEHOLDER, config.INPUT_FONT, config.DIM_TEXT_COLOR,
                      (inner.left, r.centery), "midleft")
            return
        cursor_x = font.size(self.text[:self.cursor])[0]
        scroll = max(0, cursor_x - inner.width + 4)
        old_clip = screen.get_clip()
        screen.set_clip(inner)
        sel = self.selection()
        if sel:
            x0 = inner.left - scroll + font.size(self.text[:sel[0]])[0]
            x1 = inner.left - scroll + font.size(self.text[:sel[1]])[0]
            pygame.draw.rect(screen, config.INPUT_SELECT_COLOR, (x0, r.top + 6, x1 - x0, r.height - 12))
        img = font.render(self.text, True, config.TEXT_COLOR)
        screen.blit(img, img.get_rect(midleft=(inner.left - scroll, r.centery)))
        if self.focused and self.blink < config.CURSOR_BLINK:
            x = inner.left + cursor_x - scroll
            pygame.draw.line(screen, config.TEXT_COLOR, (x, r.top + 8), (x, r.bottom - 8), 2)
        screen.set_clip(old_clip)
