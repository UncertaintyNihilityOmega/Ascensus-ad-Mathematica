# Architecture

## 1. Layout
```
requirements.txt          pygame-ce>=2.5.7, numpy>=2.0   (never install plain `pygame` alongside)
requirements-dev.txt      pytest
.gitignore                .venv/ save/ __pycache__/
ascensus/
  __init__.py
  __main__.py             from .main import main; main()
  config.py               ALL constants (DESIGN numbers, colors, palette, paths)
  mathparse.py            text -> ParsedFormula        (numpy only, no pygame)
  curvefield.py           F -> CurveData (points, hit mask, length); render to Surface
  formulas.py             FormulaEntry, FormulaManager (list ops, active set, pulses, save/load)
  enemies.py              Swarm (numpy struct-of-arrays), difficulty(t)
  player.py               Player
  scenes.py               Scene base, MenuScene, GameScene (+pause), GameOverScene
  main.py                 init, window, loop, scene switching
  ui/__init__.py
  ui/widgets.py           fonts cache, draw_text, Button
  ui/inputbox.py          InputBox
  ui/sidebar.py           Sidebar
tests/test_mathparse.py, tests/test_curvefield.py, tests/test_formulas.py
tools/smoke.py            headless run (SDL_VIDEODRIVER=dummy), synthetic input, timing report
```
Main loop: `real_dt = min(clock.tick(60)/1000, 0.05)`. Each scene has `handle_event(e)`, `update(real_dt)`, `draw(screen)`, plus a `next_scene` attribute that the loop checks after update. Only GameScene applies the time scale.

## 2. mathparse.py
```python
class FormulaError(ValueError): ...          # message is shown to the player verbatim

@dataclass(frozen=True)
class ParsedFormula:
    source: str                              # original text, stripped
    expr: str                                # final python expr of F, e.g. "(y)-(x**2)"
    uses_t: bool
    func: Callable[[np.ndarray, np.ndarray, float], np.ndarray]   # F(x,y,t), curve is F=0

def parse_formula(text: str) -> ParsedFormula
```
Pipeline:
1. Strip the text. If it's empty or longer than 80 characters, raise "Formula is empty / too long (max 80)". Lowercase it, then replace `^`→`**`, `×`→`*`, `÷`→`/`, `−`→`-`, `π`→`pi`, and `√`→`sqrt`.
2. Split on `=`. If there's more than 1, raise "Only one '=' allowed". If a side is empty, raise "Missing expression on one side of '='".
3. **Tokenize** each side with the regex `\s+ | \d+\.?\d*|\.\d+ | [a-z]+ | \*\*|[-+*/%()]`. Anything else raises "Unexpected character 'c'". Split each alpha run greedily, taking the **longest** known name at each position from FUNCS ∪ {pi, e} ∪ {x, y, t}: `xsin`→`x sin`, `exp`→`exp` (not `e xp`), `2pix`→`2 pi x`. An unknown run raises "Unknown name 'q'".
4. **Implicit multiplication**: insert `*` between token A and token B when A ∈ {number, var, const, `)`} and B ∈ {number, var, const, func, `(`}. A func not followed by `(` raises "Use parentheses: sin(x)".
5. Join each side into a string and call `ast.parse(s, mode="eval")` (on `SyntaxError`, raise "Can't read formula"). Then walk the tree and allow **only** these nodes:
   - Expression, BinOp(Add, Sub, Mult, Div, Pow, Mod), UnaryOp(UAdd, USub), and numeric Constant.
   - Name loads from {x, y, t, pi, e}.
   - Call whose func is a Name in FUNCS, with exactly 1 positional arg and no keywords.

   Anything else raises "Can't read formula".
6. Build F:
   - With one side: if `y` doesn't appear, F = `(y)-(side)`, otherwise F = `(side)`.
   - With two sides: F = `(lhs)-(rhs)`.
   - If neither `x` nor `y` appears anywhere, raise "Formula needs x or y".
