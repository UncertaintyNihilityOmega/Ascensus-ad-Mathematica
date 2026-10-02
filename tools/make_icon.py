"""Draws the 256 px 'neon graph' icon and writes ascensus/assets/icon.png and icon.ico (pygame + numpy only)."""
from __future__ import annotations

import os
import struct
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import numpy as np  # noqa: E402
import pygame  # noqa: E402

SIZE = 256
SS = 2                                   # supersampling factor for smooth edges
BG = (10, 12, 26)
AXIS = (60, 70, 110)
CYAN = (0, 220, 255)
MAGENTA = (255, 60, 220)


def glow_curve(size: int, pts: list[tuple[float, float]], color: tuple[int, int, int], width: int) -> pygame.Surface:
    """A polyline drawn thick and blurred (layered) for a neon glow; returns an SRCALPHA surface."""
    out = pygame.Surface((size, size), pygame.SRCALPHA)
    for scale, alpha, w in ((4.0, 40, width * 4), (2.4, 80, width * 2.4), (1.0, 255, width)):
        layer = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.lines(layer, (*color, alpha), False, pts, int(w))
        out.blit(layer, (0, 0))
    pygame.draw.lines(out, (255, 255, 255, 200), False, pts, max(1, width // 3))
    return out


def draw_icon() -> pygame.Surface:
    """Render the icon at SIZE x SIZE (SRCALPHA)."""
    n = SIZE * SS
    surf = pygame.Surface((n, n), pygame.SRCALPHA)
    r = n // 5
    pygame.draw.rect(surf, (*BG, 255), (0, 0, n, n), border_radius=r)
    pygame.draw.rect(surf, (40, 50, 90, 255), (0, 0, n, n), width=SS * 3, border_radius=r)
    c = n // 2
    # faint axes and grid ticks
    pygame.draw.line(surf, (*AXIS, 150), (n // 10, c), (n - n // 10, c), SS * 2)
    pygame.draw.line(surf, (*AXIS, 150), (c, n // 10), (c, n - n // 10), SS * 2)
    for k in range(-3, 4):
        if k:
            p = c + k * n // 9
            pygame.draw.line(surf, (*AXIS, 120), (p, c - SS * 5), (p, c + SS * 5), SS)
            pygame.draw.line(surf, (*AXIS, 120), (c - SS * 5, p), (c + SS * 5, p), SS)
    # parabola opening upward with its vertex at the centre, clipped to the inner square
    unit = n / 9
    xs = np.linspace(-3.2, 3.2, 200)
    para = [(c + x * unit, c - 0.42 * x * x * unit) for x in xs]
    para = [(px, py) for px, py in para if n * 0.1 < py < n * 0.9]
    # sine through the origin
    xs2 = np.linspace(-3.4, 3.4, 240)
    sine = [(c + x * unit, c - 1.4 * unit * np.sin(x * 1.45)) for x in xs2]
    surf.blit(glow_curve(n, para, CYAN, SS * 5), (0, 0))
    surf.blit(glow_curve(n, sine, MAGENTA, SS * 4), (0, 0))
    # centre dot with a cyan ring
    pygame.draw.circle(surf, (*CYAN, 60), (c, c), SS * 20)
    pygame.draw.circle(surf, (*CYAN, 255), (c, c), SS * 14, SS * 4)
    pygame.draw.circle(surf, (255, 255, 255, 255), (c, c), SS * 8)
    # round the corners again so glow never leaks outside the square
    mask = pygame.Surface((n, n), pygame.SRCALPHA)
    pygame.draw.rect(mask, (255, 255, 255, 255), (0, 0, n, n), border_radius=r)
    surf.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    return pygame.transform.smoothscale(surf, (SIZE, SIZE))


def write_ico(png_bytes: bytes, path: Path) -> None:
    """ICONDIR (6 bytes) + one 16-byte entry (width/height 0 means 256) + the embedded PNG."""
    header = struct.pack("<HHH", 0, 1, 1)
    entry = struct.pack("<BBBBHHII", 0, 0, 0, 0, 1, 32, len(png_bytes), 6 + 16)
    path.write_bytes(header + entry + png_bytes)


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    out = root / "ascensus" / "assets"
    out.mkdir(exist_ok=True)
    pygame.init()
    pygame.display.set_mode((1, 1))
    icon = draw_icon()
    png = out / "icon.png"
    pygame.image.save(icon, str(png))
    write_ico(png.read_bytes(), out / "icon.ico")
    print(f"wrote {png} and {out / 'icon.ico'}")


if __name__ == "__main__":
    sys.exit(main())
