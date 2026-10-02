"""Library scene: word wrap, layout functions, tab switching, scrolling, lazy graphs, resize."""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402
import pytest  # noqa: E402

from ascensus import config, view  # noqa: E402
from ascensus.data import library_data  # noqa: E402
from ascensus.scenes.library_page import LibraryScene, layout_function_cards, layout_paragraphs, line_height, wrap_text  # noqa: E402
from ascensus.ui import widgets  # noqa: E402


@pytest.fixture(autouse=True)
def _pg():
    pygame.init()
    screen = pygame.display.set_mode((1280, 720))
    widgets._fonts.clear()
    widgets._text_cache.clear()
    view.set_size(1280, 720)
    yield screen
    view.set_size(1280, 720)
    widgets._fonts.clear()
    widgets._text_cache.clear()
    pygame.quit()


def click(scene, pos):
    scene.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1))


def key(scene, k):
    scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=k, mod=0, unicode=""))


def test_wrap_text_respects_width_and_keeps_words():
    text = "the quick brown fox jumps over the lazy dog " * 4
    lines = wrap_text(text.strip(), 24, 200)
    assert len(lines) > 3
    font = widgets.get_font(24)
    assert all(font.size(line)[0] <= 200 for line in lines)
    assert " ".join(lines).split() == text.split()
    assert wrap_text("", 24, 200) == [""]
    assert wrap_text("supercalifragilisticexpialidocious", 24, 20) == ["supercalifragilisticexpialidocious"]


def test_layout_paragraphs_is_monotonic_and_fits():
    for tab in library_data.TABS[1:]:
        items, h = layout_paragraphs(library_data.paragraphs(tab), 500)
        ys = [it.y for it in items]
        assert ys == sorted(ys) and h > ys[-1]
        assert all(widgets.get_font(it.size).size(it.text)[0] <= 500 for it in items)
    narrow = layout_paragraphs(library_data.paragraphs("Syntax"), 200)[1]
    wide = layout_paragraphs(library_data.paragraphs("Syntax"), 1000)[1]
    assert narrow > wide                                    # narrower -> more wrapped lines


def test_layout_function_cards_stack_without_overlap():
    entries, h = layout_function_cards(library_data.FUNCTIONS, 900)
    cards = [e for e in entries if e.card is not None]
    assert len(cards) == len(library_data.FUNCTIONS)
    heads = [e.heading for e in entries if e.card is None]
    assert heads == list(dict.fromkeys(c["group"] for c in library_data.FUNCTIONS))
    for a, b in zip(entries, entries[1:]):
        assert a.rect.bottom <= b.rect.top
    assert entries[-1].rect.bottom <= h
    gw, gh = config.LIB_GRAPH_SIZE
    assert all(c.rect.h >= gh + 2 * config.LIB_CARD_PAD and c.graph_rect.size == (gw, gh) for c in cards)
    assert cards[0].graph_rect.right + config.LIB_CARD_PAD <= cards[0].rect.right


def test_tab_switching_and_scroll_reset():
    sc = LibraryScene(lambda: "back")
    assert sc.tab_name == "Functions" and sc.entries and not sc.items
    sc.area.set_scroll(500)
    assert sc.area.scroll == 500
    click(sc, sc.tabs.item_rects()[1].center)
    assert sc.tab_name == "Syntax" and sc.items and not sc.entries and sc.area.scroll == 0
    for i, name in enumerate(library_data.TABS):
        sc.select(i)
        assert sc.tab_name == name and sc.area.content_h > 0
    sc.select(99)
    assert sc.tab_name == library_data.TABS[-1]


def test_wheel_and_keys_scroll_within_bounds():
    sc = LibraryScene(lambda: "back")
    pos = sc.area.rect.center
    sc.area.handle_event(pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=-1), mouse_pos=pos)
    assert sc.area.scroll == config.SCROLL_ROWS_PER_NOTCH * sc.area.row_px
    key(sc, pygame.K_PAGEDOWN)
    assert sc.area.scroll > config.SCROLL_ROWS_PER_NOTCH * sc.area.row_px
    for _ in range(200):
        key(sc, pygame.K_PAGEDOWN)
    assert sc.area.scroll == sc.area.max_scroll > 0
    key(sc, pygame.K_UP)
    assert sc.area.scroll == sc.area.max_scroll - sc.area.row_px


def test_escape_and_back_button_return_via_callable():
    sentinel = object()
    sc = LibraryScene(lambda: sentinel)
    key(sc, pygame.K_ESCAPE)
    assert sc.next_scene is sentinel
    sc2 = LibraryScene(lambda: sentinel)
    click(sc2, sc2.back_btn.rect.center)
    assert sc2.next_scene is sentinel


def test_graphs_are_rendered_lazily_and_cached(_pg):
    sc = LibraryScene(lambda: None)
    assert sc._graphs == {}                                 # opening renders nothing
    sc.draw(_pg)
    assert 0 < len(sc._graphs) <= config.LIB_GRAPHS_PER_FRAME
    for _ in range(10):
        sc.draw(_pg)
    visible = [e for e in sc.entries if e.card is not None and sc.area.visible(e.rect.y, e.rect.h)]
    assert len(sc._graphs) == len(visible) < len(library_data.FUNCTIONS)
    first = sc._graphs[visible[0].card["example"]]
    sc.draw(_pg)
    assert sc._graphs[visible[0].card["example"]] is first
    sc.area.set_scroll(sc.area.max_scroll)                  # bottom cards render when scrolled into view
    for _ in range(10):
        sc.draw(_pg)
    assert library_data.FUNCTIONS[-1]["example"] in sc._graphs


def test_every_tab_draws_and_survives_resize():
    sc = LibraryScene(lambda: None)
    for w, h in ((1920, 1080), (900, 600), (1280, 720)):
        view.set_size(w, h)
        screen = pygame.display.set_mode((w, h))
        sc.on_resize()
        assert sc.area.rect.right <= w and sc.area.rect.bottom <= h
        for i in range(len(library_data.TABS)):
            sc.select(i)
            sc.area.set_scroll(sc.area.max_scroll / 2)
            sc.draw(screen)
            assert screen.get_clip() == screen.get_rect()
    sc.select(0)
    sc.area.set_scroll(300)
    view.set_size(1000, 700)
    sc.on_resize()
    assert 0 < sc.area.scroll <= sc.area.max_scroll
    assert line_height(24) > 0
