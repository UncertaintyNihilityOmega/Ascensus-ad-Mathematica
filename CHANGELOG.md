# Changelog

## 1.0.0 (2026-10-02)

First public release.

### Added
- Export and Import on every save slot: a run travels as one `.ascensus` file and can go into any slot.
- 20 new achievements (40 in total), including equation shapes recognised in any rearrangement and with any
  variable name: Sakuna, Cosmic, Lily, Cross0, Cross2, Aliens, Circular, Fog, Love is Endless, Heartbeat,
  Four Leaf, Infinity, and Ocean (replaces The Tan Monster).
- Mouse editing in the equation box: click to place the cursor, drag or Shift+click to select,
  double-click to select a word.
- `pyproject.toml` packaging with an `ascensus` command, GitHub Actions tests on Windows and Linux.

### Changed
- Play always starts a fresh run with no equations; equations live in runs, the autosave and save slots.
- Curves are drawn as continuous lines (grid cells joined marching-squares style) instead of dots.
- The windowed mode fits the screen, title bar included, and opens centred.
- 3x game speed costs no more than 1x: animated curves rebuild once per frame on the wall clock.
- Project layout: `core/`, `game/`, `scenes/`, `ui/`, `data/` and `assets/` inside the package.

### Fixed
- A real curve point right next to a grid node could be dropped by the pole filter, leaving gaps.
- The window opened taller than a 1366x768 screen, hiding the title bar.

## 0.3 (development)
Bug-fix round (pause pages flashing, colour picker, text overflow, settings typing, letter spacing, layout),
Kenney CC0 icons, the 20-colour palette and custom colours, controls (WASD or mouse, rebindable dash),
the game speed button, save slots, Continue and undo.

## 0.2 (development)
Full screen and resizable window, parser v2 with variables and named equations, collisions, dash, regen,
bosses, XP and upgrades, the sidebar for 200 equations and variables, Settings, Library, Achievements.

## 0.1 (development)
The prototype: the curve engine with its pole filter, the equation parser, enemies, pulses and the sidebar.
