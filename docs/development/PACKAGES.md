# Work Packages: one per fresh Sonnet session

Each package ends with green checks, a STATUS.md line, and a stop. Read only the referenced sections.

## P1 · Math core (headless) · refs: ARCHITECTURE §1–3, DESIGN §5
- Create `.venv`, `requirements*.txt`, `.gitignore`, the package skeleton, and `config.py` (all DESIGN constants).
- Write `mathparse.py`, `curvefield.py` (`build_curve` + `render_curve`), `tests/test_mathparse.py`, and `tests/test_curvefield.py`.
- Parser tests must cover every DESIGN §5 must-pass example plus these variations: `2x`, `3sin(x)`, `(x+1)(x-1)`, `xy=1`, `2pi`, `y=x^(1/2)`, `√(x)`, `X^2`, `y = -x^2 + 3`.
- They must also reject: `sin x`, `x==2`, `2=3`, `import os`, `__import__('os')`, `x.real`, `foo(x)`, `sin(x,y)`, an empty string, and an 81-character string.
- **Done when** `pytest -q` passes.

## P2 · Game shell, no formulas yet · refs: DESIGN §1–4, §7; ARCHITECTURE §1, §5, §6 (widgets only)
- Write `main.py`, `__main__.py`, `scenes.py` (Menu, Game with the pause overlay, GameOver), `player.py`, `enemies.py`, and `ui/widgets.py`.
- Add the world-anchored dot background, the cached grid/axes overlay (G toggles it), the HUD, contact damage, i-frames, and death → GameOver → Retry/Menu.
- Write `tools/smoke.py` (no typing yet).
- **Done when** pytest and the smoke run pass and `python -m ascensus` runs. The user runs the game once to check.

## P3 · Formula combat · refs: DESIGN §3, §5, §7 (input box); ARCHITECTURE §4, §6
- Write `ui/inputbox.py` (focus, slow-mo, cursor keys, error display, edit mode hook) and the `formulas.py` FormulaManager without persistence.
- Add the active set, pulses, damage budget, flash, and the throttled round-robin `t` rebuild.
- Add a temporary **minimal** read-only list in the sidebar position (text + color), so the player can see what's active.
- Extend the smoke run to type 3 formulas and assert kills > 0. Add `tests/test_formulas.py` (manager ops except save/load).
- **Done when** checks pass. **PILOT CHECKPOINT: the user playtests and gives feedback before P4.** Write the feedback into STATUS.md.

