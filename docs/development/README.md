# Development notes

These are the planning documents the game was built from, kept as a record of how it grew. They are
**history, not the current reference**: the code, the README and the tests describe the game as it is.

| File | What it is |
|---|---|
| `PROJECT.md` | The original project brief and decisions |
| `DESIGN.md`, `ARCHITECTURE.md` | v1: the first playable prototype (curve engine, parser, combat, sidebar) |
| `DESIGN_V2.md` | v2: full screen, variables, upgrades, bosses, settings, library, achievements |
| `DESIGN_V3.md` | v3: bug fixes, icons, colours, controls, speed button, saves |
| `PACKAGES.md`, `STATUS.md` | The work packages and the log of every build session |
| `reference/curve_probe.py` | The first prototype of the curve root finder and its pole filter |

Module paths in these files are from before the 1.0 reorganisation (e.g. `ascensus/mathparse.py` is now
`ascensus/core/mathparse.py`).
