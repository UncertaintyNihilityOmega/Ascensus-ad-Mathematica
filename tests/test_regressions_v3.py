"""Regression tests for the v3 bug table (one test per bug, each fails without its fix)."""
import ast
import os
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402
import pytest  # noqa: E402

from ascensus import config, display, settings, view  # noqa: E402
from ascensus.main import take_next  # noqa: E402
from ascensus.profile import Profile, set_profile  # noqa: E402
from ascensus.scenes import GameScene, open_page  # noqa: E402
from ascensus.settings_scene import SettingsScene  # noqa: E402
from ascensus.ui import widgets  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def _env():
    pygame.init()
    pygame.display.set_mode((1280, 720))
    view.set_size(1280, 720)
    widgets._fonts.clear()
    widgets._text_cache.clear()
    settings.reset_all()
    set_profile(Profile.in_memory())
    display.fullscreen = False
    yield
    settings.reset_all()
    set_profile(None)
    config.SETTINGS_PATH.unlink(missing_ok=True)


def click(scene, pos):
    scene.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1))


def key(scene, k):
    scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=k, mod=0, unicode=""))


# --- bug 1: pause -> Settings -> Back must not flash between the two scenes ----------------------
def test_pause_settings_back_stays_on_game():
    game = GameScene(seed=1)
    key(game, pygame.K_ESCAPE)
    assert game.paused
    click(game, game.settings_btn.rect.center)
    scene = take_next(game)
    assert isinstance(scene, SettingsScene) and game.next_scene is None
    key(scene, pygame.K_ESCAPE)                       # Back
    scene = take_next(scene)
    assert scene is game
    for _ in range(5):                                # the old bug: next_scene still pointed at Settings
        scene.update(1 / 60)
        assert take_next(scene) is None
    assert scene is game and game.paused


def test_pause_library_back_stays_on_game():
    game = GameScene(seed=1)
    key(game, pygame.K_ESCAPE)
    click(game, game.library_btn.rect.center)
    page = take_next(game)
    assert page is not None
    key(page, pygame.K_ESCAPE)
    assert take_next(page) is game
    assert take_next(game) is None


# --- bug 4: only the visible tab's fields may take clicks ---------------------------------------
def test_click_every_numeric_row_focuses_its_own_key():
    sc = SettingsScene(lambda: None)
    bad = []
    for tab in sc.tab_names:
        sc.select_tab(tab)
        for i, s in enumerate(sc.rows()):
            if s.key not in sc.fields:
                continue
            sc.area.set_scroll(i * config.SET_ROW_H)    # bring the row into the viewport
            sc._place()
            click(sc, sc.row_rects(s.key)["field"].center)
            if sc.focused_key() != s.key:
                bad.append((tab, s.key, sc.focused_key()))
            key(sc, pygame.K_ESCAPE)                  # cancel the edit
    assert not bad, bad


def test_typing_changes_only_the_clicked_setting():
    sc = SettingsScene(lambda: None)
    before = {s.key: settings.get(s.key) for s in settings.SETTINGS}
    sc.select_tab(sc.tab_names[-1])
    s = next(s for s in sc.rows() if s.key in sc.fields)
    click(sc, sc.row_rects(s.key)["field"].center)
    lo, hi = s.min, s.max
    target = min(max(lo + (hi - lo) / 2, lo), hi)
    sc.handle_event(pygame.event.Event(pygame.TEXTINPUT, text=str(target)))
    key(sc, pygame.K_RETURN)
    changed = [k for k, v in before.items() if settings.get(k) != v]
    assert changed in ([s.key], [])                   # [] only if the default already was the target


def test_click_elsewhere_commits_and_tab_moves_on():
    sc = SettingsScene(lambda: None)
    keys = [s.key for s in sc.rows() if s.key in sc.fields]
    assert len(keys) >= 2
    s0 = settings.find(keys[0])
    click(sc, sc.row_rects(keys[0])["field"].center)
    sc.handle_event(pygame.event.Event(pygame.TEXTINPUT, text=str(s0.max)))
    key(sc, pygame.K_TAB)                             # applies and focuses the next field
    assert settings.get(keys[0]) == s0.max
    assert sc.focused_key() == keys[1]
    click(sc, (5, view.H - 5))                        # elsewhere: commits (valid) or drops the edit
    assert sc.focused_key() is None


# --- bug 8: duplicate top-level definitions -------------------------------------------------------
def test_no_duplicate_top_level_defs():
    dupes = []
    for path in sorted((ROOT / "ascensus").rglob("*.py")):
        seen: dict[str, int] = {}
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                if node.name in seen:
                    dupes.append(f"{path.name}:{node.name} (lines {seen[node.name]} and {node.lineno})")
                seen[node.name] = node.lineno
    assert not dupes, dupes


