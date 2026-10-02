# Ascensus ad Mathematica

**Next-session prompt** (paste into a fresh Sonnet session, after `/clear`):
> Continue Ascensus ad Mathematica. Read CLAUDE.md, plan/STATUS.md and the next package in plan/PACKAGES.md (plus only the sections of plan/DESIGN.md and plan/ARCHITECTURE.md that package references). Implement that one package, run its checks, update plan/STATUS.md, then stop. No subagents. Report in three lines.

## Goal
This is a Python prototype of a Magic Survival-style survival game. The player's only weapons are **math curves they type**. Each formula is drawn across the window, with the player at (0,0) in the middle, and every curve pulses damage onto the enemies it touches.

## Scope: Pilot then Core
- **Pilot = P1 to P3**: the parser and curve engine, the game shell, and formula combat. **Stop here and have the user playtest.**
- **Core = P4 to P5**: the full sidebar (drag, edit, toggle, persistence), then tuning and polish from the playtest notes.
- Out of scope: XP and levels, upgrades, sound, multiple enemy types, packaging into an .exe.

## Decisions (user-approved 2026-10-02)
| Topic | Decision |
|---|---|
| Movement | WASD/arrows move the player. The camera stays on the player, so curves are screen-anchored. |
| Typing | Enter or a click focuses the input. While it's focused, the game runs in **slow-mo (0.2×)**. Enter casts, Esc cancels. |
| Damage | Each active curve **pulses every 1 s**. Damage per pulse = budget ÷ the curve's on-screen length, so long or dense curves are weak and short precise ones hit hard. |
| Limits | At most 4 *active* formulas: the top 4 enabled rows in the sidebar. Sidebar holds at most 12 rows. |
| Progression | None. Survive as long as possible. Enemies get slowly tougher. |
| Extras | Faint grid and axes, a time variable `t`, an on/off toggle per row, formulas saved between runs (JSON). |
| Tech | Python 3.14 (`py`), **pygame-ce 2.5.7** + **numpy 2.x**, pytest. Verified installable 2026-10-02. |
| Curves | Every formula is turned into an implicit F(x,y,t)=0. Root-finding runs on a 3 px grid with bisection and a pole filter (prototype verified, see ARCHITECTURE §3). |

## Where things live
- Code: `ascensus/` (package), tests: `tests/`, headless smoke run: `tools/smoke.py`
- Plan: `plan/` (this folder). Progress log: `plan/STATUS.md`
- Save file: `save/formulas.json` (git-ignored; override with env var `ASCENSUS_SAVE`)

## Commands (PowerShell, project root)
```
py -3.14 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt -r requirements-dev.txt
.venv\Scripts\python -m pytest -q
.venv\Scripts\python tools\smoke.py
.venv\Scripts\python -m ascensus        # play
```

## Size estimate
About 12 source files and roughly 2,000 lines of Python, split into 5 packages with one fresh Sonnet session each. Opus is only needed if a hard bug appears.
