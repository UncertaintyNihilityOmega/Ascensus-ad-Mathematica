"""Render the README screenshots headlessly (no window opens, the real save/ folder is never touched).

    python tools/screenshots.py                     # docs/images/*.png at 1280x720
    python tools/screenshots.py --size 1366x768 --out some/folder
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="ascensus_shots_"))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["ASCENSUS_PROFILE"] = str(_TMP / "profile.json")
os.environ["ASCENSUS_SETTINGS"] = str(_TMP / "settings.json")
os.environ["ASCENSUS_SLOTS"] = str(_TMP / "slots")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pygame  # noqa: E402

from ascensus import view  # noqa: E402
from ascensus.game.achievements import ACHIEVEMENTS  # noqa: E402
from ascensus.game.profile import get_profile  # noqa: E402
from ascensus.game.savegame import SlotStore  # noqa: E402
from ascensus.scenes.achievements_page import AchievementsScene  # noqa: E402
from ascensus.scenes.game import GameScene  # noqa: E402
from ascensus.scenes.library_page import LibraryScene  # noqa: E402
from ascensus.scenes.menu import MenuScene  # noqa: E402
from ascensus.scenes.saves_page import SavesScene  # noqa: E402
from ascensus.scenes.settings_page import SettingsScene  # noqa: E402

SHOWCASE = [
    "Sakuna: 0 = sin(x*a)*sin(y*a)",
    "Ocean: y/x = tan(sqrt(x^2+y^2)*a)",
    "Love: 1 = x^2+(y-sqrt(abs(x)))^2",
    "eq4: (x^2+y^2)^3 = 4x^2 y^2",
    "y = 2sin(x + t)",
    "x^2 + y^2 = 9",
]


def showcase_game(seconds: float = 40.0) -> GameScene:
    """A run with the showcase equations, a slider variable and some enemies on screen."""
    g = GameScene(seed=7)
    for text in SHOWCASE:
        g.equations.add(text)
    g.equations.store.set_value("a", 0.8)
    g.player.hp = 1e9                                   # survive the staged run
    g.direction_override = (0.4, 0.2)
    for _ in range(int(seconds * 60)):
        g.update(1 / 60)
    g.direction_override = None
    g.player.hp = g.player.max_hp * 0.8
    return g


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--size", default="1280x720")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "docs" / "images"))
    args = ap.parse_args()
    w, h = (int(v) for v in args.size.lower().split("x"))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    pygame.init()
    screen = pygame.display.set_mode((w, h))
    view.set_size(w, h)

    def shot(scene, name: str, frames: int = 3) -> None:
        for _ in range(frames):
            scene.update(1 / 60)
            scene.draw(screen)
        pygame.image.save(screen, str(out / f"{name}.png"))
        print("wrote", out / f"{name}.png")

    profile = get_profile()
    for a in ACHIEVEMENTS[::3]:
        profile.unlock(a.id)
    profile.record_run(1925.0, 2246)

    game = showcase_game()
    game.show_fps = False                                 # no real frame clock when rendering headless
    game.input.set_text("Cosmic: 200 = (x^5+y^5)^2")
    game.input.anchor, game.input.cursor = 8, 13            # show a selection in the equation box
    shot(game, "game", frames=1)

    slots = SlotStore()
    slots.save_game(1, game)
    second = showcase_game(12.0)
    slots.save_game(4, second)
    shot(SavesScene(game, lambda: None, slots), "saves")
    shot(MenuScene(), "menu", frames=12)
    shot(AchievementsScene(lambda: None), "achievements")
    shot(LibraryScene(lambda: None), "library", frames=40)
    shot(SettingsScene(lambda: None), "settings")
    pygame.quit()


if __name__ == "__main__":
    main()