7. Compile once with `code = compile(expr, "<formula>", "eval")`. Then:
   ```python
   def func(x, y, t=0.0):
       with np.errstate(all="ignore"):
           v = eval(code, {"__builtins__": {}}, {**NS, "x": x, "y": y, "t": t})
           return np.broadcast_to(np.asarray(v, dtype=float), np.shape(x))
   ```
   `NS` = numpy ufuncs, where `ln=np.log`, `log=np.log10`, `sec=lambda a:1/np.cos(a)` (likewise csc and cot), `pi=np.pi`, and `e=np.e`.
8. Smoke-evaluate F on a 3×3 grid. If that raises an exception, raise FormulaError "Can't evaluate formula".

Known limitation (acceptable): `x^(1/3)` is NaN for x<0 (use `cbrt`). Tangent-only zeros like `(x-1)^2=0` don't draw.

## 3. curvefield.py: VERIFIED algorithm
The prototype ran on 2026-10-02 (numpy 2.5, 3 px grid), with these results:
- unit circle 130 pts / 19 ms
- `y=tan(x)` 2221 pts / 8 ms, with **0 points on asymptotes**
- `tan(r)=y/x` 2520 pts / 10 ms
- `y=1/x`, with 0 points at the pole

```python
@dataclass
class CurveData:
    points: np.ndarray      # (N,2) float32 SCREEN px (sx, sy)
    hit_mask: np.ndarray    # bool, shape (ceil(H/HIT_CELL), ceil(W/HIT_CELL)), dilated
    length_units: float     # occupied (undilated) coarse cells * HIT_CELL / UNIT_PX

def build_curve(f, t=0.0, step=GRID_STEP) -> CurveData     # GRID_STEP=3, t-formulas use 5
def render_curve(points, color, size) -> pygame.Surface      # SRCALPHA, colored, per-pixel alpha
```
Root finding (copy this logic; it is proven; runnable reference: `plan/reference/curve_probe.py`):
```python
sx = np.arange(0, W + step, step); sy = np.arange(0, H + step, step)
xs = (sx - W/2 + 0.5) / UNIT_PX;  ys = -(sy - H/2 + 0.5) / UNIT_PX     # +0.5 avoids exact 0
X, Y = np.meshgrid(xs, ys); V = f(X, Y, t)
for each edge set (horizontal: [:, :-1] vs [:, 1:], vertical: [:-1] vs [1:]):
    m = isfinite(va) & isfinite(vb) & (sign(va) != sign(vb));  keep masked endpoints
    f0 = minimum(|va|, |vb|)
    repeat 5x: mid = (a+b)/2; vm = f(mid); move a or b to mid keeping the sign change (np.where)
    fr = minimum(|va|, |vb|)
    keep where isfinite(fr) & (fr < 0.5 * f0)     # POLE FILTER: real roots shrink, poles grow
    root = (a+b)/2  -> convert math -> screen px
```
- **Hit mask**: `occ[iy//HIT_CELL, ix//HIT_CELL] = True` (HIT_CELL=8), then `length_units = occ.sum()*HIT_CELL/UNIT_PX`. Dilate by `HIT_DILATE=2` cells using `np.zeros_like` + shifted `|=` (no scipy). Enemy test: `mask[sy//8, sx//8]` with a bounds check, vectorized over the whole swarm.
- **Render**: make a `uint8 alpha[W,H]` array (surfarray is indexed **[x, y]**!). Write 255 at the points, then dilate 1 px for the core (3 px line). Next, take a second array dilated by 3 more px, set it to 80, and take `np.maximum` with the core for the glow. Create `Surface((W,H), SRCALPHA)`, `fill(color)`, then write `pygame.surfarray.pixels_alpha(surf)[:] = alpha` and `del` the view. At draw time use `surf.set_alpha(a)`.

