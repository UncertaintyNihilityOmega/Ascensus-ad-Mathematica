"""P18 smoke phase: every icon, sidebar pencil/trash rows, the colour popup with its Custom row.

`phase(screen)` runs at the screen's size (tools/smoke.py can call it at 1280x720 and 1920x1080);
`python tools/smoke_p18.py` runs it standalone at both sizes.
"""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
_tmp = Path(tempfile.gettempdir())
os.environ.setdefault("ASCENSUS_PROFILE", str(_tmp / f"ascensus_smoke_p18_profile_{os.getpid()}.json"))
os.environ.setdefault("ASCENSUS_SETTINGS", str(_tmp / f"ascensus_smoke_p18_settings_{os.getpid()}.json"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pygame  # noqa: E402

from ascensus import config, view  # noqa: E402
from ascensus.scenes import GameScene  # noqa: E402
from ascensus.ui import icons  # noqa: E402
from ascensus.ui.colorpicker import parse_hex  # noqa: E402

DT = 1 / 60


def _ev(kind, **kw):
    return pygame.event.Event(kind, **kw)


def _step(game, screen) -> None:
    game.update(DT)
    game.draw(screen)


def _draw_all_icons(screen: pygame.Surface) -> None:
    """A contact sheet of every icon at 16/32/64 px in a few colours; each must put pixels on the screen."""
    screen.fill(config.BG_COLOR)
    x = 10
    for name in icons.ICON_NAMES:
        for size, color in ((16, (255, 255, 255)), (32, (255, 90, 90)), (64, (120, 200, 255))):
            img = icons.icon(name, size, color)
            assert img.get_size() == (size, size) and pygame.mask.from_surface(img, 10).count() > size
            screen.blit(img, (x, 10 + {16: 0, 32: 30, 64: 70}[size]))
        x += 70
    for fn in (icons.skull, icons.medal, icons.padlock):
        assert fn(24).get_size() == (24, 24)


def phase(screen: pygame.Surface) -> None:
    """Icons, sidebar icon buttons and the colour popup (grid, tooltip, hue strip, hex box) at screen size."""
    w, h = screen.get_size()
    view.set_size(w, h)
    pygame.mouse.set_pos((w - 5, h - 5))
    _draw_all_icons(screen)

    game = GameScene(seed=3)
    if hasattr(game, "on_resize"):
        game.on_resize()
    for text in ("x^2", "sin(x)", "a*x", "cos(x)"):
        game.equations.add(text)
    sb, fm = game.sidebar, game.equations
    _step(game, screen)
    row = sb.row_rect(1)
    pygame.mouse.set_pos(row.center)                          # hover a row: pencil / trash buttons light up
    _step(game, screen)
    parts = sb.rects(1)
    assert parts["edit"].w > 0 and parts["delete"].w > 0

    # the popup: modal, inside the window, 5 x 4 grid with hover names and a Custom row
    sb.handle_event(_ev(pygame.MOUSEBUTTONDOWN, pos=sb.rects(1)["swatch"].center, button=1))
    assert sb.picker_idx == 1 and pygame.Rect(0, 0, w, h).contains(sb.picker_rect)
    cell = sb._picker_cell(11)
    pygame.mouse.set_pos(cell.center)
    _step(game, screen)
    assert sb.picker_tooltip(cell.center) == config.CURVE_PALETTE_NAMES[11] == "Cyan"

    hs = sb.custom.hue_strip.rect
    game.handle_event(_ev(pygame.MOUSEBUTTONDOWN, pos=(hs.left + hs.w // 2, hs.centery), button=1))
    game.handle_event(_ev(pygame.MOUSEBUTTONUP, pos=(hs.left + hs.w // 2, hs.centery), button=1))
    custom = fm.entries[1].color
    assert custom not in config.CURVE_PALETTE_20 and sb.picker_idx == 1
    _step(game, screen)

    hx = sb.custom.hex
    game.handle_event(_ev(pygame.MOUSEBUTTONDOWN, pos=hx.rect.center, button=1))
    game.handle_event(_ev(pygame.TEXTINPUT, text="#2fa4c8"))
    _step(game, screen)
    game.handle_event(_ev(pygame.KEYDOWN, key=pygame.K_RETURN, mod=0, unicode=""))
    assert fm.entries[1].color == parse_hex("#2fa4c8") == (0x2F, 0xA4, 0xC8)
    _step(game, screen)

    game.handle_event(_ev(pygame.MOUSEBUTTONDOWN, pos=sb._picker_cell(5).center, button=1))   # Red, closes
    assert sb.picker_idx is None and fm.entries[1].color == config.CURVE_PALETTE_20[5]
    _step(game, screen)
    print(f"smoke_p18 OK at {w}x{h}")


def main() -> None:
    pygame.init()
    for size in ((1280, 720), (1920, 1080)):
        phase(pygame.display.set_mode(size))


if __name__ == "__main__":
    main()
