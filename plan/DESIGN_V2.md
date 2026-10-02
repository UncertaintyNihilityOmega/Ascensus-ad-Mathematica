# Design v2 (approved 2026-10-02)

Extends DESIGN.md / ARCHITECTURE.md; where they conflict, **this file wins**. Packages P6-P14 in PACKAGES.md reference sections V1-V7 here.

## User decisions (2026-10-02)
- **Sidebar "hover-able":** mouse-wheel scrolling while hovering. The Equations and Variables sections scroll independently.
- **Dash:** R dashes toward the **last movement direction**, with no cooldown by default.
- **Variable names:** single letters (other than x, y, t, e) plus subscripts like `a_1` and `k_12`. `ab` still means a×b. New variables start at 1.
- **Collisions:** enemies have collision circles and must not stack on each other or overlap the player. Add contact knockback.
- **Extras:**
  - mini live graphs in the Library
  - Settings and Library also reachable from Pause
  - a desktop shortcut and a project-folder shortcut with the new icon
- **Icon:** the "neon graph" design: a cyan parabola and a magenta sine crossing at the player dot.
- **Upgrades ("gentle"):**
  - Max HP +10 per level (and heals 10).
  - Base DMG +10 per level.
  - Cooldown ×0.95 per level.
  - Cost starts at 20 XP and grows ×1.12 per purchase of that stat.
- `In()` / `in()` are aliases of `ln()`.
- Base regen: +10 HP/min, capped at max HP, with no upgrade for it.
- Achievements: 20 of them, with no rewards yet.
- Named equations use a `name:` prefix (e.g. `eq4: (x^(2)+y^(2))^(3)=4 x^(2) y^(2)`). The name is a label shown in the sidebar.

## Root cause: `y = x` shows "off-screen" (verified)
- In `curvefield._find_roots`, every grid node the line y=x crosses evaluates to **exactly 0**. Nodes sit at sx+sy=999, a multiple of the 3 px step.
- An edge with one exact-zero endpoint gets `f0 = 0`, so the pole filter `fr < 0.5*f0` rejects it.
- The same bug hides `y = -0.01`. Measured: `y=x` gives 0 points, while `y=-x` gives 481.
- **Fix:**
  - Add nodes where `V == 0` directly as root points.
  - Exclude edges with an exact-zero endpoint (`& (va != 0) & (vb != 0)`).
  - First write the failing tests (`y=x` ≥ 400 points on the diagonal, `y=-0.01` visible), as CLAUDE.md requires before changing the algorithm.

---

## Spec

### V1. Viewport, full screen and resize
- New `ascensus/view.py` holds the mutable `W, H`, `center()`, `math_to_screen` / `screen_to_math` and `set_size(w, h)`. Replace **every** `from .config import W, H` and `config.W/H` use with `view.W` / `view.H`, read at call time.
- `UNIT_PX` stays fixed (default 50, editable in Settings). A larger window shows more of the plane, because the visible range is ±W/2/UNIT_PX.
- **Start mode:** full screen at the desktop size (`pygame.display.get_desktop_sizes()[0]`, `FULLSCREEN`).
  - **F11** and the Settings ▸ Display toggle switch to a **square resizable window**. Its side is `WINDOW_SIZE` (default = 85% of desktop height) and the flag is `pygame.RESIZABLE`.
  - The window is resizable by dragging its edges, and the last mode is saved in settings.
- On `VIDEORESIZE` / `WINDOWSIZECHANGED`, call `view.set_size`, then the current scene's `on_resize()`. That handler re-lays-out the buttons, input box, sidebar and upgrade panel, rebuilds the dot and grid surfaces, marks every curve dirty, and drops cached curve surfaces.
- `curvefield.build_curve(f, t, step, size=None, unit=None, vars=None)` defaults to the view size and unit. An explicit size is used for the Library mini graphs. Its hit-mask shape follows the size.
- Spawn distance = `hypot(W, H)/2 + margin`, using the current size.
- Apply the `y = x` fix above, with its tests.

