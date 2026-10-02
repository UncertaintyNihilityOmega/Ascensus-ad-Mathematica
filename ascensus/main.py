"""Window setup (full screen / square resizable window) and the main loop."""
from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEO_MINIMIZE_ON_FOCUS_LOSS", "0")   # stay visible behind export/import dialogs

import pygame  # noqa: E402

from . import config, display, settings, view
from .display import set_display          # noqa: F401  (kept importable from here)
from .profile import get_profile
from .scenes import QUIT, GameOverScene, GameScene, MenuScene, Scene


def sync_view(scene: Scene) -> pygame.Surface:
    """Adopt the real display size (after a resize event) and tell the scene."""
    screen = pygame.display.get_surface()
    if screen.get_size() != (view.W, view.H):
        view.set_size(*screen.get_size())
        scene.on_resize()
    return screen


def set_app_identity() -> None:
    """Taskbar identity (Windows) and window icon; every failure is ignored."""
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(config.APP_USER_MODEL_ID)
    except Exception:
        pass
    try:
        pygame.display.set_icon(pygame.transform.smoothscale(pygame.image.load(str(config.ICON_PATH)), (64, 64)))
    except Exception:
        pass


def take_next(scene: Scene) -> "Scene | str | None":
    """Pop the scene's switch request. It must be cleared: a scene that is returned to later
    (pause -> Settings -> Back gives the same GameScene) would otherwise switch away again at once."""
    nxt, scene.next_scene = scene.next_scene, None
    return nxt


def track_game(live: "GameScene | None", scene: Scene) -> "GameScene | None":
    """The run that is still alive behind the current scene: a GameScene is itself, the menu and the game-over
    screen mean no run, and a page opened from pause (Settings, Saves, ...) keeps the paused game."""
    if isinstance(scene, GameScene):
        return scene
    if isinstance(scene, (MenuScene, GameOverScene)):
        return None
    return live


def autosave_live(live: "GameScene | None") -> bool:
    """Closing the window mid-run: write the autosave of the run that is still going."""
    return live is not None and live.autosave()


def main() -> None:
    pygame.init()
    pygame.display.set_caption(config.TITLE)
    set_app_identity()
    settings.apply_saved()                      # saved overrides, incl. the last display mode
    get_profile()                               # load the profile (best run, achievements)
    screen = display.set_display(config.FULLSCREEN_START)
    pygame.key.set_repeat(config.KEY_REPEAT_DELAY, config.KEY_REPEAT_INTERVAL)
    clock = pygame.time.Clock()
    scene: Scene = MenuScene()
    live: GameScene | None = None               # the unfinished run, for the autosave on window close
    running = True
    while running:
        real_dt = min(clock.tick(config.FPS) / 1000.0, config.MAX_DT)
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                autosave_live(live)                 # window closed mid-run: Continue picks it up
                running = False
            elif e.type == pygame.KEYDOWN and e.key == pygame.K_F11:
                screen = display.toggle()
                settings.save()                 # remembers the last display mode
                scene.on_resize()
            elif e.type in (pygame.VIDEORESIZE, pygame.WINDOWSIZECHANGED):
                screen = sync_view(scene)
            else:
                scene.handle_event(e)
        scene.fps = clock.get_fps()
        scene.update(real_dt)
        screen = pygame.display.get_surface()   # a page may have switched the display mode
        scene.draw(screen)
        pygame.display.flip()
        nxt = take_next(scene)
        if nxt == QUIT:
            running = False
        elif nxt is not None:
            scene = nxt
            live = track_game(live, scene)
    settings.save()
    get_profile().save()
    pygame.quit()
