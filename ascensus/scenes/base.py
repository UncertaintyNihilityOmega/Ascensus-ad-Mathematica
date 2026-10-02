"""Scene base class, the page factory (open_page) and helpers shared by the menus."""
from __future__ import annotations

import pygame

from ascensus import config, view
from ascensus.ui.widgets import Button


QUIT = "quit"


def fmt_time(seconds: float) -> str:
    """mm:ss."""
    s = int(seconds)
    return f"{s // 60:02d}:{s % 60:02d}"


def centered_button(cx: int, cy: int, label: str) -> Button:
    w, h = config.BUTTON_SIZE
    return Button(pygame.Rect(cx - w // 2, cy - h // 2, w, h), label)


def button_stack(n: int, head: int, foot: int = 0) -> tuple[int, list[pygame.Rect]]:
    """Rects of `n` centred menu buttons under a `head` px title block, with `foot` px left below them.

    The whole block is centred vertically. In a short window the button height and gap shrink (down to
    24 px buttons) so everything still fits. Returns (top of the block, button rects).
    """
    m = 12
    full_w, full_h = config.BUTTON_SIZE
    pitch = min(full_h + 12, max((view.H - 2 * m - head - foot) // max(n, 1), 24))
    gap = 12 if pitch == full_h + 12 else max(int(pitch * 0.18), 4)
    bh = pitch - gap
    total = head + n * pitch - gap + foot
    top = max((view.H - total) // 2, m)
    w = min(full_w, view.W - 20)
    return top, [pygame.Rect(view.W // 2 - w // 2, top + head + i * pitch, w, bh) for i in range(n)]


class Scene:
    """Base scene. Set `next_scene` (a Scene or QUIT) to ask the main loop to switch."""

    def __init__(self) -> None:
        self.next_scene: Scene | str | None = None
        self.fps = 0.0

    def handle_event(self, e: pygame.event.Event) -> None:
        pass

    def on_resize(self) -> None:
        """The window size changed (view.W / view.H are already updated): re-lay-out."""

    def update(self, dt: float) -> None:
        pass

    def draw(self, screen: pygame.Surface) -> None:
        pass


def open_page(name: str, back, game=None) -> "Scene | None":
    """Build the Settings / Library / Achievements / Saves page (imported lazily); None if it does not exist.

    `back` is a zero-argument callable returning the Scene the page's Back button leads to. `game` is only
    used by the Saves page: the paused GameScene it can save (None from the main menu).
    """
    try:
        if name == "saves":
            from ascensus.scenes.saves_page import SavesScene
            return SavesScene(game, back)
        if name == "settings":
            from ascensus.scenes.settings_page import SettingsScene
            return SettingsScene(back)
        if name == "library":
            from ascensus.scenes.library_page import LibraryScene
            return LibraryScene(back)
        if name == "achievements":
            from ascensus.scenes.achievements_page import AchievementsScene
            return AchievementsScene(back)
    except ImportError:
        return None
    return None
