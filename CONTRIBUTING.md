# Contributing

Thanks for wanting to help! Bug reports, balance ideas, new achievements and code are all welcome.

## Getting started

```bash
python -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"      # Windows: .venv\Scripts\python ...
.venv/bin/python -m pytest
.venv/bin/python tools/smoke.py
```

## Guidelines

- **Every tunable number lives in `ascensus/config.py`.** Read it as `config.NAME` at use time (never
  `from ascensus.config import NAME`) so the Settings page can change it while the game runs.
- **Window size comes from `ascensus/view.py`** (`view.W`, `view.H`); every scene must survive `on_resize()`.
- **Text goes through `ascensus/ui/widgets.py`** (`draw_text`, which can fit and wrap); icons through
  `ascensus/ui/icons.py`.
- The equation evaluator only runs whitelisted syntax trees (see `ascensus/core/mathparse.py`); never `eval`
  user text directly. The core math modules stay free of pygame so the tests run headless.
- Changing the curve root finder needs a failing test first (`tests/test_curvefield.py`).
- Tests must never touch the real `save/` folder (`tests/conftest.py` fails the run if they do).
- Keep the code plain and readable: type hints, short docstrings, numpy for anything per pixel or per enemy.

## Licensing

The project is public domain ([Unlicense](LICENSE)). By contributing you agree that your contribution is
released under the same terms. Only add assets that are CC0 / public domain or made by you.
