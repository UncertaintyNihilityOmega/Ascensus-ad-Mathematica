"""P19 smoke phase: mouse mode, dashes, speed button, Controls tab, smooth curves. `python tools/smoke_p19.py` runs alone."""
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
_tmp = Path(tempfile.gettempdir())
os.environ.setdefault("ASCENSUS_PROFILE", str(_tmp / f"ascensus_smoke_p19_profile_{os.getpid()}.json"))
os.environ.setdefault("ASCENSUS_SETTINGS", str(_tmp / f"ascensus_smoke_p19_settings_{os.getpid()}.json"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402
import pygame  # noqa: E402

from ascensus import config, controls, settings, view  # noqa: E402
from ascensus.curvefield import build_curve, render_curve  # noqa: E402
from ascensus.mathparse import parse_equation  # noqa: E402
from ascensus.profile import Profile  # noqa: E402
from ascensus.scenes import GameScene  # noqa: E402
from ascensus.settings_scene import SettingsScene  # noqa: E402

DT = 1 / 60


def _ev(kind, **kw):
    return pygame.event.Event(kind, **kw)


def _click(scene, pos, button=1):
    scene.handle_event(_ev(pygame.MOUSEBUTTONDOWN, pos=pos, button=button))


def _key(scene, k):
    scene.handle_event(_ev(pygame.KEYDOWN, key=k, mod=0, unicode=""))


def _run(game, screen, frames):
    for _ in range(frames):
        game.update(DT)
        game.draw(screen)


def mouse_phase(screen) -> None:
    """Mouse mode: walk toward the cursor, dead zone, over-UI and unfocused stops, right-click and J dashes."""
    cx, cy = view.center()
    cursor = [cx, cy]
    saved = controls.mouse_pos, controls.window_active
    controls.mouse_pos = lambda: tuple(cursor)
    controls.window_active = lambda: True
    try:
        settings.set_value("MOVE_MODE", "Mouse")
        game = GameScene(seed=21, profile=Profile.in_memory())
        game.player.hp = 1e9
        cursor[:] = [cx + 300, cy]
        p0 = game.player.pos.copy()
        _run(game, screen, 30)
        moved = game.player.pos[0] - p0[0]
        assert abs(moved - config.PLAYER_SPEED * 0.5) < 3 and abs(game.player.pos[1] - p0[1]) < 1e-6
        assert game.player.facing[0] > 0.99
        cursor[:] = [cx - 5, cy]                                         # inside the dead zone: stand, but face it
        p1 = game.player.pos.copy()
        _run(game, screen, 10)
        assert np.allclose(game.player.pos, p1) and game.player.facing[0] < -0.99
        for name, pos in (("sidebar", game.sidebar.panel_rect.center), ("speed", game.speed_button.rect.center),
                          ("upgrades", game.upgrade_panel.panel_rect.center), ("input", game.input.rect.center)):
            cursor[:] = pos
            _run(game, screen, 5)
            assert np.allclose(game.player.pos, p1), f"moved over the {name}"
        cursor[:] = [cx, cy + 200]
        controls.window_active = lambda: False
        _run(game, screen, 5)
        assert np.allclose(game.player.pos, p1), "moved while unfocused"
        controls.window_active = lambda: True
        # right-click dash toward the cursor, then the J dash
        game.handle_event(_ev(pygame.MOUSEBUTTONDOWN, pos=(cx, cy + 200), button=3))
        assert game.player.dashing and game.player.dash_count == 1
        p2 = game.player.pos.copy()
        while game.player.dashing:
            game.update(DT)
        assert game.player.pos[1] - p2[1] > config.DASH_DIST * 0.9 and abs(game.player.pos[0] - p2[0]) < 1.0
        _key(game, pygame.K_j)
        assert game.player.dash_count == 2
        game.handle_event(_ev(pygame.MOUSEBUTTONDOWN, pos=game.speed_button.rect.center, button=3))
        assert game.player.dash_count == 2                               # right-click over the UI is ignored
    finally:
        controls.mouse_pos, controls.window_active = saved
        settings.reset_all()
    print("p19  : mouse mode (walk, dead zone, UI/unfocus stop, right-click + J dash) OK")


def speed_phase(screen) -> None:
    """The speed button cycles 1 -> 2 -> 3 -> 1; fast play is split into substeps of at most 1/30 s."""
    game = GameScene(seed=22, profile=Profile.in_memory())
    game.player.hp = 1e9
    game.equations.add("y = x")
    assert game.speed == 1
    for want in (2, 3, 1, 2, 3):
        _click(game, game.speed_button.rect.center)
        assert game.speed == want
    dts = []
    orig = game.swarm.update
    game.swarm.update = lambda dt, pos: (dts.append(dt), orig(dt, pos))[1]
    game.update(0.1)
    assert len(dts) == 9 and max(dts) <= config.SIM_MAX_SUBSTEP + 1e-12 and abs(game.game_t - 0.3) < 1e-9
    game.swarm.update = orig
    game.draw(screen)
    r = game.speed_button.rect
    assert r.left > view.W // 2 and screen.get_rect().contains(r)
    print("p19  : speed button + substeps OK")


def controls_tab_phase(screen) -> None:
    """Settings > Controls: click the key row, press a key (binds), Esc cancels, the choice row cycles."""
    settings.reset_all()
    page = SettingsScene(lambda: None)
    page.select_tab("Controls")
    page.draw(screen)
    row = page.row_rects("DASH_KEY")["cycle"]
    _click(page, row.center)
    assert page.listening_key() == "DASH_KEY"
    page.draw(screen)
    _key(page, pygame.K_ESCAPE)
    assert page.listening_key() is None and page.next_scene is None and config.DASH_KEY == "j"
    _click(page, row.center)
    _key(page, pygame.K_k)
    assert config.DASH_KEY == "k" and controls.dash_key_code() == pygame.K_k
    game = GameScene(seed=23, profile=Profile.in_memory())
    _key(game, pygame.K_j)
    assert game.player.dash_count == 0
    _key(game, pygame.K_k)
    assert game.player.dash_count == 1
    _click(page, page.row_rects("MOVE_MODE")["cycle"].center)
    assert config.MOVE_MODE == "Mouse"
    page.draw(screen)
    settings.reset_all()
    config.SETTINGS_PATH.unlink(missing_ok=True)
    print("p19  : Controls tab key binding OK")


def render_phase(w: int, h: int) -> None:
    """Smooth render at w x h: no beading on a diagonal, halo for black, timing of a full-window render."""
    old = view.W, view.H
    view.set_size(w, h)
    try:
        c = build_curve(parse_equation("y = x").func, 0.0, size=(w, h))
        surf = render_curve(c.points, (0, 255, 255), (w, h))
        alpha = pygame.surfarray.array_alpha(surf)
        off = (w + h) / 2 - 1
        xs = np.arange(w // 2 - 200, w // 2 + 200)
        vals = np.array([alpha[x, int(round(off - x))] for x in xs], dtype=float)
        assert vals.min() >= 230 and vals.std() < 8, (vals.min(), vals.std())
        black = render_curve(c.points, (0, 0, 0), (w, h))
        x0 = w // 2
        y0 = int(round(off - x0))
        halo_seen = any(black.get_at((x0 + d, y0)).a > 0 and min(black.get_at((x0 + d, y0))[:3]) > 120
                        for d in range(2, 6))
        assert halo_seen, "black curve has no light halo"
        mono = build_curve(parse_equation("tan(sqrt(x^2 + y^2)) = y / x").func, 0.0, size=(w, h))
        render_curve(mono.points, (0, 255, 255), (w, h))
        t0 = time.perf_counter()
        for _ in range(10):
            render_curve(mono.points, (0, 255, 255), (w, h))
        ms = (time.perf_counter() - t0) * 100
        print(f"p19  : smooth render {w}x{h}: {len(mono.points)} pts, {ms:.2f} ms per full-window render, "
              f"diagonal alpha min {vals.min():.0f} std {vals.std():.1f}")
    finally:
        view.set_size(*old)


def phase(screen) -> None:
    """Run every P19 check at the current window size (screen = the display surface)."""
    mouse_phase(screen)
    speed_phase(screen)
    controls_tab_phase(screen)
    render_phase(1280, 720)
    render_phase(1920, 1080)


def main() -> None:
    pygame.init()
    for w, h in ((1280, 720), (1920, 1080)):
        screen = pygame.display.set_mode((w, h))
        view.set_size(w, h)
        print(f"--- {w}x{h}")
        phase(screen)
    print("smoke_p19 OK")


if __name__ == "__main__":
    main()
