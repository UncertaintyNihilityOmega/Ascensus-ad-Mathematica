# Ascensus ad Mathematica: operating rules

A Python prototype of a survival game where typed math curves are the weapons. The plan lives in `plan/`. Start with `plan/PROJECT.md`.

## Each session
1. Read `plan/STATUS.md` → find the next package in `plan/PACKAGES.md`.
2. Read **only** the sections that package references. P6 onward is specified in `plan/DESIGN_V2.md`, which overrides DESIGN.md and ARCHITECTURE.md wherever they conflict. Don't re-read the whole plan or unrelated code. Use grep for lookups.
3. Implement that one package only. Write each file once, then fix with small edits, never full rewrites.
4. Run the checks (below), fix any failures, and append one line to `plan/STATUS.md`. Then stop and reply in ≤3 lines.
5. Verify with pytest and `tools/smoke.py` output, not screenshots.
6. After each package: `git commit` with the package id in the message. Push only at batch end (P21).
7. Parallel agents (max 3) only for packages marked parallel. Each agent owns its files; two agents never edit the same file. P16, P17 and P21 run alone.
8. Licensing: the project is Unlicense (public domain). Only CC0 / public-domain assets may be added to the repo (no MIT/ISC/OFL files). Pip dependencies are fine because they aren't bundled.

## Commands (PowerShell, project root)
- Setup: `py -3.14 -m venv .venv` then `.venv\Scripts\python -m pip install -r requirements.txt -r requirements-dev.txt`
- Tests: `.venv\Scripts\python -m pytest -q`
- Smoke: `.venv\Scripts\python tools\smoke.py`
- Play: `.venv\Scripts\python -m ascensus`

## Code rules
- Use **pygame-ce**; never install plain `pygame`. Use numpy for anything per-pixel or per-enemy.
- Every tunable number goes in `ascensus/config.py`. Always read it as `config.NAME` at use time, never via `from .config import NAME`, so that Settings can change it at runtime.
- From P6 on, window size comes only from `ascensus/view.py` (`view.W`, `view.H`), never from constants. Everything must survive `on_resize()`.
- Perf budget (from P6 on): at 1920×1080 with 200 enemies, 6 active equations and 50 queued, average < 10 ms and p95 < 16 ms per frame, as reported by `tools/smoke.py`.
- `mathparse.py` and `curvefield.build_curve` must not import pygame, so the tests stay headless.
- The equation evaluator must use the AST whitelist plus `{"__builtins__": {}}` (ARCHITECTURE §2). Never use eval on raw user text.
- `pygame.surfarray` arrays are indexed `[x, y]`; numpy grids from meshgrid are `[row=y, col=x]`. Convert carefully.
- Text goes through `ui/widgets.py` (`get_font` / `draw_text`, pygame.freetype with the built-in font, `origin=True`). Never call `pygame.font` directly. Icons come from `ui/icons.py` (Kenney CC0 PNGs), or are drawn with primitives; no Unicode glyphs.
- Tests must never touch the real `save/` folder. Save paths are read at call time (`equations.USE_CONFIG`), and `tests/conftest.py` fails the run if `save/` changes.
- Keep the code plain and readable: type hints, short docstrings, no frameworks beyond pygame-ce and numpy.
- Don't change the curve algorithm in ARCHITECTURE §3 without a failing test that shows why.
