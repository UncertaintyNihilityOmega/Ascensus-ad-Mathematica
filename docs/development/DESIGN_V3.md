# Design v3 (approved 2026-10-02)

Extends DESIGN_V2.md; where they conflict, **this file wins**. Packages P15-P21 in PACKAGES.md reference sections W1-W7 and the bug table here.

## Bugs: verified root causes
| # | Bug | Root cause (verified) | Fix |
|---|---|---|---|
| 1 | Pause → Settings/Library → Back makes the screens flash | `GameScene.next_scene` is never cleared. `_return_here` returns the *same* GameScene, which still has `next_scene = SettingsScene`, so `main.py` switches back and forth every frame. | In the main loop, set `scene.next_scene = None` before switching. Regression test: pause → settings → back → 5 frames, and the scene stays the GameScene. |
| 2 | Can't change an equation's color | The popup opens under the swatch and overlaps the VARIABLES section. `Sidebar.handle_event` runs `_handle_vars` **before** the picker, so the variable rows take the clicks. The popup is also drawn underneath them. | Make the picker modal: when it's open it gets events first and is drawn last, on top of everything. Enlarge the swatch hit area to 22 px. |
| 3 | Text overflows in small windows (worst on Achievements) | The renders confirm it: titles are cut mid-phrase ("Off on a", "The Tan") and "Unlocked 2026-10-0" runs past the card edge. Text is drawn without any width limit. | Add `draw_text(..., max_w=, wrap=, min_size=)` to `ui/widgets.py`: shrink the font down to `min_size`, then wrap or add "…". Use it for every button, card, setting row, stats row and upgrade button. Set a minimum window size of 800×600 via `pygame.Window.from_display_module().minimum_size`. |
| 4 | Settings: some fields change on click, some won't take typing | `SettingsScene._click` loops over **every** tab's NumberField. Fields from hidden tabs keep their old rects and steal focus. Measured: 37 of 47 fields focus the wrong key. Typing then changes a hidden setting, e.g. the window size. | Only the visible tab's fields get events. Clicking elsewhere commits the focused field. Enter applies and Tab moves to the next field. Regression test: clicking every numeric row focuses its own key (the probe I ran). |
| 5 | Letter gaps: "Pi xel s", "act ive", "Ki l l s" | `pygame.font.Font(None)` (SDL_ttf) spaces letters badly at small sizes. In a side-by-side test, `pygame.freetype` rendering the **same built-in font** draws them correctly. | Switch `get_font` / `draw_text` (and the sidebar's bold cache) to `pygame.freetype`. No font file is added, so there are no license concerns. |
| 6 | Auto button hides under the input box in small windows | The upgrade panel and the centered input box overlap horizontally (visible in the 800×800 render). | Layout rule: the input box is centered in the free space between the sidebar and the panel, at least 300 px wide. If it still doesn't fit, the panel stacks **above** the input box. A test checks for no overlap at 800×600, 800×800 and 1920×1080. |
| 7 | (mine) Smoke perf gate fails at 1280×720 | p95 is 17.1 ms against a 16 ms gate. | Re-measure after the smooth-curve rewrite in P19, then fix or re-gate in P21. |
| 8 | (mine) Duplicate definitions from the parallel agents | `profile.py` defines `get_profile` and `set_profile` twice. | Remove the duplicates. Add a test that scans every module for duplicate top-level defs. |
| 9 | (mine) Stray files | `prof.out` sits in the root, and the machine-specific `.lnk` would be committed. | Delete `prof.out`. Git-ignore `*.lnk`, `save/` and `prof.out`. |

## Decisions (2026-10-02)
- **Save slots store the full run** and are resumable: time, HP, XP and upgrades, enemies and bosses, equations, variables and colors.
- **Colors:** 20 organized swatches plus a Custom row (hue strip and a `#RRGGBB` box).
- **Assets must be license-free for the Unlicense:**
  - Text: `pygame.freetype` with pygame's built-in font. Nothing is bundled.
  - Icons: **Kenney CC0 packs** ("Game Icons" and "Board Game Icons" from kenney.nl). Any icon they lack is drawn in our own code (Unlicense).
  - No ISC/MIT/OFL assets. Note: the pip dependencies, pygame-ce (LGPL) and numpy (BSD), are installed, not bundled.
- **Included suggestions:** a git safety net plus the GitHub remote, smooth curves, a Continue button with autosave, and undo delete.
- **GitHub:** `https://github.com/UncertaintyNihilityOmega/Ascensus-ad-Mathematica`, under the Unlicense.

## Spec

### W1. Repo and cleanup (done by Opus right after approval)
- Run `git init -b main` and add `LICENSE` (the Unlicense text).
- Update `.gitignore`: `.venv/`, `save/`, `__pycache__/`, `.pytest_cache/`, `*.lnk`, `prof.out`.
- Delete `prof.out`.
- **Remove `Play.bat`.** The shortcut launches the game. First-time setup moves to `tools/setup.bat`: create the venv, install, make the icon, make the shortcuts. The README documents it.
- Make a baseline commit (the current v2 state), check the remote with `git ls-remote`, add `origin` and push `main`. If the push needs credentials, the user is asked to sign in.
- Update CLAUDE.md:
  - Commit after each package, using the attribution lines.
  - Push only at batch end.
  - No two agents edit the same file. P17 (the rename) runs alone.
  - Licensing rule: CC0 assets only.

### W2. Bug fixes: see the table above (package P16)

### W3. Rename formulas → equations (package P17, runs alone)
- Rename the module `formulas.py` to `equations.py`, and rename:
  - `FormulaManager` → `EquationManager`
  - `FormulaEntry` → `EquationEntry`
  - `ParsedFormula` → `ParsedEquation`
  - `parse_formula` → `parse_equation`
  - `FormulaError` → `EquationError`
  - `MAX_FORMULA_LEN` → `MAX_EQUATION_LEN`
  - `game.formulas` → `game.equations`
  - the test files `test_formulas*` → `test_equations*`
  - every user-facing string ("Formula is empty" → "Equation is empty")
  - the README and plan references
- Save file: `save/formulas.json` becomes `save/equations.json`, with a one-time migration. If the new file is missing and the old one exists, read it, write the new one and leave the old one in place. `ASCENSUS_SAVE` stays.
- Done when `rg -i formula ascensus tests tools` only hits the migration code.

### W4. Icons, fonts and colors (package P18)
- `tools/fetch_icons.py` downloads the Kenney CC0 zips (Game Icons and Board Game Icons). It copies only the needed PNGs into `assets/icons/` plus Kenney's `License.txt` (CC0).
  - Needed icons: skull, reset/refresh, play, pause, trash, pencil/edit, plus, minus, save, fast-forward, gear, book, trophy/medal, padlock, arrow left/right, home, undo.
  - First verify the zip URLs on kenney.nl. Any missing icon stays drawn in code.
- `ui/icons.py`: `icon(name, size, color)` loads a white PNG, tints it (multiply with `BLEND_RGBA_MULT`) and caches it by (name, size, color). Replace the hand-drawn skull, reset, play, pause, medal and padlock icons and the sidebar's Edit/Del text with icons.
- **Palette (`CURVE_PALETTE_20`)**, shown as a 5×4 grid of rows, each color with a hover name tooltip:
  - **Row 1, neutrals:** White (255,255,255), Silver (192,198,212), Gray (128,134,150), Graphite (70,74,88), Black (0,0,0)
  - **Row 2, warm:** Red (255,59,48), Orange (255,149,0), Yellow (255,214,10), Lime (190,240,40), Green (52,199,89)
  - **Row 3, cool:** Teal (0,199,170), Cyan (0,220,255), Sky (90,170,255), Blue (40,90,255), Indigo (94,92,230)
  - **Row 4, purple to brown:** Violet (150,90,255), Purple (190,80,230), Magenta (255,45,200), Pink (255,120,170), Brown (165,110,60)
- **Custom row** under the grid: a hue strip (click or drag), a brightness strip, a preview swatch and a `#RRGGBB` box (an InputBox-style field; Enter applies).
- **Dark colors:** when relative luminance < 0.15, the curve's glow uses a light halo (200,205,220) at a low alpha, so black stays visible.

### W5. Controls, time speed and smooth curves (package P19)
- **New Settings tab "Controls":**
  - **Movement:** a choice between WASD and Mouse.
  - **Dash key:** a key-binding row, default **J**. Click it, press any key, Esc cancels. Stored as a pygame key name.
  - **Mouse dead zone:** in px.
- **Mouse mode:**
  - The player walks toward the cursor at `PLAYER_SPEED` and stops inside the dead zone (default: the player radius).
  - It does **not** move while the cursor is over the UI (sidebar, upgrade panel, input box, speed button) or the window is unfocused.
  - Facing = toward the cursor. **Right-click dashes**, and the dash key also works.
- **WASD mode:** unchanged, except the dash key replaces R.
- **Speed button:** semi-transparent (fill alpha 120), just right of the timer. The label is `1x`/`2x`/`3x` with a fast-forward icon. Clicking cycles 1→2→3→1.
  - Game dt = real dt × speed × (slow-mo if typing). It's split into substeps of ≤ 1/30 s so collisions don't tunnel.
  - Resets to 1x each run, is stored in saves and shown in Stats.
- **Smooth curves:** `render_curve` stamps a soft radial kernel instead of hard squares. The kernel is precomputed (7×7): full alpha within r ≤ 1.5 px, falling off to 0 at r = 4 px.
  - It's vectorized: one `np.maximum.at` per kernel offset over all points.
  - The grid step is 3 px and the kernel radius ≥ 2 px, so the beading disappears.
  - The dark-color halo from W4 hooks in here.

### W6. Saves, Continue and Undo (package P20)
- **`savegame.py`:** `snapshot(game) -> dict` and `restore(data) -> GameScene`. Saves carry `"version": 1`. A snapshot holds:
  - the player: position, HP, max HP, facing
  - the swarm arrays as lists, including the boss flags
  - the spawner accumulator, boss timer, game time and kills
  - the stats counters (bosses killed, damage dealt, dashes, equations cast)
  - the upgrades (XP, levels and the earned/spent totals) and the speed multiplier
  - the equations `[{text, enabled, color}]` and the variables `{name: {value, playing, dir}}`

  The RNG gets a new seed, and the profile is not part of a save. Loading a slot also makes its equations the current list.
- **Slots:** `save/slots/slot1..6.json` plus `slotN.png`.
  - The thumbnail is rendered at save time: the grid plus the active curves only (no enemies or UI), at the screen size, then smoothscaled to 320×180.
- **Saves page:** `saves_scene.py`, opened from the Main menu and from Pause.
  - A 3×2 grid of slot cards (2×3 when the window is narrower than 1000 px). Each card shows the thumbnail, the run time `mm:ss` at top-left (large, with a shadow), and the save date and kills small at the bottom-left.
  - Bottom of each card: **Save** (enabled only when opened from Pause; asks to confirm before overwriting) and **Delete** (a second click within 3 s confirms).
  - Clicking a filled thumbnail **loads** it. From Pause, a confirm step comes first ("Current run will be lost").
  - Empty slots show "Empty".
- **Continue:** an autosave goes to `save/slots/autosave.json` (+ png).
  - It's written on Main Menu from Pause, on window close mid-run, and every 60 s of play. It's deleted on game over.
  - When an autosave exists, the Main menu shows **"Continue (mm:ss)"** above Play.
- **Menus:**
  - Main: Continue?, Play, Saves, Settings, Library, Achievements, Quit, then the best-run line.
  - Pause: Resume, Stats, Saves, Settings, Library, Main Menu.
- **Undo delete:**
  - `EquationManager` keeps an undo stack of up to 10 deletions (entry plus index, also re-adding the entry's variables).
  - After Del, a toast says "Deleted eq4 · Undo" for 5 s; clicking Undo restores the equation.
  - **Ctrl+Z** also restores it, unless a text field is focused.

### W7. Final QA (package P21)
- **Overflow audit test:** render every page (menu, game with 12 equations and 6 variables, pause, stats, saves, settings with each tab, library with each tab, achievements) at 800×600, 800×800 and 1920×1080. `draw_text` counts every time text needed truncation below `min_size`, and the test asserts that count is 0.
- **Perf:** re-measure and fix, or document the gate at both sizes.
- **README v3:** features, controls (both movement modes), setup via `tools/setup.bat`, the Unlicense, and third-party notes (Kenney CC0 icons; pygame-ce and numpy installed via pip).
- Push to GitHub.

## Reused existing code
- `ui/widgets.py` (`Button`, `Tabs`, `NumberField`, `ScrollArea`, `draw_text`): extend with max_w/wrap, a key-binding field, and a hue strip.
- `settings.py` registry: add the Controls tab, a `key` kind and the `choice` Movement row.
- `display.py`: add the minimum window size.
- `curvefield.render_curve`: replace only the stamping.
- `upgrade_panel.on_resize` / `InputBox.on_resize`: add the shared layout rule.
- `scenes.open_page` and `_return_here`: add Saves. The bug #1 fix covers all pages.
- The `tools/smoke.py` phases: extend for saves, the speed button, mouse mode and the picker.

## Verification
- pytest, including the new regression tests for each bug: scene switch, picker over variables, settings focus per tab, layout no-overlap, duplicate defs, overflow audit.
- `tools/smoke.py` at 1280×720 and 1920×1080.
- Opus renders screenshots at 800×800 and 1920×1080 for all pages and reviews them (as done in this session).
- Then the user playtests: pause → Settings → Back, color change, small window, Settings typing, mouse mode + right-click dash, J dash, speed button, saves/Continue, undo.
