"""Scenes: Menu, Game (with pause overlay) and GameOver."""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pygame

from . import config, controls, view
from .curvefield import build_curve, render_curve
from .enemies import Spawner, Swarm
from .equations import USE_CONFIG, EquationManager, resolve_save_path
from .mathparse import EquationError, parse_equation
from .achievements import AchievementTracker
from .player import Player
from .profile import Profile, get_profile
from .savegame import SlotStore
from .ui import icons
from .ui.inputbox import InputBox
from .ui.sidebar import Sidebar
from .ui.speed_button import SpeedButton, next_speed
from .ui.undo_toast import UndoToast
from .ui.upgrade_panel import UpgradePanel
from .layout import game_layout
from .ui.widgets import Button, draw_text, get_font
from .upgrades import Upgrades

QUIT = "quit"


def fmt_time(seconds: float) -> str:
    """mm:ss."""
    s = int(seconds)
    return f"{s // 60:02d}:{s % 60:02d}"


def _button(cx: int, cy: int, label: str) -> Button:
    w, h = config.BUTTON_SIZE
    return Button(pygame.Rect(cx - w // 2, cy - h // 2, w, h), label)


def button_stack(n: int, head: int, foot: int = 0) -> tuple[int, list[pygame.Rect]]:
    """Rects of `n` centred menu buttons under a `head` px title block, with `foot` px left below them.

    The whole block is centred vertically. In a short window the button height and gap shrink (down to
    24 px buttons) so everything still fits. Returns (top of the block, button rects).
    """
    m = 12
    full_w, full_h = config.BUTTON_SIZE
    pitch = min(full_h + 12, max((view.H - 2 * m - head - foot) // max(n, 1), 24))
    gap = 12 if pitch == full_h + 12 else max(int(pitch * 0.18), 4)
    bh = pitch - gap
    total = head + n * pitch - gap + foot
    top = max((view.H - total) // 2, m)
    w = min(full_w, view.W - 20)
    return top, [pygame.Rect(view.W // 2 - w // 2, top + head + i * pitch, w, bh) for i in range(n)]


class Scene:
    """Base scene. Set `next_scene` (a Scene or QUIT) to ask the main loop to switch."""

    def __init__(self) -> None:
        self.next_scene: Scene | str | None = None
        self.fps = 0.0

    def handle_event(self, e: pygame.event.Event) -> None:
        pass

    def on_resize(self) -> None:
        """The window size changed (view.W / view.H are already updated): re-lay-out."""

    def update(self, dt: float) -> None:
        pass

    def draw(self, screen: pygame.Surface) -> None:
        pass


def open_page(name: str, back, game=None) -> "Scene | None":
    """Build the Settings / Library / Achievements / Saves page (imported lazily); None if it does not exist.

    `back` is a zero-argument callable returning the Scene the page's Back button leads to. `game` is only
    used by the Saves page: the paused GameScene it can save (None from the main menu).
    """
    try:
        if name == "saves":
            from .saves_scene import SavesScene
            return SavesScene(game, back)
        if name == "settings":
            from .settings_scene import SettingsScene
            return SettingsScene(back)
        if name == "library":
            from .library import LibraryScene
            return LibraryScene(back)
        if name == "achievements":
            from .achievements_scene import AchievementsScene
            return AchievementsScene(back)
    except ImportError:
        return None
    return None


class MenuScene(Scene):
    """Title, [Continue (mm:ss)] / Play / Saves / Settings / Library / Achievements / Quit and the best run."""

    LABELS = ("Play", "Saves", "Settings", "Library", "Achievements", "Quit")

    def __init__(self, store: SlotStore | None = None) -> None:
        super().__init__()
        self.store = store if store is not None else SlotStore()
        info = self.store.autosave_info()
        self.continue_time: float | None = info.game_t if info is not None else None
        self.play = self.quit = _button(0, 0, "")
        self.buttons: dict[str, Button] = {}
        self.top = 0
        self.on_resize()
        self.t = 0.0
        self.rebuild_timer = config.MENU_CURVE_REBUILD       # build on the first update
        self.curve_func = parse_equation(config.MENU_CURVE).func
        self.curve_surf: pygame.Surface | None = None

    def _names(self) -> list[str]:
        return (["Continue"] if self.continue_time is not None else []) + list(self.LABELS)

    def on_resize(self) -> None:
        names = self._names()
        self.top, rects = button_stack(len(names), 130, 44)
        self.buttons = {}
        for name, rect in zip(names, rects):
            label = f"Continue ({fmt_time(self.continue_time)})" if name == "Continue" else name
            self.buttons[name] = Button(rect, label)
        self.play, self.quit = self.buttons["Play"], self.buttons["Quit"]
        self.rebuild_timer = config.MENU_CURVE_REBUILD       # redraw the curve at the new size

    def update(self, dt: float) -> None:
        """Animate the background curve (rebuilt at ~10 Hz on the coarse grid)."""
        self.t += dt
        self.rebuild_timer += dt
        if self.rebuild_timer >= config.MENU_CURVE_REBUILD:
            self.rebuild_timer = 0.0
            curve = build_curve(self.curve_func, self.t, config.GRID_STEP_T)
            self.curve_surf = render_curve(curve.points, config.ACCENT_COLOR)
            self.curve_surf.set_alpha(config.MENU_CURVE_ALPHA)

    def continue_game(self) -> None:
        """Load the autosave into a GameScene; an unreadable autosave is deleted and the button disappears."""
        from .savegame import restore
        data = self.store.load_autosave()
        try:
            if data is None:
                raise ValueError("no autosave")
            self.next_scene = restore(data)
        except ValueError:
            self.store.delete_autosave()
            self.continue_time = None
            self.on_resize()

    def handle_event(self, e: pygame.event.Event) -> None:
        if self.play.handle_event(e) or (e.type == pygame.KEYDOWN and e.key == pygame.K_RETURN):
            self.next_scene = GameScene()
        elif "Continue" in self.buttons and self.buttons["Continue"].handle_event(e):
            self.continue_game()
        elif self.quit.handle_event(e):
            self.next_scene = QUIT
        else:
            for name in ("Saves", "Settings", "Library", "Achievements"):
                if self.buttons[name].handle_event(e):
                    self.next_scene = open_page(name.lower(), lambda: MenuScene(self.store))
                    break

    def draw(self, screen: pygame.Surface) -> None:
        screen.fill(config.BG_COLOR)
        if self.curve_surf is not None:
            screen.blit(self.curve_surf, (0, 0))
        cx, wmax = view.W // 2, view.W - 40
        draw_text(screen, config.TITLE, config.TITLE_FONT, config.ACCENT_COLOR, (cx, self.top + 36), "center",
                  max_w=wmax, min_size=28)
        draw_text(screen, "Survive with equations", config.SUBTITLE_FONT,
                  config.TEXT_COLOR, (cx, self.top + 100), "center", max_w=wmax, min_size=18)
        for b in self.buttons.values():
            b.draw(screen)
        last = self.quit.rect.bottom
        draw_text(screen, get_profile().best_text(), config.BODY_FONT, config.DIM_TEXT_COLOR,
                  (cx, last + 24), "center", max_w=wmax, min_size=14)


class GameOverScene(Scene):
    """Survival time, kills, Retry / Main Menu."""

    def __init__(self, survived: float, kills: int) -> None:
        super().__init__()
        self.survived = survived
        self.kills = kills
        self.retry = self.menu = _button(0, 0, "")
        self.on_resize()

    def on_resize(self) -> None:
        cx, cy = view.W // 2, view.H // 2
        self.retry = _button(cx, cy + 40, "Retry")
        self.menu = _button(cx, cy + 110, "Main Menu")

    def handle_event(self, e: pygame.event.Event) -> None:
        if self.retry.handle_event(e):
            self.next_scene = GameScene()
        elif self.menu.handle_event(e):
            self.next_scene = MenuScene()

    def draw(self, screen: pygame.Surface) -> None:
        screen.fill(config.BG_COLOR)
        cx, cy = view.W // 2, view.H // 2
        draw_text(screen, "You died", config.TITLE_FONT, config.DANGER_COLOR, (cx, cy - 190), "center")
        draw_text(screen, f"You survived {fmt_time(self.survived)}", config.SUBTITLE_FONT + 10,
                  config.TEXT_COLOR, (cx, cy - 90), "center")
        draw_text(screen, f"Kills: {self.kills}", config.SUBTITLE_FONT,
                  config.TEXT_COLOR, (cx, cy - 40), "center")
        self.retry.draw(screen)
        self.menu.draw(screen)


def _mix(color: tuple[int, int, int], alpha: int) -> tuple[int, int, int]:
    """`color` at `alpha` over the background colour, as an opaque colour (cheap to draw)."""
    k = alpha / 255
    return tuple(int(c * k + bg * (1 - k)) for c, bg in zip(color, config.BG_COLOR))


def make_dot_surface() -> pygame.Surface:
    """Dot pattern on a colour-keyed (RLE) surface: blitting it only touches the dots, not every pixel."""
    t, r, key = config.DOT_TILE, config.DOT_RADIUS, (255, 0, 255)
    surf = pygame.Surface((view.W + t, view.H + t))
    surf.fill(key)
    for x in range(0, view.W + t, t):
        for y in range(0, view.H + t, t):
            surf.fill(config.DOT_COLOR, (x - r, y - r, 2 * r, 2 * r))
    surf.set_colorkey(key, pygame.RLEACCEL)
    return surf


def make_grid() -> tuple[list[tuple[tuple[int, int, int], tuple[int, int], tuple[int, int]]],
                         list[tuple[pygame.Surface, tuple[int, int]]]]:
    """Player-anchored grid: opaque pre-mixed line segments (colour, p0, p1) and tick-number images."""
    W, H = view.W, view.H
    cx, cy = view.center()
    step = int(config.UNIT_PX)
    line, axis = _mix(config.GRID_COLOR, config.GRID_ALPHA), _mix(config.GRID_COLOR, config.AXES_ALPHA)
    lines = [(line, (x, 0), (x, H - 1)) for x in range(cx % step, W, step)]
    lines += [(line, (0, y), (W - 1, y)) for y in range(cy % step, H, step)]
    lines += [(axis, (cx, 0), (cx, H - 1)), (axis, (0, cy), (W - 1, cy))]
    font = get_font(config.GRID_TICK_FONT)
    every = config.GRID_TICK_EVERY
    labels: list[tuple[pygame.Surface, tuple[int, int]]] = []
    for horizontal, extent in ((True, W), (False, H)):
        for k in range(every, int(extent / 2 / config.UNIT_PX) + 1, every):
            for sign in (1, -1):
                img = font.render(str(sign * k), True, config.GRID_TICK_COLOR)
                img.set_alpha(config.GRID_TICK_ALPHA)
                if horizontal:
                    pos = img.get_rect(midtop=(cx + sign * k * step, cy + 4)).topleft
                else:
                    pos = img.get_rect(midright=(cx - 5, cy - sign * k * step)).topleft
                labels.append((img, pos))
    return lines, labels


class GameScene(Scene):
    """The survival game: player, swarm, HUD and pause overlay."""

    def __init__(self, seed: int | None = None, save_path: Path | None | str = USE_CONFIG,
                 profile: Profile | None = None, slots: SlotStore | None = None) -> None:
        super().__init__()
        self.slots = slots if slots is not None else SlotStore()      # where the autosave goes
        self._autosave_t = 0.0                       # seconds of play since the last autosave
        self.undo_toast = UndoToast()
        self.profile = profile if profile is not None else get_profile()
        self.tracker: AchievementTracker | None = AchievementTracker(self.profile)
        self.toast: tuple[str, float] | None = None   # (text, seconds left) of the shown unlock toast
        self.rng = np.random.default_rng(seed)
        self.player = Player()
        self.swarm = Swarm(self.rng)
        self.spawner = Spawner()
        self.equations = EquationManager(resolve_save_path(save_path))
        self.equations.load()
        self.equations.store.listener = self.emit     # var_created / var_play -> achievements
        self.input = InputBox()
        self.sidebar = Sidebar(self.equations, self.input)
        self.sidebar.on_delete = self._equation_deleted
        self.game_t = 0.0
        self.kills = 0
        self.boss_banner = 0.0           # seconds left on the "BOSS INCOMING" banner
        self.paused = False
        self.show_grid = config.SHOW_GRID_DEFAULT
        self.show_fps = config.SHOW_FPS_DEFAULT
        self.equations_cast = 0                      # stats counter (successful submits)
        self._recorded = False                       # the run was added to the profile
        self._seen = self._page_sig()                # display/default settings the layout matches
        self.upgrades = Upgrades()                   # per-run XP and stats
        self._auto_prev = False                      # to emit auto_on when Auto is switched on
        self.upgrade_panel = UpgradePanel(self.upgrades, self.buy)
        self.speed = 1                               # game speed 1x/2x/3x (per run; the speed button cycles it)
        self.speed_button = SpeedButton()
        self._layout_collapsed = False
        self.layout_bottom()
        self.direction_override: tuple[float, float] | None = None   # tests/smoke only
        self.grid_lines, self.grid_labels = make_grid()
        self.dots = make_dot_surface()
        self.resume_btn = self.menu_btn = self.stats_btn = self.settings_btn = self.library_btn = _button(0, 0, "")
        self.saves_btn = _button(0, 0, "")
        self.pause_top = 0
        self._layout_pause()

    @property
    def bosses_killed(self) -> int:
        """Stats: bosses killed this run (counted by the swarm)."""
        return self.swarm.bosses_killed

    @property
    def damage_dealt(self) -> float:
        """Stats: total hp removed by equation pulses this run."""
        return self.swarm.damage_dealt

    def _layout_pause(self) -> None:
        names = ("Resume", "Stats", "Saves", "Settings", "Library", "Main Menu")
        self.pause_top, rects = button_stack(len(names), 70)
        (self.resume_btn, self.stats_btn, self.saves_btn, self.settings_btn, self.library_btn,
         self.menu_btn) = (Button(r, n) for r, n in zip(rects, names))

    @staticmethod
    def _page_sig() -> tuple:
        """What the layout depends on: window size, zoom, curve quality (and the HUD defaults)."""
        return (view.W, view.H, config.UNIT_PX, config.GRID_STEP, config.SHOW_FPS_DEFAULT, config.SHOW_GRID_DEFAULT)

    def _return_here(self) -> "GameScene":
        """`back` for pages opened from pause: re-lay-out if the settings changed meanwhile."""
        old, new = self._seen, self._page_sig()
        if old[:4] != new[:4]:
            self.on_resize()
        if old[4] != new[4]:
            self.show_fps = config.SHOW_FPS_DEFAULT
        if old[5] != new[5]:
            self.show_grid = config.SHOW_GRID_DEFAULT
        self._seen = new
        return self

    def finish_run(self) -> None:
        """Add this run to the profile's bests once (game over, or quitting to the menu)."""
        if not self._recorded:
            self._recorded = True
            self.profile.record_run(self.game_t, self.kills)

    def layout_bottom(self) -> None:
        """Place the input box and the upgrades panel so they never overlap (see layout.game_layout)."""
        sb = self.sidebar
        left = sb.tab_rect.right if sb.collapsed else sb.panel_rect.right
        rect, bottom = game_layout(left, view.W, view.H)
        self.input.rect = rect
        self.upgrade_panel.on_resize(bottom)
        self._layout_collapsed = sb.collapsed

    def on_resize(self) -> None:
        """Re-lay-out widgets, rebuild background surfaces and recompute every curve."""
        self.sidebar.on_resize()
        self.speed_button.on_resize()
        self.undo_toast.on_resize()
        self.layout_bottom()
        self.equations.on_resize()
        self.grid_lines, self.grid_labels = make_grid()
        self.dots = make_dot_surface()
        self._layout_pause()
        self._seen = self._page_sig()

    def time_scale(self) -> float:
        """Slow-mo while typing or dragging a sidebar row (the speed button's multiplier is separate)."""
        slow = self.input.focused or self.sidebar.dragging or self.sidebar.value_focused
        return config.TYPING_TIME_SCALE if slow else 1.0

    def _move_input(self) -> tuple[tuple[float, float], tuple[float, float] | None]:
        """(walk direction, facing override) from the keys or the mouse (see controls.read_movement)."""
        if self.direction_override is not None:
            return self.direction_override, None
        return controls.read_movement(self)

    def _direction(self) -> tuple[float, float]:
        return self._move_input()[0]

    def handle_event(self, e: pygame.event.Event) -> None:
        if self.paused:
            if self.resume_btn.handle_event(e) or (
                    e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                self.paused = False
            elif self.stats_btn.handle_event(e):
                from .pages import StatsScene
                self.next_scene = StatsScene(self, self._return_here)
            elif self.saves_btn.handle_event(e):
                self.next_scene = open_page("saves", self._return_here, game=self)
            elif self.settings_btn.handle_event(e):
                self.next_scene = open_page("settings", self._return_here)
            elif self.library_btn.handle_event(e):
                self.next_scene = open_page("library", self._return_here)
            elif self.menu_btn.handle_event(e):
                self.finish_run()
                self.autosave()
                self.next_scene = MenuScene(self.slots)
            return
        if self.sidebar.picker_idx is not None:       # the colour popup is modal
            self.sidebar.handle_event(e)
            return
        if self.undo_toast.handle_event(e):
            self.undo()
            return
        if (e.type == pygame.KEYDOWN and e.key == pygame.K_z and e.mod & pygame.KMOD_CTRL
                and not (self.input.focused or self.sidebar.value_focused)):
            self.undo()
            return
        if self.speed_button.handle_event(e):
            self.speed = next_speed(self.speed)
            return
        if self.upgrade_panel.handle_event(e) or self.sidebar.handle_event(e):
            return
        was_focused = self.input.focused
        result = self.input.handle_event(e)
        if result == "submit":
            self._submit()
        if was_focused or self.input.focused:
            return                          # typing owns the keyboard (also the focusing Enter)
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_ESCAPE:
                self.paused = True
            elif controls.is_dash_event(e):
                self._dash(e)
            elif e.key == pygame.K_g:
                self.show_grid = not self.show_grid
            elif e.key == pygame.K_F3:
                self.show_fps = not self.show_fps
        elif controls.is_dash_event(e):              # right-click in Mouse mode
            self._dash(e)

    # --- undo delete and autosave ---------------------------------------------------------------------
    def _equation_deleted(self, entry) -> None:
        """The sidebar's Del removed `entry`: offer 'Deleted <name> - Undo' for a few seconds."""
        self.undo_toast.show(entry.parsed.name or entry.text)

    def undo(self) -> bool:
        """Bring back the last deleted equation (Ctrl+Z or the toast); True when one came back."""
        entry = self.equations.undo_delete()
        self.undo_toast.hide()
        if entry is None:
            return False
        ei = self.input.edit_index
        if ei is not None and self.equations.entries.index(entry) <= ei:
            self.input.edit_index = ei + 1           # the equation being edited moved down one row
        return True

    def autosave(self) -> bool:
        """Write the autosave (Continue loads it); nothing for a dead or brand-new run."""
        self._autosave_t = 0.0
        if not self.player.alive or self.game_t < config.AUTOSAVE_MIN_TIME:
            return False
        return self.slots.autosave(self)

    def _dash(self, e: pygame.event.Event) -> None:
        """Dash on the dash key, or on a right-click (toward the cursor, unless it is over the UI)."""
        if e.type == pygame.MOUSEBUTTONDOWN:
            if controls.mouse_over_ui(self, e.pos):
                return
            self.player.face(controls.aim(e.pos))
        if self.player.start_dash():
            self.emit("dash")

    def buy(self, stat: str) -> bool:
        """Buy one level of `stat`; Max HP also raises the player's cap and heals."""
        if not self.upgrades.buy(stat):
            return False
        if stat == "max_hp":
            self.player.raise_max_hp(config.UPG_HP_STEP)
        self.emit("upgrade", stat=stat)
        return True

    def emit(self, event: str, **data) -> None:
        """Forward a game event to the achievement tracker (no-op without one)."""
        if self.tracker is not None:
            self.tracker.on(event, **data)

    def _update_toast(self, real_dt: float) -> None:
        """Count down the shown unlock toast and start the next queued one (real time, also while paused)."""
        if self.toast is not None:
            text, left = self.toast
            left -= real_dt
            self.toast = (text, left) if left > 0 else None
        if self.toast is None and self.tracker is not None:
            ach = self.tracker.pop_toast()
            if ach is not None:
                self.toast = (self.tracker.toast_text(ach), config.TOAST_TIME)

    def _draw_toast(self, screen: pygame.Surface) -> None:
        """Gold-bordered 'Achievement unlocked: ...' box below the timer."""
        if self.toast is None:
            return
        text, pad = self.toast[0], config.TOAST_PAD
        w, h = get_font(config.TOAST_FONT).size(text)
        box = pygame.Rect(0, 0, w + 2 * pad, h + 2 * pad)
        box.midtop = (view.W // 2, config.HUD_MARGIN + config.HUD_TIMER_FONT + config.TOAST_GAP)
        pygame.draw.rect(screen, config.TOAST_FILL, box, border_radius=8)
        pygame.draw.rect(screen, config.TOAST_BORDER, box, width=2, border_radius=8)
        draw_text(screen, text, config.TOAST_FONT, config.TOAST_BORDER, box.center, "center")

    def _submit(self) -> None:
        """Add the typed equation (or replace the one being edited); show errors in the box."""
        try:
            if self.input.edit_index is None:
                parsed = self.equations.add(self.input.text).parsed
            else:
                self.equations.replace(self.input.edit_index, self.input.text)
                parsed = self.equations.entries[self.input.edit_index].parsed
        except EquationError as err:
            self.input.show_error(str(err))
            return
        self.input.clear()
        self.equations_cast += 1
        self.emit("cast", parsed=parsed)

    def update(self, real_dt: float) -> None:
        self.input.update(real_dt)
        self.sidebar.update(real_dt)
        if self.sidebar.collapsed != self._layout_collapsed:       # collapsing frees / uses space
            self.layout_bottom()
        self._update_toast(real_dt)
        self.undo_toast.update(real_dt)
        if self.paused:
            return
        self._autosave_t += real_dt
        if self._autosave_t >= config.AUTOSAVE_PERIOD:
            self.autosave()
        self.boss_banner = max(0.0, self.boss_banner - real_dt)
        direction, face = self._move_input()
        total = real_dt * self.speed * self.time_scale()
        n = min(max(1, math.ceil(total / config.SIM_MAX_SUBSTEP - 1e-9)), config.SIM_MAX_SUBSTEPS)
        for _ in range(n):                   # substeps <= SIM_MAX_SUBSTEP so fast play does not tunnel
            self._sim_step(total / n, direction, face)
            if not self.player.alive:
                break

    def _sim_step(self, dt: float, direction: tuple[float, float],
                  face: tuple[float, float] | None) -> None:
        """Advance the simulation by `dt` game seconds."""
        self.game_t += dt
        self.player.update(dt, direction, face)
        # contact uses last frame's resolved positions; knockback only when the hit lands
        if self.player.take_damage(self.swarm.contact_damage(self.player.pos, config.PLAYER_RADIUS)):
            self.swarm.knockback(self.player.pos, config.PLAYER_RADIUS)
        for _ in range(self.spawner.update(dt, self.game_t)):
            self.swarm.spawn(self.player.pos, self.game_t)
        for _ in range(self.spawner.bosses_due(self.game_t)):
            self.swarm.spawn_boss(self.player.pos, self.game_t)
            self.boss_banner = config.BOSS_BANNER_TIME
        self.swarm.update(dt, self.player.pos)
        killed = self.equations.update(dt, self.game_t, self.swarm, self.player.pos,
                                      self.upgrades.base_dmg, self.upgrades.cooldown)
        self.kills += killed
        for _ in range(killed):
            self.emit("kill")
        for _ in range(self.swarm.last_removed_bosses):
            self.emit("boss_kill")
        self.swarm.last_removed_bosses = 0
        auto_was = self._auto_prev
        self._auto_prev = self.upgrades.auto
        if self._auto_prev and not auto_was:
            self.emit("auto_on")
        self.emit("tick", game_t=self.game_t, active_count=len(self.equations.active()))
        self.upgrades.add_xp(self.upgrades.kill_xp(self.swarm.last_removed_max_hp))
        self.swarm.last_removed_max_hp = 0.0
        while self.upgrades.auto and (stat := self.upgrades.cheapest_affordable()):
            self.buy(stat)
        if not self.player.alive:
            self.finish_run()
            self.slots.delete_autosave()
            self.next_scene = GameOverScene(self.game_t, self.kills)

    def draw(self, screen: pygame.Surface) -> None:
        t = config.DOT_TILE
        cx, cy = view.center()
        ox = int(cx - self.player.pos[0]) % t
        oy = int(cy - self.player.pos[1]) % t
        screen.fill(config.BG_COLOR)
        screen.blit(self.dots, (ox - t, oy - t))                 # dots scroll with the world
        if self.show_grid:
            for color, p0, p1 in self.grid_lines:
                pygame.draw.line(screen, color, p0, p1)
            for img, pos in self.grid_labels:
                screen.blit(img, pos)
        self.equations.draw(screen)
        self.swarm.draw(screen, self.player.pos)
        self.player.draw(screen)
        self._draw_hud(screen)
        self.sidebar.draw(screen)
        self.input.draw(screen)
        self.sidebar.draw_popups(screen)
        if self.paused:
            self._draw_pause(screen)

    def _draw_hud(self, screen: pygame.Surface) -> None:
        m = config.HUD_MARGIN
        draw_text(screen, fmt_time(self.game_t), config.HUD_TIMER_FONT, config.TEXT_COLOR,
                  (view.W // 2, m), "midtop")
        self.speed_button.draw(screen, self.speed)
        font, lh = config.HUD_TEXT_FONT, config.HUD_LINE_H
        skull = icons.skull(font, config.HUD_KILL_COLOR)                # "12 :" + skull, right-aligned
        screen.blit(skull, skull.get_rect(topright=(view.W - m, m)))
        draw_text(screen, f"{self.kills} :", font, config.HUD_KILL_COLOR,
                  (view.W - m - font - 2, m + font // 2 - 1), "midright")
        draw_text(screen, f"{int(self.upgrades.xp)} :XP", font, config.HUD_XP_COLOR,
                  (view.W - m, m + lh), "topright")
        if self.show_fps:
            draw_text(screen, f"{self.fps:.0f} :FPS", font, config.HUD_FPS_COLOR,
                      (view.W - m, m + 2 * lh), "topright")
        self.upgrade_panel.draw(screen)
        self._draw_toast(screen)
        self.undo_toast.draw(screen)
        if self.boss_banner > 0:
            draw_text(screen, "BOSS INCOMING", config.BOSS_BANNER_FONT, config.BOSS_COLOR,
                      (view.W // 2, view.H // 4), "center")

    def _draw_pause(self, screen: pygame.Surface) -> None:
        dim = pygame.Surface((view.W, view.H), pygame.SRCALPHA)
        dim.fill((0, 0, 0, config.PAUSE_DIM_ALPHA))
        screen.blit(dim, (0, 0))
        draw_text(screen, "PAUSED", config.TITLE_FONT, config.TEXT_COLOR, (view.W // 2, self.pause_top + 28),
                  "center", max_w=view.W - 40, min_size=28)
        for b in (self.resume_btn, self.stats_btn, self.saves_btn, self.settings_btn, self.library_btn,
                  self.menu_btn):
            b.draw(screen)