## P4 · Sidebar and persistence · refs: DESIGN §6; ARCHITECTURE §4 (save/load), §6
- Write the full `ui/sidebar.py`: collapse/expand, rows, hover, the on/off switch, Edit (→ the input's edit mode), Del, drag reorder with an insertion gap, and the queued/off/off-screen tags. Replace the P3 minimal list with it.
- Add save/load to `save/formulas.json` on every change, and load on game start.
- Extend the smoke run with synthetic mouse events: toggle, drag row 3→1, edit, delete, collapse/expand. Add a save/load test.
- **Done when** checks pass and the user confirms that the drag feels right.

## P5 · Tuning and polish · refs: STATUS.md playtest notes, DESIGN §7
- Apply the playtest feedback by changing `config.py` numbers first. Add the menu's background-curve flourish if there's time.
- Do a perf check from smoke output (< 8 ms/frame). Write a `README.md` covering how to run, the controls, and the formula syntax cheat-sheet.
- **Done when** checks pass and the README exists.

---

# v2 packages (spec: plan/DESIGN_V2.md)
These run in order, one fresh Sonnet session each. Read **only** the DESIGN_V2 sections listed, plus the "Root cause" section for P6. Every package also extends `tools/smoke.py` and keeps all earlier tests green.

## P6 · Viewport and the y=x fix · refs: V1, Root cause
- **Fix first:** add the failing tests (`y=x` ≥ 400 points on the diagonal, `y=-0.01` visible), then fix `_find_roots`. Exact-zero nodes become root points, and edges with an exact-zero endpoint are skipped.
- Add `view.py` and replace every fixed `W/H` use with it. Add full screen on start, F11 to switch to the square resizable window, and `on_resize()` in every scene. Add `build_curve(size=, unit=)`.
- The smoke run must run at 1280×720 and at 1920×1080.
- **Done when** the tests and both smoke runs pass. **Then the user playtests.**

## P7 · Parser v2 and named equations · refs: V2, V3 "Named rows"
- Add the new functions with their aliases (`in` = `ln`), the 2-argument functions with a comma token, variables (letters and `a_1`-style subscripts) and the unknown-function check.
- Add the `name:` prefix with a uniqueness check in FormulaManager and the bold name in sidebar rows.
- Add the `name`/`funcs`/`variables` fields and `func(..., vars=)`. `MAX_FORMULA_LEN` becomes 120.
- **Done when** the new parser tests pass, including `eq4: (x^(2)+y^(2))^(3)=4 x^(2) y^(2)`.

## P8 · Collision, dash, regen, HP numbers and the boss · refs: V4 (Collision, Player, HP display, Boss)
- **Done when** the enemy and boss tests pass, and in the smoke run no two enemies overlap by more than 1 px after 10 s of play and no enemy overlaps the player.

## P9 · XP, upgrades, HUD stack and skull · refs: V4 (Damage model, XP, Upgrades panel, HUD stack, Skull icon)
- Set `MAX_ACTIVE` to 6.
- **Done when** the unit tests for cost growth and Auto's cheapest-first order pass and the smoke run buys upgrades. **Then the user playtests.**

## P10 · Sidebar v2 and clipboard · refs: V3 (everything except Variables)
- Add EQUATIONS, 200 rows, wheel scrolling per section, the 20-color picker, the queued layer with progressive loading, save format v2 and clipboard plus selection in the input box.
- **Done when** the smoke run with 150 equations meets the perf budget.

## P11 · Variables · refs: V3 Variables and Curve rebuilds
- Add `VariableStore`, the VARIABLES section (slider, value box, play) and rebuild scheduling.
- **Done when** the smoke run animates a variable and the save round-trip test passes. **Then the user playtests.**

## P12 · Settings, Stats, menus and profile · refs: V5
- **Done when** the settings round-trip test passes and the smoke run opens every page from both the menu and pause.

## P13 · Library and achievements · refs: V6
- **Done when** there is a tracker unit test per achievement and the smoke run unlocks at least 5. **Then the user playtests.**

## P14 · Icon, shortcuts and final pass · refs: V7, "Verification and perf budget"
- Make the icon (.png and .ico), the shortcuts (project folder and Desktop), the taskbar ID and README v2, and do a final perf pass at 1920×1080.
- **Done when** the icon files exist, the shortcuts launch the game and the README is updated. Then hand back to Opus for a visual review.

---

# v3 packages (spec: plan/DESIGN_V3.md)
Read **only** the DESIGN_V3 sections listed for the package. After each package: pytest + smoke pass, add a STATUS.md line, and make a local `git commit` (no push until P21).

## P15 · Repo and cleanup · refs: W1 · DONE by Opus

## P16 · Bug fixes #1–#9 · refs: bug table, W2 · run ALONE
- Fix each bug. Each one gets a regression test that fails before the fix (scene switch, picker over variables, settings focus per tab, input/panel overlap at 800×600 / 800×800 / 1920×1080, duplicate top-level defs).
- Switch text to `pygame.freetype`. Add `draw_text(max_w=, wrap=, min_size=)` and use it on the Achievements cards, buttons, settings rows, stats rows and upgrade buttons. Set the 800×600 minimum window size.

## P17 · Rename formulas → equations · refs: W3 · run ALONE
- **Done when** `rg -i formula ascensus tests tools` only hits the save-migration code, and the old `save/formulas.json` migrates to `save/equations.json` (with a test).

## P18 · Icons and colors · refs: W4 · may run in parallel with P19/P20
- Owns `tools/fetch_icons.py`, `assets/icons/`, `ui/icons.py`, the sidebar picker and `CURVE_PALETTE_20`.
- Icons must be **CC0** (Kenney). Anything missing is drawn in code.

## P19 · Controls, speed button and smooth curves · refs: W5 · parallel
- Owns `player.py`, `curvefield.render_curve`, the HUD timer area and the settings registry's Controls tab.

## P20 · Saves, Continue and Undo · refs: W6 · parallel
- Owns `savegame.py`, `saves_scene.py`, the menu/pause button lists and `EquationManager` undo.

## P21 · Final QA · refs: W7 · run ALONE, last
- Overflow audit test at 3 sizes, perf gate, README v3, then `git push`. After that, hand back to Opus for a visual review.
