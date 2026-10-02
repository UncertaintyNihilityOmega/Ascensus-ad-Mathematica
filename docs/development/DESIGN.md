# Game Design Spec

All numbers below are starting values. They live in `ascensus/config.py`; never hard-code them elsewhere.

## 1. Window and coordinates
- Window: 1280×720, 60 FPS, title "Ascensus ad Mathematica".
- **Math space**: the player is always at the window center = math (0,0). `UNIT_PX = 50`, so the visible area is x ∈ [-12.8, 12.8] and y ∈ [-7.2, 7.2]. y points **up**.
  - math→screen: `sx = W/2 + x*UNIT_PX`, `sy = H/2 - y*UNIT_PX`
- **World space** (pixels) holds the player and enemies. Camera: `screen = world - player_pos + (W/2, H/2)`.
- Curves are evaluated **only inside the window**. They are cached and rebuilt only when the formula changes (or periodically if it uses `t`). Moving never forces a rebuild.

## 2. Scenes
1. **Main menu**: the title "Ascensus ad Mathematica", a subtitle ("Survive with equations"), **Play** and **Quit** buttons, and a 4-line controls summary. Optional flourish: an animated `y = sin(x + t)` curve behind the title (reuses the curve engine).
2. **Game**: see below. Esc (when not typing) opens a **pause overlay** with Resume and Main Menu buttons. Esc again resumes.
3. **Game over**: "You survived mm:ss", kills, and **Retry** and **Main Menu** buttons.

## 3. Controls (game scene)
| Input | Effect |
|---|---|
| WASD / arrow keys | Move (speed 220 px/s, diagonal normalized). Disabled while typing. |
| Enter (not typing) or click the input box | Focus the input. Time scale drops to `TYPING_TIME_SCALE = 0.2`. |
| Enter (typing) | Parse the formula. If it's valid, add it to the sidebar (or replace the row being edited), clear the box, unfocus. If it's invalid, show a red error above the box for 3 s and keep the text. |
| Esc (typing) | Cancel: unfocus and exit edit mode. Text is kept unless in edit mode. |
| Left/Right/Home/End/Backspace/Delete | Text-cursor editing in the input |
| G | Toggle the grid and axes overlay |
| F3 | Toggle the FPS / debug readout |
| Mouse | Sidebar interactions (see §6). Dragging a row also triggers slow-mo. |

## 4. Player and enemies
- Player: a white circle with a radius of 14 and a soft cyan ring. 100 HP, no regen. After a hit, the player gets 0.6 s of invulnerability and blinks.
- Enemy (a single type): a red circle with a radius of 12 that chases the player directly. It darkens as HP drops and flashes white for 0.1 s when hit.
- Spawning: enemies appear at a random angle, at distance `hypot(W,H)/2 + 40` from the player (just off-screen). At most 250 alive at once.
- Contact: on overlap, the player takes the touching enemy's damage, then i-frames apply.
- **Difficulty** (`m` = game minutes elapsed):
  - `hp     = 20 * (1 + 0.15*m)`
  - `damage = 8  * (1 + 0.10*m)`
  - `speed  = min(70 * (1 + 0.03*m), 140)` px/s
  - `spawn_interval = max(0.15, 1.0 / (1 + 0.35*m))` s (spawn 1 enemy per interval)
- The game clock counts **scaled** time, so slow-mo also slows the clock.

## 5. Formulas and combat
- **Accepted syntax**: numbers, `x y t pi e`, `+ - * / ^ %`, parentheses, and implicit multiplication (`2x`, `3sin(x)`, `(x+1)(x-1)`, `xy`, `2pi`).
  - Functions (must use parentheses): `sin cos tan asin acos atan sinh cosh tanh sqrt cbrt abs exp ln log sec csc cot`
  - Also accepted: `**`, `×`, `÷`, `−`, `π`, and `√(`. Lowercase is applied automatically. Max 80 characters.
- **Meaning**:
  - Without `=` and without `y`, a formula means `y = expr` (so `x^2` means y=x², and `sin(x)` means y=sin x).
  - Without `=` but with `y`, it means `expr = 0`.
  - With one `=`, it means `lhs - rhs = 0` (`x = 2`, `1 = x^2 + y^2`, `tan(sqrt(x^2+y^2)) = y/x`).
  - The formula must contain `x` or `y`. More than one `=` is an error.
