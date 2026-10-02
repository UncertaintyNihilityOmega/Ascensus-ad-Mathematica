# Ascensus ad Mathematica

A fun free survival game where the magic is math equations.

A survival game where the equations you type are your weapons. Enemies chase you from
off-screen; every curve you cast pulses and damages everything it touches. Kills give XP, XP buys
upgrades, and a boss arrives every 5 minutes. The game starts full screen; you stand at the origin
and the visible plane is ±(width/2)/50 by ±(height/2)/50 units.

## Run

**First time:** double-click `tools\setup.bat` (needs internet once). It creates the Python
environment, installs the packages and makes the "Ascensus ad Mathematica" shortcut in the
project folder and on the Desktop.

**Play:** double-click the "Ascensus ad Mathematica" shortcut.

Manual setup: Python 3.14 on Windows (PowerShell, from the project folder):

```powershell
py -3.14 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt -r requirements-dev.txt
.venv\Scripts\python -m ascensus
```

Other commands:

```powershell
.venv\Scripts\python -m pytest -q        # unit tests
.venv\Scripts\python tools\smoke.py      # headless play-through at 1280x720 and 1920x1080, with timings
.venv\Scripts\python tools\make_icon.py  # regenerate assets/icon.png and icon.ico
powershell -File tools\make_shortcut.ps1 # recreate the shortcuts
```

Use `pygame-ce` (it is in `requirements.txt`); do not install plain `pygame` next to it.

## Menus

- **Main menu:** Play, Settings, Library, Achievements, Quit, and your best run.
- **Pause (Esc):** Resume, Stats, Settings, Library, Main Menu. Settings and Library return to the paused game.
- **Settings:** tabs for Display, Player, Enemies, Boss, Combat, Upgrades & XP and Equations & Variables.
  Click a value to type it, use - / + or reset it. Saved to `save/settings.json`.
- **Library:** every function with a live mini graph, syntax, combat, upgrades, enemies and controls.
- **Achievements:** 20 of them, saved with your best run in `save/profile.json`.

## Controls

| Input | Effect |
|---|---|
| WASD / arrow keys | Move (disabled while typing) |
| R | Dash toward your last movement direction (invulnerable while dashing) |
| Enter, or click the box | Focus the equation box (time slows to 20 %) |
| Enter (typing) | Cast the equation; a red error appears if it can't be read |
| Ctrl+V / C / X / A, Shift+arrows | Paste, copy, cut, select all, extend selection in the box |
| Esc | Cancel typing; when not typing, pause |
| G | Toggle the grid and axes |
| F3 | Toggle the FPS readout |
| F11 | Switch between full screen and a square resizable window |

## Sidebar

- **EQUATIONS** (up to 200): drag to reorder, pill switch on/off, **Edit** loads it into the box,
  **Del** removes it, click the colour swatch for a 20-colour picker. The mouse wheel scrolls the
  list while hovered. The first 6 enabled rows fire; the rest are "queued" (faint, not animated).
- **VARIABLES** (up to 200, appear automatically): slider -5..5, a value box (type any number),
  and a play button that ping-pongs the value.
- Named equations: `eq4: (x^(2)+y^(2))^(3)=4 x^(2) y^(2)` shows `eq4` in bold. Names are unique labels.
- Everything is saved to `save/formulas.json` after every change.

## Formula syntax cheat-sheet

- **Variables and constants:** `x`, `y`, `t` (seconds of game time), `pi` (or `π`), `e`. Any other
  single letter, or a letter with a subscript like `a_1`, is a **variable** that starts at 1.
  `ab` means a·b; `ab_1` means a·b_1.
- **Operators:** `+ - * / % ^` (also `**`, `×`, `÷`, `−`), parentheses, and implicit multiplication:
  `2x`, `3sin(x)`, `(x+1)(x-1)`, `xy`, `2pi`.
- **Functions** (always with parentheses; `ln` and `in` are the same):
  - trig `sin cos tan sec csc cot`, inverse `asin/arcsin acos atan asec acsc acot`;
  - hyperbolic `sinh cosh tanh asinh acosh atanh`;
  - `sqrt cbrt abs sign floor ceil round exp ln log log2` (`log` is base 10);
  - two arguments: `min max mod hypot atan2 root(n,x) log(b,x)`.
- **Meaning:**
  - no `=` and no `y`: it is `y = expr`, so `x^2` draws a parabola;
  - no `=` but with `y`: the curve is `expr = 0`;
  - one `=`: the curve is `left = right`, e.g. `x = 2`, `1 = x^2 + y^2`, `y = x`.
- A formula needs `x` or `y`; one `=` at most; max 120 characters (after the name); case is ignored.
- Examples: `x^3`, `x = -4`, `y = a*sin(x + t)`, `x^2 + y^2 = (t % 5)^2`, `tan(sqrt(x^2 + y^2)) = y / x`.
- Limits: `x^(1/3)` is undefined for negative x (use `cbrt(x)`), and curves that only touch zero
  without crossing it, like `(x-1)^2 = 0`, are not drawn.

## Combat, XP and upgrades

- A pulse deals `base_dmg * 4 / L` damage (clamped to 1 .. base_dmg/2) to every enemy near the
  curve, where `L` is the curve's visible length in grid units. Short curves hit hard, long ones are gentle.
  The pulse period is your **cooldown** stat (starts at 1 s).
- Enemies collide with each other and with you, and knock back when they hit. You regenerate 10 HP/min.
- Kills give XP (half the enemy's max HP). Spend it in the bottom-right panel: **Max HP** (+10, heals 10),
  **Base DMG** (+10), **Cooldown** (x0.95) and **Auto** (buys the cheapest affordable upgrade). Costs
  start at 20 XP and grow x1.12 per purchase of that stat; levels reset every run.
- HUD (top right): kills with a skull, XP, FPS. Your HP is the green number under you, enemy HP the red numbers.
- All numbers live in `ascensus/config.py`; most can be changed in Settings.

## Files and saves

`save/formulas.json` (equations, colours, variables), `save/settings.json`, `save/profile.json`
(best run, lifetime counters, achievements). Delete a file to reset it.

## License

Released into the public domain under the [Unlicense](LICENSE). Dependencies (pygame-ce, numpy)
are installed with pip and are not part of this repository.
