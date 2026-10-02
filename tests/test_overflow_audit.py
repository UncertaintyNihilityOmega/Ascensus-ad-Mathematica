"""QA audit: render every page at 800x600, 800x800 and 1920x1080; no text may be cut below its minimum size.

`draw_text(max_w=...)` counts every time it had to truncate text with '...' even at its smallest size;
this test asserts that count stays 0 (and that nothing crashes on the way).
"""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402
import pytest  # noqa: E402

from ascensus import config, display, settings, view  # noqa: E402
from ascensus.game.profile import Profile, set_profile  # noqa: E402
from ascensus.scenes.achievements_page import AchievementsScene  # noqa: E402
from ascensus.scenes.game import GameScene  # noqa: E402
from ascensus.scenes.game_over import GameOverScene  # noqa: E402
from ascensus.scenes.library_page import LibraryScene  # noqa: E402
from ascensus.scenes.menu import MenuScene  # noqa: E402
from ascensus.scenes.saves_page import SavesScene  # noqa: E402
from ascensus.scenes.settings_page import SettingsScene  # noqa: E402
from ascensus.scenes.stats_page import StatsScene  # noqa: E402
from ascensus.ui import widgets  # noqa: E402

SIZES = [(800, 600), (800, 800), (1920, 1080)]
EQUATIONS = ["x^2", "sin(x)", "cos(x)", "tan(x)", "eq4: (x^(2)+y^(2))^(3)=4 x^(2) y^(2)",
             "a*sin(b*x + c)", "d*x", "sqrt(abs(x))", "x = 2", "y = -x",
             "longest_name_16c: y = 3*sin(x/2) + 2*cos(x) - x/4", "1 = x^2 + y^2"]


@pytest.fixture(autouse=True)
def _env():
    pygame.init()
    widgets._fonts.clear()
    widgets._text_cache.clear()
    settings.reset_all()
    set_profile(Profile.in_memory())
    display.fullscreen = False
    yield
    settings.reset_all()
    set_profile(None)
    config.SETTINGS_PATH.unlink(missing_ok=True)


def _screen(size):
    screen = pygame.display.set_mode(size)
    view.set_size(*size)
    return screen


def _render(scene, screen, frames=2):
    for _ in range(frames):
        scene.update(1 / 60)
        scene.draw(screen)


def _busy_game():
    game = GameScene(seed=5)
    for text in EQUATIONS:
        game.equations.add(text)
    assert len(game.equations.entries) == 12 and len(game.sidebar.variable_names()) >= 4
    for _ in range(80):
        game.swarm.spawn(game.player.pos, 60.0)
    return game


def _audit(label, scene, screen):
    """No text cut below its minimum size, and no unclipped text drawn partly outside the window."""
    widgets.reset_overflow()
    widgets.audit_rects = []
    try:
        _render(scene, screen)
        rects = widgets.audit_rects
    finally:
        widgets.audit_rects = None
    assert widgets.overflow_count == 0, (label, widgets.overflow_log[:5])
    w, h = screen.get_size()
    full = pygame.Rect(0, 0, w, h)
    outside = [(text, tuple(r)) for text, r, clip, _ in rects
               if clip == full and r.w > 0 and not full.inflate(2, 2).contains(r)
               and not (text.isdigit() and r.h <= 14)]      # enemy HP numbers straddle the edge by design
    assert not outside, (label, outside[:5])


@pytest.mark.parametrize("size", SIZES)
def test_no_text_is_cut_on_any_page(size):
    screen = _screen(size)
    _audit("menu", MenuScene(), screen)
    _audit("game over", GameOverScene(754.0, 1234), screen)

    game = _busy_game()
    _audit("game", game, screen)
    game.show_fps = True
    game.upgrades.xp = 5000.0
    game.upgrades.auto = True
    _audit("game with auto + xp", game, screen)

    game.paused = True
    _audit("pause", game, screen)
    game.paused = False

    back = lambda: game  # noqa: E731
    _audit("stats", StatsScene(game, back), screen)
    _audit("saves (from pause)", SavesScene(game, back), screen)
    _audit("saves (from menu)", SavesScene(None, back), screen)
    _audit("achievements", AchievementsScene(back, Profile.in_memory()), screen)

    sc = SettingsScene(back)
    for name in sc.tab_names:
        sc.select_tab(name)
        sc.area.set_scroll(0)
        _audit(f"settings/{name}", sc, screen)
        for i in range(0, len(sc.rows()), 4):               # a few scroll positions per tab
            sc.area.set_scroll(i * config.SET_ROW_H)
            _audit(f"settings/{name}@{i}", sc, screen)

    lib = LibraryScene(back)
    for i in range(len(lib.tabs.labels) if hasattr(lib.tabs, "labels") else 7):
        lib.select(i)
        _audit(f"library/{lib.tab_name}", lib, screen)


@pytest.mark.parametrize("size", SIZES)
def test_pages_survive_resizing_between_sizes(size):
    """Open at one size, resize to another and render again: layouts follow and nothing is cut."""
    screen = _screen((1280, 720))
    game = _busy_game()
    scenes = [MenuScene(), game, StatsScene(game, lambda: game), SettingsScene(lambda: game),
              LibraryScene(lambda: game), AchievementsScene(lambda: game, Profile.in_memory()),
              SavesScene(game, lambda: game)]
    for sc in scenes:
        sc.draw(screen)
    screen = _screen(size)
    for sc in scenes:
        sc.on_resize()
        _audit(type(sc).__name__, sc, screen)