## 4. formulas.py
```python
@dataclass
class FormulaEntry:
    text: str; enabled: bool; color: tuple
    parsed: ParsedFormula; curve: CurveData | None = None; surface: Surface | None = None
    pulse_timer: float = 0.3; flash: float = 0.0; rebuild_timer: float = 0.0

class FormulaManager:
    def __init__(self, save_path: Path | None)            # None = no persistence (tests)
    entries: list[FormulaEntry]
    def add(self, text) -> FormulaEntry                    # FormulaError on bad text or full (12)
    def replace(self, i, text); delete(i); move(src, dst); toggle(i)   # each calls save()
    def active(self) -> list[FormulaEntry]                 # first MAX_ACTIVE enabled
    def status(self, e) -> "active" | "queued" | "off" | "offscreen"
    def update(self, dt, game_t, swarm) -> int              # rebuild t-curves, pulses, damage; returns kills
    def draw(self, screen)
    def save(self); load(self)                              # JSON {"version":1,"formulas":[{"text","enabled"}]}
```
- Pygame surfaces are built lazily in `draw` (so the tests stay headless).
- Pulse logic: `pulse_timer -= dt`. When it hits ≤0, add `PULSE_PERIOD` back, set `flash = FLASH_TIME`, and call `swarm.damage_where(mask, dmg)`.
- `load` silently skips entries that fail to parse.
- Colors are reassigned in order on load.

## 5. enemies.py
`Swarm` holds the numpy arrays `pos (n,2) float`, `hp`, `max_hp`, `dmg`, `speed`, and `flash`. Its methods:
- `spawn(player_pos, game_t)`
- `update(dt, player_pos)`, which does vectorized chase
- `contact_damage(player_pos, r) -> float`, which returns the max damage among overlapping enemies (0 if none)
- `damage_where(hit_mask, dmg, player_pos)`, which converts world→screen, applies the mask, subtracts dmg and sets flash
- `remove_dead() -> int`
- `draw(screen, player_pos)`, which loops `pygame.draw.circle` over the on-screen enemies only

`difficulty(game_t) -> (hp, dmg, speed, interval)` uses the DESIGN §4 formulas, and `Spawner` is a time accumulator. Removal uses boolean-mask compression, never per-item `del`.

## 6. UI
- `InputBox`: has the fields `text`, `cursor`, `focused`, `edit_index`, `error`, `error_timer`. Its `handle_event(e) -> "submit" | "cancel" | None` uses `TEXTINPUT` for characters (ignored when unfocused) and `KEYDOWN` for the editing keys.
  - Guard: the Enter that *focuses* the box must not also submit, so only submit if the box was already focused before this event.
- `Sidebar(manager, input_box)`: `handle_event(e) -> bool` (True = consumed), `update(dt)`, `draw(screen)`, plus `dragging` and `collapsed` properties.
  - Store row rects each frame for hit testing. Mouse events inside the panel rect are always consumed.
- GameScene routes events in this order: pause overlay → sidebar → input box → game keys. Time scale = 0.2 if `input.focused or sidebar.dragging`.

## 7. Testing (cheap, no screenshots)
- `pytest -q`: parser accept/reject lists, numeric checks (`x^2` at (2,4) gives F=0), and the curve checks.
  - Curve checks: the circle's `length_units` is within 15% of 2π; `x=2` points all have sx≈740±2; the tan and 1/x pole leak counts are 0; the tan monster has >500 points.
  - Manager checks: move, delete, toggle, the active set, and a save/load round trip (tmp_path).
- `tools/smoke.py`: sets `SDL_VIDEODRIVER=dummy` and `ASCENSUS_SAVE` to a temp file. It drives a GameScene for 1800 frames at a fixed dt of 1/60, posting synthetic events (Enter, TEXTINPUT chars, Enter for 3 formulas incl. one with `t`, plus later packages' sidebar clicks/drags).
  - It asserts there are no exceptions, kills > 0, and the formula count is as expected.
  - It prints the average and p95 ms per frame (budget: < 8 ms with 200 enemies and 4 formulas).
