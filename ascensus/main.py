"""Window setup (full screen / square resizable window) and the main loop."""
from __future__ import annotations

import pygame

from . import config, display, settings, view
from .display import set_display          # noqa: F401  (kept importable from here)
from .profile import get_profile
from .scenes import QUIT, MenuScene, Scene


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
    running = True
    while running:
        real_dt = min(clock.tick(config.FPS) / 1000.0, config.MAX_DT)
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
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
        nxt = scene.next_scene
        if nxt == QUIT:
            running = False
        elif nxt is not None:
            scene = nxt
    settings.save()
    get_profile().save()
    pygame.quit()