### V2. Parser v2 (`mathparse.py`)
- **1-argument functions** (aliases → canonical name):
  - Trig: sin, cos, tan, sec, csc, cot.
  - Inverse trig: asin/arcsin, acos/arccos, atan/arctan, asec/arcsec, acsc/arccsc, acot/arccot.
  - Hyperbolic: sinh, cosh, tanh, asinh/arsinh/arcsinh, acosh/arcosh/arccosh, atanh/artanh/arctanh.
  - Roots: sqrt, cbrt.
  - Rounding and sign: abs, sign/sgn, floor, ceil, round.
  - Exponentials and logs: exp, ln/in, log (base 10), log2.
- **2-argument functions:**
  - min(a,b), max(a,b), mod(a,b), hypot(a,b), atan2/arctan2(y,x)
  - root(n,x): the real n-th root; for odd integer n it is sign(x)·|x|^(1/n)
  - log(b,x): log base b, so `log` takes 1 or 2 arguments
- Arity is checked per function. Add a `,` token. No implicit `*` is inserted next to a comma. Tuples stay rejected by the AST whitelist.
- **Variables:**
  - After greedy longest-known-name splitting, any leftover single letter (not x, y, t or e) becomes a variable. A trailing `_digits` attaches to the letter (`ab_1` → a × b_1).
  - Tokenizer regex: `[a-z]+(?:_\d+)?`.
  - Heuristic: if an alpha run with no known function splits into ≥2 variables and is directly followed by `(`, raise "Unknown function 'sni' (for variables write s*n*i(...))".
- **Named equations:** an optional `name:` prefix, for example `eq4: (x^(2)+y^(2))^(3)=4 x^(2) y^(2)`.
  - Prefix regex: `^\s*([A-Za-z][A-Za-z0-9_]{0,15})\s*:\s*(.+)$`. The name keeps its case. The colon is otherwise illegal, so the prefix is unambiguous.
  - The name is a **label** only, and other equations can't reference it. That could come later, Desmos-style.
  - Names must be unique among the equations ("Name 'eq4' already used"). The 120-character limit applies to the body.
  - The saved and edited text is the full `name: body`. Edit loads it back with its name.
  - That example (a four-petal rose) and `r1: x^2+y^2=1` are added to the parser tests.
- `ParsedFormula` gains `name: str | None`, `funcs: frozenset[str]` (canonical names) and `variables: frozenset[str]`. `source` holds the body without the name.
  - `func(x, y, t=0.0, vars=None)`; missing variables default to `VAR_DEFAULT`.
  - The probe evaluation uses vars = 1.
- `MAX_FORMULA_LEN` goes from 80 to 120. Every existing test stays green, and new tests cover each function, the aliases, arity errors, the variables and the heuristic.

### V3. Equations, variables and the sidebar
- **Limits:** `MAX_ROWS = 200` equations, `MAX_VARIABLES = 200`, `MAX_ACTIVE = 6`.
- **Sidebar:** the header text "FORMULAS" becomes **"EQUATIONS"** (also used in messages), with "active n/6" beneath it.
  - Below sits a **"VARIABLES"** section with a count.
  - The panel spans the full window height. When variables exist, equations get 60% of the height and variables 40%; otherwise equations get all of it.
  - Each section is clipped and **scrolls with the mouse wheel while hovered** (3 rows per notch), with a thin scrollbar indicator.
  - Drag reorder keeps working inside a scrolled list and auto-scrolls within 30 px of a section edge.
- **Named rows:** a named equation shows its name in bold, in the curve color, followed by the dimmed body (`eq4  (x^2+y^2)^3=…`). The text is truncated as before. Unnamed rows look the same as now.
- **Color picker:**
  - Clicking a row's swatch opens a popup with **20 colors** in a 5×4 grid of 22 px squares (`CURVE_PALETTE_20`). Click a color to pick it; click outside or press Esc to close.
  - New equations take the first unused color, cycling once all are used.
  - Colors are now saved.
