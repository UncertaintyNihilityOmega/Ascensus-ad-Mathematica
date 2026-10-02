"""Download Kenney's CC0 icon packs and copy the few white PNGs the game uses into ascensus/assets/icons/.

Packs (both CC0 / public domain, https://kenney.nl):
  Game Icons        https://kenney.nl/assets/game-icons
  Board Game Icons  https://kenney.nl/assets/board-game-icons

The zips go to a temporary directory that is deleted afterwards; only the chosen PNGs and a
License.txt land in ascensus/assets/icons/. Icons the packs lack (play) are drawn in code by ui/icons.py.
Run from the project root:  .venv\\Scripts\\python tools\\fetch_icons.py
"""
from __future__ import annotations

import re
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "ascensus" / "assets" / "icons"

PACKS = {
    "game": ("https://kenney.nl/assets/game-icons",
             "https://kenney.nl/media/pages/assets/game-icons/1ebf9c14af-1677661579/kenney_game-icons.zip"),
    "board": ("https://kenney.nl/assets/board-game-icons",
              "https://kenney.nl/media/pages/assets/board-game-icons/19cae04050-1721645690/"
              "kenney_board-game-icons.zip"),
}
GAME_2X = "PNG/White/2x/{}.png"          # Game Icons: white, 100 px (a few only exist at 1x, 50 px)
GAME_1X = "PNG/White/1x/{}.png"
BOARD = "PNG/Double (128px)/{}.png"      # Board Game Icons: white, 128 px

# canonical icon name -> (pack, source file stem)
ICONS: dict[str, tuple[str, str]] = {
    "skull": ("board", "skull"),
    "reset": ("board", "arrow_counterclockwise"),
    "undo": ("game", "return"),
    "pause": ("game", "pause"),
    "fast_forward": ("game", "fastForward"),
    "trash": ("game", "trashcan"),
    "pencil": ("board", "notepad"),
    "plus": ("game", "plus"),
    "minus": ("game", "minus"),
    "cross": ("game", "cross"),
    "save": ("game", "save"),
    "gear": ("game", "gear"),
    "book": ("board", "book_open"),
    "trophy": ("game", "trophy"),
    "medal": ("game", "medal2"),
    "padlock": ("game", "locked"),
    "arrow_left": ("game", "arrowLeft"),
    "arrow_right": ("game", "arrowRight"),
    "home": ("game", "home"),
}
# "play" is not in the packs (Game Icons' triangle is tiny): ui/icons.py draws it in code.


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (ascensus fetch_icons)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def _zip_url(page: str, fallback: str) -> str:
    """The pack's zip link as currently published on its asset page (falls back to the known URL)."""
    try:
        html = _get(page).decode("utf-8", "replace")
        m = re.search(r"https://kenney\.nl/media/[^'\"\s]+\.zip", html)
        if m:
            return m.group(0)
    except OSError:
        pass
    return fallback


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    licenses: list[str] = []
    missing: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        zips: dict[str, zipfile.ZipFile] = {}
        for key, (page, fallback) in PACKS.items():
            url = _zip_url(page, fallback)
            print(f"downloading {url}")
            path = Path(tmp) / f"{key}.zip"
            path.write_bytes(_get(url))
            zips[key] = zipfile.ZipFile(path)
            lic = next(n for n in zips[key].namelist() if n.lower().endswith("license.txt"))
            licenses.append(f"==== Kenney {key.capitalize()} Icons ({page}) ====\n"
                            + zips[key].read(lic).decode("utf-8", "replace").strip() + "\n")
        for name, (pack, stem) in ICONS.items():
            z = zips[pack]
            names = set(z.namelist())
            candidates = [BOARD.format(stem)] if pack == "board" else [GAME_2X.format(stem), GAME_1X.format(stem)]
            src = next((c for c in candidates if c in names), None)
            if src is None:
                missing.append(name)
                continue
            (OUT / f"{name}.png").write_bytes(z.read(src))
            print(f"  {name}.png <- {pack}: {src}")
        for z in zips.values():
            z.close()
    (OUT / "License.txt").write_text(
        "Icons in this folder are from Kenney (https://kenney.nl), released under CC0 1.0 (public domain):\n"
        "http://creativecommons.org/publicdomain/zero/1.0/\n\n" + "\n".join(licenses), encoding="utf-8")
    if missing:
        print("missing (drawn in code instead):", ", ".join(missing))
        return 1
    print(f"done: {len(ICONS)} icons in {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