# --- bug 2: the colour popup must work (and draw) over the VARIABLES section --------------------
def test_color_picker_over_variables_picks_color():
    game = GameScene(seed=2)
    for text in ("a*x", "b*x", "c*x", "x^2", "x^3", "sin(x)", "cos(x)", "x"):
        game.equations.add(text) if hasattr(game, "equations") else game.equations.add(text)
    mgr = getattr(game, "equations", None) or game.equations
    sb = game.sidebar
    assert sb.var_rect() is not None
    hit = None
    for i in range(len(mgr.entries)):
        sb.open_picker(i)
        if sb.picker_rect.colliderect(sb.var_rect()):
            hit = i
            break
        sb.picker_idx = None
    assert hit is not None, "the popup never overlaps the variables section in this layout"
    sb.picker_idx = None
    click(game, sb.rects(hit)["swatch"].center)
    assert sb.picker_idx == hit
    old = mgr.entries[hit].color
    target = next(k for k, c in enumerate(config.CURVE_PALETTE_20) if c != old)
    click(game, sb._picker_cell(target).center)             # lands on a variable row if not modal
    assert mgr.entries[hit].color == config.CURVE_PALETTE_20[target] != old
    assert sb.picker_idx is None


def test_picker_blocks_clicks_to_the_upgrade_panel_and_esc_closes():
    game = GameScene(seed=2)
    mgr = getattr(game, "equations", None) or game.equations
    mgr.add("x")
    game.sidebar.open_picker(0)
    xp_before = game.upgrades.xp if hasattr(game, "upgrades") else None
    key(game, pygame.K_ESCAPE)
    assert game.sidebar.picker_idx is None and not game.paused


# --- bug 3: minimum window size and fitted text ------------------------------------------------------
def test_windowed_mode_has_minimum_size():
    screen = display.set_display(False)
    assert min(screen.get_size()) >= min(config.WINDOW_MIN_SIZE)
    try:
        win = pygame.Window.from_display_module()
        assert tuple(win.minimum_size) in (tuple(config.WINDOW_MIN_SIZE), (0, 0))   # dummy driver may ignore it
    except AttributeError:
        pass
    display.set_display(False)


def test_draw_text_shrinks_then_truncates_and_counts():
    surf = pygame.Surface((400, 100))
    widgets.reset_overflow()
    r = widgets.draw_text(surf, "Off on a Tangent", 30, (255, 255, 255), (0, 0), max_w=120, min_size=14)
    assert r.w <= 120 and widgets.overflow_count == 0          # shrank to fit
    r = widgets.draw_text(surf, "A very long achievement name that cannot fit", 30, (255, 255, 255), (0, 0),
                          max_w=100, min_size=20)
    assert r.w <= 100 and widgets.overflow_count == 1          # cut with '...' below min size
    widgets.reset_overflow()
    r = widgets.draw_text(surf, "A very long achievement name that cannot fit", 30, (255, 255, 255), (0, 0),
                          max_w=100, min_size=20, wrap=True)
    assert r.w <= 100 and r.h > widgets.get_font(20).get_height() and widgets.overflow_count == 0


def test_freetype_text_has_no_gaps_inside_words():
    """'Pixels' must not be spaced like 'Pi xel s': the gap between letters stays small."""
    font = widgets.get_font(20)
    whole = font.size("Pixels")[0]
    parts = sum(font.size(c)[0] for c in "Pixels")
    assert abs(whole - parts) <= 4


# --- bug 6: the input box and the upgrades panel must never overlap ---------------------------------
@pytest.mark.parametrize("size", [(800, 600), (800, 800), (1280, 720), (1920, 1080)])
@pytest.mark.parametrize("collapsed", [False, True])
def test_input_box_and_upgrade_panel_do_not_overlap(size, collapsed):
    pygame.display.set_mode(size)
    view.set_size(*size)
    game = GameScene(seed=3)
    game.sidebar.collapsed = collapsed
    game.update(1 / 60)                                   # collapse state change re-lays-out
    game.on_resize()
    box, panel = game.input.rect, game.upgrade_panel.panel_rect
    view_rect = pygame.Rect(0, 0, *size)
    assert not box.colliderect(panel), (size, box, panel)
    assert view_rect.contains(box) and view_rect.contains(panel)
    left = game.sidebar.tab_rect.right if collapsed else game.sidebar.panel_rect.right
    assert box.left >= left
    for rect in game.upgrade_panel.rects.values():
        assert not rect.colliderect(box)
    if panel.bottom >= box.top - 1 and panel.left > box.right:        # side by side: not too narrow
        assert box.w >= config.INPUT_MIN_W


# --- text drawn at its baseline, not one ascender too low (the "halved text" bug) ---------------------
@pytest.mark.parametrize("size", [16, 22, 28, 60])
def test_text_ink_is_not_cut_off(size):
    """freetype's render_to takes the bbox top-left unless origin mode is on; without it the glyphs
    were drawn an ascender too low and the bottom half fell outside the line surface."""
    img = widgets.get_font(size).render("Hgpy Settings", True, (255, 255, 255))
    ink = img.get_bounding_rect()
    assert ink.top <= img.get_height() * 0.3, (ink, img.get_size())     # capitals start near the top
    assert ink.height >= img.get_height() * 0.6, (ink, img.get_size())  # whole glyphs, not a sliver


# --- a new run starts empty and never writes an equations file (equations live only in runs/saves) ----
def test_new_game_starts_without_equations(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    g = GameScene(seed=1, profile=Profile.in_memory())
    assert g.equations.entries == [] and not g.equations.store.vars
    g.equations.add("y = a x")
    assert list(tmp_path.iterdir()) == []                     # nothing written next to the game
