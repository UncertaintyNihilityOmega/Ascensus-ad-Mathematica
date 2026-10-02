# Ascensus ad Mathematica: notes for Claude Code sessions

A pygame-ce survival game where typed math curves are the weapons. README.md describes the game,
CONTRIBUTING.md the code rules (they apply here too). `docs/development/` holds the original plans: history,
not the current reference.

## Commands (project root; Windows paths shown)
- Setup: `py -3.14 -m venv .venv` then `.venv\Scripts\python -m pip install -e ".[dev]"` (or `tools\setup.bat`)
- Tests: `.venv\Scripts\python -m pytest`
- Smoke run (headless game, frame times): `.venv\Scripts\python tools\smoke.py` (`ASCENSUS_PERF_GATE=1` makes slow frames fail)
- Screenshots for the README: `.venv\Scripts\python tools\screenshots.py`
- Play: `.venv\Scripts\python -m ascensus`

## Layout
`ascensus/core` (parser, curve engine, equations, variables, equation matching), `ascensus/game` (player,
enemies, upgrades, controls, save games, profile, achievements, stats), `ascensus/scenes` (menu, game,
game over, pages), `ascensus/ui` (widgets, sidebar, input box, picker, icons, file dialogs, layout),
`ascensus/data`, `ascensus/assets`, `ascensus/config.py` (every tunable number).

## Rules
- Use **pygame-ce**, never plain `pygame`; numpy for anything per pixel or per enemy.
- Read config as `config.NAME` at use time (Settings changes it live); window size only from `ascensus/view.py`.
- Absolute imports (`from ascensus.core.mathparse import ...`); scene modules reference each other through
  their sibling *module* (e.g. `game_scene.GameScene`) to stay circular-safe.
- `core/mathparse.py` and `core/curvefield.build_curve` must not import pygame (headless tests).
- The equation evaluator only runs the AST whitelist with `{"__builtins__": {}}`; never eval raw user text.
- Text through `ui/widgets.py` (`get_font`, `draw_text`; pygame.freetype with `origin=True`); icons through
  `ui/icons.py`. No Unicode glyphs.
- `pygame.surfarray` arrays are `[x, y]`; meshgrid arrays are `[row=y, col=x]`.
- Tests must never touch the real `save/` folder (`tests/conftest.py` guards it). Equations are saved only
  inside runs (autosave and slots).
- Don't change the curve root finder or its pole filter without a failing test first.
- Licensing: Unlicense (public domain). Only CC0 / public-domain assets in the repo.
- Commit with a clear message after each finished piece of work; push only when asked.