- Must-pass examples: `x^2`, `x^3`, `x = 2`, `x = -4`, `1 = x^2 + y^2`, `sin(x)`, `cos(x)`, `x^(1/2)`, `tan(sqrt(x^2 + y^2)) = y / x`, `y = 2sin(x + t)`, `x^2 + y^2 = (t % 5)^2`.
- **Active set**: the first `MAX_ACTIVE = 4` *enabled* rows, in sidebar order. Other enabled rows are "queued", drawn very faint, and do no damage. Reordering by drag decides which ones fire.
- **Pulse**: each active formula has its own timer (`PULSE_PERIOD = 1.0` s; a new formula's first pulse comes after 0.3 s). On a pulse, every enemy in the curve's hit mask takes
  `dmg = clamp(DAMAGE_BUDGET / max(L, L_MIN), DMG_MIN, DMG_MAX)` with `DAMAGE_BUDGET=200, L_MIN=4, DMG_MIN=1, DMG_MAX=50`.
  Here `L` is the visible curve length in math units. Reference values: `x=2` (L≈14.4) does ~14, the unit circle ~32, `sin(x)` ~6, and the tan monster ~2.
- **Hit thickness**: about ±16 px around the curve (the coarse hit mask, see ARCHITECTURE §3).
- **Visuals**: each formula gets a neon color from an 8-color palette (the first color not already in use). Idle curve alpha is 90; on a pulse it flashes to 255 and fades back over 0.25 s. Queued formulas are drawn at alpha 30, disabled ones aren't drawn.
- `t` formulas: rebuilt at most 10×/s, at a coarser 5 px grid, with at most one rebuild per frame (round-robin).
- If a formula yields no visible points, it's still added, and its row shows "(off-screen)".

## 6. Sidebar (left, collapsible, semi-transparent)
- Panel: x=0, width 300, full height, color (15,18,30) at alpha 170. Curves stay visible beneath it.
- Header: "FORMULAS", an "active n/4" readout, and a collapse button `<`. When collapsed, only a small `>` tab (30×60, left edge, y=80) is shown, and clicking it reopens the panel.
- Rows: 44 px high, max 12 rows (no scrolling needed). Left to right, each row has:
  - a drag handle (3 short lines)
  - a 10 px color swatch
  - the formula text, truncated with "..."
  - an on/off switch (a small pill with a knob, drawn with primitives)
  - an **Edit** text button
  - a **Del** text button in red
- States: hover = lighter background, button hover = highlight. A disabled row is dimmed with an "off" tag, and a queued row is dimmed with a "queued" tag.
- **Drag**: press on a row (not on a button), then move more than 4 px while holding to start a drag. The row follows the mouse with an insertion gap, and release reorders it. A press-and-release without moving does nothing.
- **Edit**: loads the text into the input box, focuses it, and shows "Editing #n" over the box. Enter replaces that row in place, and Esc cancels.
- **Del**: removes the row immediately (prototype; no confirm).
- Adding a 13th formula shows the error "Sidebar full (12) - delete one first".
- Every change (add, edit, delete, move, toggle) saves to `save/formulas.json`. The list is loaded when a game starts.

## 7. HUD and look
- Draw order: background → grid/axes → curves → enemies → player → HUD → sidebar → input box → overlays.
- Background: dark navy (10,12,24), plus a **world-anchored** dot pattern (a 64 px tile) so movement is visible.
- Grid (player-anchored, cached): lines every 1 unit at alpha 22, axes at alpha 70, small tick numbers every 2 units.
- HUD: the timer `mm:ss` top-center (large), an HP bar top-right with kills below it, and FPS when F3 is on.
- Input box: a 560×42 rect, centered horizontally, bottom at H-20, with a dark fill and a 2 px border that brightens when focused.
  - When empty, it shows the placeholder "Type an equation, e.g. y = sin(x)   [Enter]", and a blinking cursor when focused.
  - The error text is red, 18 px above the box.
- Fonts: `pygame.font.Font(None, size)` only, because the default font lacks many glyphs. Draw icons with primitives, not Unicode.
