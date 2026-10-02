"""Library scene: tabbed help pages. Content is data in library_data.py; this file only lays it out."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pygame

from ascensus import config, view
from ascensus.data import library_data
from ascensus.scenes.base import Scene
from ascensus.ui.minigraph import render_minigraph
from ascensus.ui.widgets import Button, ScrollArea, Tabs, draw_text, get_font

_wrap_cache: dict[tuple[str, int, int], list[str]] = {}


def wrap_text(text: str, size: int, max_w: int) -> list[str]:
    """Greedy word wrap of one line of text to `max_w` px with the cached default font.

    An empty string gives [""]; a single word wider than max_w stays on its own line."""
    key = (text, size, max_w)
    hit = _wrap_cache.get(key)
    if hit is not None:
        return hit
    if len(_wrap_cache) > 4000:
        _wrap_cache.clear()
    font = get_font(size)
    lines: list[str] = []
    cur = ""
    for word in text.split(" "):
        trial = word if not cur else f"{cur} {word}"
        if cur and font.size(trial)[0] > max_w:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    lines.append(cur)
    _wrap_cache[key] = lines
    return lines


def line_height(size: int) -> int:
    return get_font(size).get_linesize()


# ---------------------------------------------------------------------------------------------------
# Layout (pure functions of the content width; positions are in content space, y from 0)
# ---------------------------------------------------------------------------------------------------
@dataclass
class TextItem:
    """One wrapped line of a text tab at content-space y."""
    y: int
    text: str
    size: int
    kind: str                       # "head" or "body"


def layout_paragraphs(paras: list[tuple[str, list[str]]], width: int) -> tuple[list[TextItem], int]:
    """Wrapped lines for a (title, [lines]) tab and the total content height."""
    items: list[TextItem] = []
    y = 0
    for title, lines in paras:
        items.append(TextItem(y, title, config.LIB_HEAD_FONT, "head"))
        y += line_height(config.LIB_HEAD_FONT) + 4
        for line in lines:
            for piece in wrap_text(line, config.LIB_TEXT_FONT, width):
                items.append(TextItem(y, piece, config.LIB_TEXT_FONT, "body"))
                y += line_height(config.LIB_TEXT_FONT)
        y += config.LIB_PARA_GAP
    return items, y


@dataclass
class CardLayout:
    """A function card (or a group heading when `card` is None) in content space."""
    rect: pygame.Rect
    card: dict | None
    heading: str = ""
    explanation: list[str] | None = None

    @property
    def graph_rect(self) -> pygame.Rect:
        gw, gh = config.LIB_GRAPH_SIZE
        return pygame.Rect(self.rect.x + config.LIB_CARD_PAD, self.rect.y + config.LIB_CARD_PAD, gw, gh)


def layout_function_cards(cards: list[dict], width: int) -> tuple[list[CardLayout], int]:
    """One full-width card per function with group headings; returns (entries, total height)."""
    pad, gap = config.LIB_CARD_PAD, config.LIB_CARD_GAP
    gw, gh = config.LIB_GRAPH_SIZE
    text_w = max(width - gw - 3 * pad, 120)
    out: list[CardLayout] = []
    y = 0
    group = None
    for card in cards:
        if card["group"] != group:
            group = card["group"]
            h = line_height(config.LIB_GROUP_FONT) + gap
            out.append(CardLayout(pygame.Rect(0, y, width, h), None, heading=group))
            y += h
        expl = wrap_text(card["explanation"], config.LIB_TEXT_FONT, text_w)
        text_h = (line_height(config.LIB_NAME_FONT) + line_height(config.LIB_SMALL_FONT)
                  + len(expl) * line_height(config.LIB_TEXT_FONT) + line_height(config.LIB_SMALL_FONT) + 6)
        h = max(gh, text_h) + 2 * pad
        out.append(CardLayout(pygame.Rect(0, y, width, h), card, explanation=expl))
        y += h + gap
    return out, y


# ---------------------------------------------------------------------------------------------------
# The scene
# ---------------------------------------------------------------------------------------------------
class LibraryScene(Scene):
    """Tabs | Functions, Syntax, Variables, ... `back()` returns the scene to go to on Esc / Back."""

    def __init__(self, back: Callable[[], object]) -> None:
        super().__init__()
        self.back = back
        m = config.PAGE_MARGIN
        self.tabs = Tabs(pygame.Rect(m, config.PAGE_HEADER_H, config.LIB_TABS_W, 300), library_data.TABS)
        self.area = ScrollArea(pygame.Rect(0, 0, 100, 100))
        self.back_btn = Button(pygame.Rect(m, m // 2, *config.PAGE_BACK_SIZE), "Back", size=28)
        self.entries: list[CardLayout] = []
        self.items: list[TextItem] = []
        self._graphs: dict[str, pygame.Surface] = {}     # lazily rendered mini graphs, by example text
        self._graph_budget = config.LIB_GRAPHS_PER_FRAME
        self.on_resize()

    @property
    def tab_name(self) -> str:
        return library_data.TABS[self.tabs.selected]

    def _content_width(self) -> int:
        return max(self.area.rect.w - config.SCROLLBAR_W - 10, 100)

    def on_resize(self) -> None:
        """Re-lay-out tabs and content for the current view size (keeps the scroll position)."""
        m = config.PAGE_MARGIN
        top = config.PAGE_HEADER_H
        self.tabs.set_rect(pygame.Rect(m, top, config.LIB_TABS_W, view.H - top - m))
        left = m + config.LIB_TABS_W + m
        self.area.set_rect(pygame.Rect(left, top, max(view.W - left - m, 100), max(view.H - top - m, 50)))
        self._relayout()

    def _relayout(self) -> None:
        w = self._content_width()
        if self.tab_name == "Functions":
            self.entries, h = layout_function_cards(library_data.FUNCTIONS, w)
            self.items = []
        else:
            self.items, h = layout_paragraphs(library_data.paragraphs(self.tab_name), w)
            self.entries = []
        self.area.set_content_height(h)

    def select(self, index: int) -> None:
        """Switch tab (scroll resets to the top)."""
        self.tabs.selected = max(0, min(index, len(library_data.TABS) - 1))
        self.area.set_scroll(0)
        self._relayout()

    # -- input ---------------------------------------------------------------------------------------
    def handle_event(self, e: pygame.event.Event) -> None:
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_ESCAPE:
                self.next_scene = self.back()
            elif e.key in (pygame.K_DOWN, pygame.K_UP):
                self.area.set_scroll(self.area.scroll + (1 if e.key == pygame.K_DOWN else -1) * self.area.row_px)
            elif e.key in (pygame.K_PAGEDOWN, pygame.K_PAGEUP):
                self.area.set_scroll(self.area.scroll + (1 if e.key == pygame.K_PAGEDOWN else -1) * self.area.rect.h)
            return
        if self.back_btn.handle_event(e):
            self.next_scene = self.back()
        elif self.tabs.handle_event(e):
            self.select(self.tabs.selected)
        else:
            self.area.handle_event(e)

    # -- drawing -------------------------------------------------------------------------------------
    def graph_for(self, card: dict) -> pygame.Surface | None:
        """The card's mini graph, rendered lazily (at most LIB_GRAPHS_PER_FRAME new ones per frame)."""
        key = card["example"]
        surf = self._graphs.get(key)
        if surf is None and self._graph_budget > 0:
            self._graph_budget -= 1
            surf = self._graphs[key] = render_minigraph(key, config.LIB_GRAPH_SIZE, config.LIB_GRAPH_UNIT)
        return surf

    def draw(self, screen: pygame.Surface) -> None:
        self._graph_budget = config.LIB_GRAPHS_PER_FRAME
        screen.fill(config.BG_COLOR)
        self.back_btn.draw(screen)
        draw_text(screen, "Library", config.PAGE_TITLE_FONT, config.ACCENT_COLOR,
                  (config.PAGE_MARGIN * 2 + config.PAGE_BACK_SIZE[0], config.PAGE_MARGIN // 2 + 20), "midleft")
        self.tabs.draw(screen)
        old = self.area.begin_clip(screen)
        if self.tab_name == "Functions":
            self._draw_cards(screen)
        else:
            self._draw_text(screen)
        self.area.end_clip(screen, old)
        self.area.draw_scrollbar(screen)

    def _draw_text(self, screen: pygame.Surface) -> None:
        ox, _ = self.area.origin()
        for it in self.items:
            if not self.area.visible(it.y, line_height(it.size)):
                continue
            color = config.ACCENT_COLOR if it.kind == "head" else config.TEXT_COLOR
            draw_text(screen, it.text, it.size, color, (ox, self.area.to_screen_y(it.y)))

    def _draw_cards(self, screen: pygame.Surface) -> None:
        pad = config.LIB_CARD_PAD
        for ent in self.entries:
            if not self.area.visible(ent.rect.y, ent.rect.h):
                continue
            r = self.area.offset_rect(ent.rect)
            if ent.card is None:
                draw_text(screen, ent.heading, config.LIB_GROUP_FONT, config.DIM_TEXT_COLOR, r.topleft)
                continue
            card = ent.card
            pygame.draw.rect(screen, config.LIB_CARD_FILL, r, border_radius=8)
            pygame.draw.rect(screen, config.LIB_CARD_BORDER, r, width=1, border_radius=8)
            gr = self.area.offset_rect(ent.graph_rect)
            graph = self.graph_for(card)
            if graph is not None:
                screen.blit(graph, gr)
            pygame.draw.rect(screen, config.LIB_CARD_BORDER, gr, width=1)
            x, y = gr.right + pad, r.y + pad
            draw_text(screen, card["name"], config.LIB_NAME_FONT, config.TEXT_COLOR, (x, y))
            if card["aliases"]:
                nw = get_font(config.LIB_NAME_FONT).size(card["name"])[0]
                draw_text(screen, "also: " + ", ".join(card["aliases"]), config.LIB_SMALL_FONT,
                          config.DIM_TEXT_COLOR, (x + nw + 14, y + 8))
            y += line_height(config.LIB_NAME_FONT)
            draw_text(screen, card["syntax"], config.LIB_SMALL_FONT, config.ACCENT_COLOR, (x, y))
            y += line_height(config.LIB_SMALL_FONT) + 6
            for line in ent.explanation or []:
                draw_text(screen, line, config.LIB_TEXT_FONT, config.TEXT_COLOR, (x, y))
                y += line_height(config.LIB_TEXT_FONT)
            draw_text(screen, "Example: " + card["example"], config.LIB_SMALL_FONT, config.DIM_TEXT_COLOR, (x, y))