- **Variables:**
  - New `variables.py` with `VariableStore`, an ordered map from name to `Variable(value=1.0, playing=False, dir=+1)`.
  - A variable is auto-created when an equation that uses it is cast, and auto-removed when no equation uses it any more. Casting beyond 200 raises "Too many variables (200)".
  - Each row has the name, a **slider from VAR_MIN −5 to VAR_MAX 5** (click or drag, snapping to 0.01), a **value box** and a **play/pause button** (triangle or two bars, drawn with primitives).
    - The value box takes a click and then any typed float, which may lie outside ±5. Enter applies, Esc cancels. A focused value box triggers slow-mo the same way typing does.
    - Play ping-pongs between −5 and 5 in steps of `VAR_STEP` 0.01, ticking `VAR_PLAY_HZ` 60 times per second of game time.
  - Values are saved.
- **Curve rebuilds:** a formula is dirty if it uses `t` or a variable that changed.
  - Active dirty curves rebuild at most `T_REBUILD_HZ` (10) times per second each, at most 2 rebuilds per frame, round-robin.
  - Queued curves are **not** animated. They are drawn into **one shared "queued layer" surface**, refreshed at most once per second when it's dirty.
  - Only active entries (≤6) own full-screen surfaces. 200 surfaces at 1080p would need about 1.6 GB.
  - On load, the active curves build immediately and the queued ones build progressively, 2 per frame.
- **Save format:** `save/formulas.json` v2 is `{version: 2, formulas: [{text, enabled, color}], variables: {name: {value, playing}}}`. v1 files still load.
- **Input box clipboard:**
  - Ctrl+V pastes via `pygame.scrap.get_text()` (pygame-ce ≥ 2.2; newlines and tabs become spaces, and the max length is respected).
  - Ctrl+C copies the selection, or the whole text if nothing is selected (`pygame.scrap.put_text`). Ctrl+X cuts and Ctrl+A selects all.
  - Shift + Left/Right/Home/End extends the selection. Typing replaces the selection, which is drawn highlighted.

### V4. Combat, player and enemies
- **Collision** (`enemies.py`):
  - Per-enemy `radius` array: normal 12, boss `BOSS_RADIUS` 40.
  - After moving, run pairwise numpy separation (n×n distances, n ≤ 250 plus bosses, 2 iterations). Overlapping pairs push apart, weighted by mass ∝ r².
  - Enemies overlapping the player are pushed out to `r_p + r_e`; the player is never pushed.
  - Contact means `d ≤ r_p + r_e + CONTACT_SLOP` (2 px).
  - When an enemy deals contact damage, every touching enemy is knocked back `KNOCKBACK_DIST` (40 px) away from the player.
- **Player:**
  - Regen `PLAYER_REGEN_PER_MIN` = 10, capped at max HP.
  - Dash on R (KEYDOWN, ignored while typing): `DASH_DIST` 160 px over `DASH_TIME` 0.12 s toward the facing direction, with invulnerability during the dash and `DASH_COOLDOWN` 0 (no limit).
  - Facing = the last non-zero move direction (starts facing right), shown as a small triangle notch on the player ring.
