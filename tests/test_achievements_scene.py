"""Achievements page: card model, grid layout (fits or scrolls), input, drawing."""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402
import pytest  # noqa: E402

from ascensus import config, view  # noqa: E402
from ascensus.achievements import ACHIEVEMENTS, TOTAL  # noqa: E402
from ascensus.achievements_scene import AchievementsScene, card_model, counter_text, grid_layout  # noqa: E402
from ascensus.profile import Profile  # noqa: E402
from ascensus.ui import widgets  # noqa: E402


@pytest.fixture(autouse=True)
def _pg():
    pygame.init()
    pygame.display.set_mode((1280, 720))
    widgets._fonts.clear()
    widgets._text_cache.clear()
    view.set_size(1280, 720)
    yield
    view.set_size(1280, 720)
    widgets._fonts.clear()
    widgets._text_cache.clear()
    pygame.quit()


def test_card_model_and_counter():
    p = Profile.in_memory()
    assert counter_text(p) == f"0/{TOTAL}"
    assert len(card_model(p)) == TOTAL and not any(m["unlocked"] for m in card_model(p))
    p.unlock("hello_sine")
    p.unlock("investor")
    model = {m["id"]: m for m in card_model(p)}
    assert counter_text(p) == f"2/{TOTAL}"
    assert model["hello_sine"]["unlocked"] and model["hello_sine"]["date"] == p.achievements["hello_sine"]
    assert not model["co_star"]["unlocked"] and model["co_star"]["date"] == ""
    assert [m["name"] for m in card_model(p)] == [a.name for a in ACHIEVEMENTS]


def test_grid_is_4_wide_and_fits_when_tall_enough():
    rects, h = grid_layout(1200, 1400)
    assert len(rects) == TOTAL and h <= 1400
    assert len({r.x for r in rects}) == 4 and len({r.y for r in rects}) == TOTAL // 4
    for a in rects:
        assert sum(a.colliderect(b) for b in rects) == 1            # overlaps only itself
    assert max(r.right for r in rects) <= 1200


def test_grid_scrolls_when_too_short():
    rects, h = grid_layout(1200, 300)
    assert rects[0].h == config.ACH_CARD_MIN_H and h > 300
    assert h == rects[-1].bottom


def test_scene_scrolls_on_small_window_and_fits_on_large():
    sc = AchievementsScene(lambda: None, Profile.in_memory())
    view.set_size(1920, 1080)
    sc.on_resize()
    assert len({r.x for r in sc.rects}) == config.ACH_COLS             # 4 across; 40 cards scroll
    view.set_size(900, 420)
    sc.on_resize()
    assert sc.area.max_scroll > 0 and max(r.right for r in sc.rects) <= sc.area.rect.w


def test_escape_and_back_return_via_callable():
    sentinel = object()
    sc = AchievementsScene(lambda: sentinel, Profile.in_memory())
    sc.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0, unicode=""))
    assert sc.next_scene is sentinel
    sc2 = AchievementsScene(lambda: sentinel, Profile.in_memory())
    sc2.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=sc2.back_btn.rect.center, button=1))
    assert sc2.next_scene is sentinel


def test_draw_locked_and_unlocked_at_several_sizes():
    p = Profile.in_memory()
    for a in ACHIEVEMENTS[:7]:
        p.unlock(a.id)
    sc = AchievementsScene(lambda: None, p)
    for w, h in ((1280, 720), (1920, 1080), (800, 500)):
        view.set_size(w, h)
        screen = pygame.display.set_mode((w, h))
        sc.on_resize()
        sc.draw(screen)
        assert screen.get_clip() == screen.get_rect()