- **HP display:**
  - The HP bar is removed. The player's HP shows as a **green integer under the player**.
  - Every on-screen enemy shows its HP as a **red integer under it** (font 16; the boss's is font 26). Both use the text cache.
- **Boss:**
  - Spawns every `BOSS_INTERVAL` = 300 s of game time (5:00, 10:00, …), like a normal enemy and not counted toward the max-alive cap.
  - Stats: HP = the current enemy HP × `BOSS_HP_MULT` 40, damage × 3, speed × 0.75, radius 40, purple (170, 60, 255).
  - A "BOSS INCOMING" banner shows for 2.5 s.
  - Its hit test is radius-aware: any hit-mask cell inside its bounding box counts.
- **Damage model:**
  - `dmg = clamp(base_dmg * DMG_SCALE / max(L, L_MIN), 1, base_dmg * 0.5)`, with `DMG_SCALE = 4`. Base DMG 100 therefore matches a damage budget of 400, the stronger value from the earlier simulation.
  - Pulse period = the cooldown stat (starts at 1.0 s, floor `COOLDOWN_MIN` 0.05).
- **XP:** each kill earns `XP_PER_HP` (0.5) × the enemy's max HP. Track the current XP plus totals earned and spent.
- **Upgrades panel** (bottom-right, re-laid-out on resize):
  - Four stacked buttons:
    - "Max HP: 110 / 22 XP": +10 max HP and heals 10.
    - "Base DMG: 100 / 20 XP": +10.
    - "Cooldown: 1.00s / 20 XP": ×0.95.
    - "Auto: OFF/ON", a toggle.
  - Each button is greyed out when unaffordable. Costs are `round(UPG_COST_BASE 20 × UPG_COST_GROWTH 1.12^level)`, tracked per stat, and levels reset every run.
  - With Auto on, the game buys the cheapest affordable upgrade each frame until nothing is affordable. Ties go HP → DMG → CD.
- **HUD stack** (top-right, right-aligned):
  - `12 :` plus the **skull icon**, in red.
  - `350 :XP` in green.
  - `60 :FPS` in orange (255, 160, 40), always the last line. It's shown by default, F3 toggles it, and the choice is saved in settings.
  - The timer stays at the top center.
- **Skull icon** (`ui/icons.py`):
  - Drawn with primitives at 96 px, then smoothscaled to the font height.
  - Shape: a cranium circle and a jaw rounded-rect, eye sockets shaped like **π** (a bar plus two legs), a **∇** (nabla) triangle nose, and **=** marks for teeth.

### V5. Menus and pages
- **Main menu:** buttons Play, Settings, Library, Achievements, Quit. Below them: "Best run: 07:32 · 154 kills", or "--:--" if there's no run yet. The help lines move into the Library.
- **Pause menu:** Resume, Stats, Settings, Library, Main Menu. Settings and Library return to pause.
- **Stats page** (from pause), with four column groups:
  - **Run:** time, kills, bosses killed, XP (current, earned, spent), dashes, total damage dealt, equations cast.
  - **Player:** HP / max, regen, base DMG, cooldown, upgrade levels and next costs, speed.
  - **Enemies now:** HP, damage, speed, spawn interval, alive count, next boss in mm:ss.
  - **Equations:** active n/6, total, variable count.
- **Settings** (`settings.py` registry + `SettingsScene`):
  - `Setting(key, label, tab, kind=int|float|bool|choice, min, max, step, note)`. Values are config attribute overrides, saved to `save/settings.json`, applied at startup with `setattr(config, …)`. Defaults are captured at import.
  - Layout: tabs on the left; on the right, rows of label, value (click to type), [−] [+] and a small reset button. A "(next run)" note marks values that only apply to a new run. There are "Reset tab" and "Reset all" buttons, the page scrolls on hover, and Esc / Back returns.
  - Tabs:
    - **Display:** fullscreen, window size, UNIT_PX (zoom 25–100), show FPS, show grid, GRID_STEP (curve quality 2–6).
    - **Player:** base max HP, speed, regen/min, i-frames, dash distance/time/cooldown, typing slow-mo.
    - **Enemies:** all `ENEMY_*`, the spawn rates, max alive, knockback.
    - **Boss:** interval, HP/DMG/speed multipliers, radius.
    - **Combat:** MAX_ACTIVE, base DMG start, base cooldown, cooldown min, DMG_SCALE, L_MIN, hit thickness.
    - **Upgrades & XP:** XP_PER_HP, the upgrade steps, cost base and growth.
    - **Equations & Variables:** max rows, max variables, VAR_MIN/MAX/STEP/PLAY_HZ/DEFAULT, T_REBUILD_HZ.
- **Profile** (`profile.py`, `save/profile.json`): best_time, best_kills, lifetime counters (dashes, kills) and achievements `{id: unlock date}`. It is saved at game over, on unlock and on quit.

### V6. Library and achievements
- **Library scene:**
  - Tabs: **Functions | Syntax | Variables | Combat | Upgrades & XP | Enemies & Bosses | Controls**.
  - The content is data in `library_data.py` (titles, syntax, explanations, examples), so changing it never touches layout code.
  - The Functions tab is a scrollable list of cards. Each card shows the name, aliases, syntax, a one-line explanation, an example equation and a **200×120 mini graph** rendered once with `build_curve(size=(200,120), unit=20)`, with faint axes.
- **Achievements** (`achievements.py`): data list plus `AchievementTracker.on(event, **data)`. The game emits these events: `cast(parsed)`, `kill`, `boss_kill`, `upgrade`, `auto_on`, `dash`, `var_play`, `var_created`, `tick(game_t, active_count)`.
  - Unlocks show a toast below the timer for 3 s, with a gold border: "Achievement unlocked: …".
  - The page is a 4×5 grid of cards with a medal icon (grey padlock if locked), name, description, unlock date and an "n/20" counter. There are no rewards.
  - The 20 achievements:
    1. **Hello, Sine:** cast an equation with sin
    2. **Co-Star:** cast one with cos
    3. **Off on a Tangent:** cast one with tan
    4. **Full Circle:** cast an equation containing both x² and y² (regex on `expr`: `x\*\*\(?2\)?` and `y\*\*\(?2\)?`, so `x^(2)` counts too)
    5. **Rooted:** use sqrt or root
    6. **Natural Talent:** use ln
    7. **Inverse Thinking:** use any inverse trig function
    8. **Hyperbole:** use sinh, cosh or tanh
    9. **Time Lord:** use t
    10. **Variable Star:** create a variable
    11. **Autoplay:** press play on a variable
    12. **Full House:** have 6 equations active at once
    13. **The Tan Monster:** cast `tan(sqrt(x^2+y^2))=y/x` (whitespace-insensitive)
    14. **First Blood:** get your first kill
    15. **Centurion:** 100 kills in one run
    16. **Giant Slayer:** kill a boss
    17. **Survivor:** survive 5:00
    18. **Marathon:** survive 15:00
    19. **Investor:** buy an upgrade
    20. **Dash Addict:** dash 100 times (lifetime)

### V7. Icon, shortcut and taskbar
- `tools/make_icon.py` draws the 256 px "neon graph" icon:
  - a dark rounded square with faint axes
  - a glowing cyan parabola and a magenta sine
  - a white dot with a cyan ring at the center

  It writes `assets/icon.png` and `assets/icon.ico`. The .ico is a PNG embedded in an ICO, written by hand: a 6-byte ICONDIR plus a 16-byte entry with width/height 0 (= 256).
- `main.py`:
  - Before `display.set_mode`, call `ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Ascensus.ad.Mathematica")` (only when on Windows), so the taskbar shows our icon.
  - Call `pygame.display.set_icon(icon.png scaled to 64)`.
- `tools/make_shortcut.ps1` creates "Ascensus ad Mathematica.lnk" in the project folder **and** on the Desktop, using WScript.Shell:
  - Target: `.venv\Scripts\pythonw.exe`
  - Arguments: `-m ascensus`
  - Working directory: the project folder
  - Icon: `assets\icon.ico`

  `Play.bat` runs the script after first-time setup.

---

## Reused existing code
- `curvefield._find_roots` / `_dilate` / `render_curve`: extend with the size and vars arguments, don't rewrite.
- `ui/widgets.draw_text`, its text cache and `Button`: reuse for every new page. Add `Tabs`, `Slider`, `NumberField` and `ScrollArea` helpers to `ui/widgets.py`.
- `Swarm.damage_where`: add the radius-aware path for the boss.
- `FormulaManager` add/replace/move/save: extend for colors, the v2 format and variables.
- The sidebar's drag logic: keep it and add a scroll offset.
- `tools/smoke.py`: extend each package's synthetic-event script.

## Verification and perf budget
- Each package runs `.venv\Scripts\python -m pytest -q` and `.venv\Scripts\python tools\smoke.py`. Smoke runs at both 1280×720 and 1920×1080 using the dummy driver.
- **Perf budget** at 1920×1080 with 200 enemies, 1 boss, 6 active equations (1 with `t`, 1 with an animated variable) and 50 queued equations: average < 10 ms and p95 < 16 ms per frame.
- **After P6, P9, P11 and P13**, the user double-clicks Play.bat for a short playtest, and the feedback goes into STATUS.md.
- Opus at the end: one rendered-frame check (game, settings, library, achievements) to review the visuals, as done previously.
