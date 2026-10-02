"""All tunable numbers, colors and paths (DESIGN.md is the source of truth)."""
import os
from pathlib import Path

# Window / coordinates
WINDOW_FRACTION = 0.80     # windowed mode: square window, side = this * usable screen height
FPS = 60
TITLE = "Ascensus ad Mathematica"
UNIT_PX = 50.0
MAX_DT = 0.05

# Paths
ROOT = Path(__file__).resolve().parent.parent
PROFILE_PATH = Path(os.environ.get("ASCENSUS_PROFILE", ROOT / "save" / "profile.json"))
SETTINGS_PATH = Path(os.environ.get("ASCENSUS_SETTINGS", ROOT / "save" / "settings.json"))
ICON_PATH = Path(__file__).resolve().parent / "assets" / "icon.png"
APP_USER_MODEL_ID = "Ascensus.ad.Mathematica"

# Controls
TYPING_TIME_SCALE = 0.2
PLAYER_SPEED = 220.0

# Player
PLAYER_RADIUS = 14
PLAYER_HP = 100
PLAYER_IFRAMES = 0.6

# Enemies
ENEMY_RADIUS = 12
ENEMY_MAX_ALIVE = 250
ENEMY_SPAWN_MARGIN = 40
ENEMY_FLASH = 0.1
ENEMY_HP_BASE = 20.0
ENEMY_HP_PER_MIN = 0.15
ENEMY_DMG_BASE = 8.0
ENEMY_DMG_PER_MIN = 0.10
ENEMY_SPEED_BASE = 70.0
ENEMY_SPEED_PER_MIN = 0.03
ENEMY_SPEED_MAX = 140.0
SPAWN_MIN_INTERVAL = 0.15
SPAWN_RATE_PER_MIN = 0.35
SEPARATION_ITERS = 2         # pairwise enemy separation passes per frame
SEPARATION_MARGIN = 12.0     # broad phase: pairs closer than r_i + r_j + this are refined
CONTACT_SLOP = 2.0           # contact means d <= r_p + r_e + slop
KNOCKBACK_DIST = 40.0        # touching enemies are shoved this far when contact damage lands

# Boss
BOSS_INTERVAL = 300.0        # game seconds between bosses
BOSS_HP_MULT = 40.0
BOSS_DMG_MULT = 3.0
BOSS_SPEED_MULT = 0.75
BOSS_RADIUS = 40
BOSS_COLOR = (170, 60, 255)
BOSS_BANNER_TIME = 2.5
BOSS_BANNER_FONT = 72
BOSS_HP_FONT = 26

# Player dash / regen
PLAYER_REGEN_PER_MIN = 10.0
DASH_DIST = 160.0
DASH_TIME = 0.12
DASH_COOLDOWN = 0.0
PLAYER_NOTCH_LEN = 7         # facing triangle: length (px) and half-width
PLAYER_NOTCH_HALF = 4

# HP numbers
ENEMY_HP_FONT = 16
ENEMY_HP_TEXT_COLOR = (255, 70, 70)
PLAYER_HP_FONT = 20
PLAYER_HP_TEXT_COLOR = (80, 220, 120)

# Equations and combat
MAX_EQUATION_LEN = 120
NAME_MAX_LEN = 16               # longest equation name ("eq4: ...")
VAR_DEFAULT = 1.0               # value of a variable the caller did not supply
MAX_VARIABLES = 200
VAR_MIN = -5.0                  # variable slider / play range
VAR_MAX = 5.0
VAR_STEP = 0.01                 # slider snap and play step
VAR_PLAY_HZ = 60.0              # play steps per second of game time
SIDEBAR_NAME_GAP = 8            # px between a row's bold name and its dimmed body
MAX_ROWS = 200
MAX_ACTIVE = 6
PULSE_PERIOD = 1.0              # starting cooldown stat (seconds between pulses)
FIRST_PULSE_DELAY = 0.3
BASE_DMG = 100.0                # starting base damage stat
DMG_SCALE = 4.0                 # dmg = base_dmg * DMG_SCALE / max(L, L_MIN)
L_MIN = 4.0
DMG_MIN = 1.0
DMG_MAX_FRAC = 0.5              # a pulse never exceeds this fraction of base_dmg
COOLDOWN_MIN = 0.05
ERROR_SHOW_TIME = 3.0

# XP and upgrades
XP_PER_HP = 0.5                 # xp earned per point of killed-enemy max hp
UPG_COST_BASE = 20.0
UPG_COST_GROWTH = 1.12          # cost = round(base * growth ** level), per stat
UPG_HP_STEP = 10                # Max HP buy: +max hp and the same heal
UPG_DMG_STEP = 10               # Base DMG buy: +base damage
UPG_CD_MULT = 0.95              # Cooldown buy: cooldown *= this
UPG_PANEL_W = 250
UPG_BTN_H = 40
UPG_GAP = 6
UPG_FONT = 26
UPG_DISABLED_COLOR = (90, 96, 118)
UPG_AUTO_ON_FILL = (20, 80, 70)

# Curve engine
GRID_STEP = 3
GRID_STEP_T = 5
BISECT_ITERS = 5
POLE_FILTER = 0.5
HIT_CELL = 8
HIT_DILATE = 2
CORE_DILATE = 1
GLOW_DILATE = 3
GLOW_ALPHA = 80
T_REBUILD_HZ = 10
CURVE_TILE = 64              # curves are blitted per occupied tile of this size
CURVE_TILE_MAX_FILL = 0.7    # above this fraction of occupied tiles, blit the whole bbox
REBUILDS_PER_FRAME = 2       # at most this many dirty (t) curves rebuild per frame, round-robin
QUEUED_BUILD_PER_FRAME = 2   # progressive build of queued curves after a load / resize
QUEUED_LAYER_PERIOD = 1.0    # the shared queued-curve layer refreshes at most this often (seconds)

# Curve visuals
ALPHA_IDLE = 90
ALPHA_PULSE = 255
ALPHA_QUEUED = 30
PULSE_FADE = 0.25
# Equation colours (W4): 20 named swatches, shown as a 5 x 4 grid of rows in the sidebar picker.
CURVE_PALETTE_20 = [
    (255, 255, 255), (192, 198, 212), (128, 134, 150), (70, 74, 88), (0, 0, 0),           # neutrals
    (255, 59, 48), (255, 149, 0), (255, 214, 10), (190, 240, 40), (52, 199, 89),          # warm
    (0, 199, 170), (0, 220, 255), (90, 170, 255), (40, 90, 255), (94, 92, 230),           # cool
    (150, 90, 255), (190, 80, 230), (255, 45, 200), (255, 120, 170), (165, 110, 60),      # purple to brown
]
CURVE_PALETTE_NAMES = [
    "White", "Silver", "Gray", "Graphite", "Black",
    "Red", "Orange", "Yellow", "Lime", "Green",
    "Teal", "Cyan", "Sky", "Blue", "Indigo",
    "Violet", "Purple", "Magenta", "Pink", "Brown",
]
# New equations take colours from this list (the palette without Black and Graphite, which are
# nearly invisible on the dark background); the picker still offers all 20.
CURVE_PALETTE_AUTO = [c for c, n in zip(CURVE_PALETTE_20, CURVE_PALETTE_NAMES) if n not in ("Black", "Graphite")]

# Look
BG_COLOR = (10, 12, 24)
DOT_TILE = 64
DOT_COLOR = (34, 40, 64)
GRID_ALPHA = 22
AXES_ALPHA = 70
GRID_TICK_EVERY = 2

# Sidebar
SIDEBAR_W = 300
SIDEBAR_COLOR = (15, 18, 30, 170)
SIDEBAR_ROW_H = 44
SIDEBAR_TAB_SIZE = (30, 60)
SIDEBAR_TAB_Y = 80
DRAG_THRESHOLD = 4
SIDEBAR_HEADER_H = 64
SIDEBAR_PAD = 8
SIDEBAR_TITLE_FONT = 28
SIDEBAR_SMALL_FONT = 20
SIDEBAR_TEXT_FONT = 24
SIDEBAR_TAG_FONT = 18
SIDEBAR_COLLAPSE_SIZE = 28
SIDEBAR_SWATCH = 14
SIDEBAR_SWITCH_SIZE = (32, 16)
SIDEBAR_EDIT_W = 40
SIDEBAR_DEL_W = 34
SIDEBAR_BTN_H = 24
SIDEBAR_HOVER_COLOR = (255, 255, 255, 28)
SIDEBAR_DRAG_ALPHA = 200
SIDEBAR_SCROLL_ROWS = 3             # rows per mouse-wheel notch
SIDEBAR_EDGE_SCROLL_ZONE = 30       # dragging within this many px of a section edge auto-scrolls
SIDEBAR_EDGE_SCROLL_SPEED = 500.0   # px per second at the very edge
SIDEBAR_SCROLLBAR_W = 4
SIDEBAR_SCROLLBAR_MIN = 20          # shortest scrollbar thumb (px)
SIDEBAR_SCROLLBAR_COLOR = (120, 135, 175, 160)
SIDEBAR_VARS_FRACTION = 0.4         # share of the panel height for VARIABLES when any exist
SIDEBAR_SECTION_H = 24              # height of a section title strip
VAR_ROW_H = 36                      # height of a VARIABLES row
VAR_NAME_W = 44                     # width of the name cell
VAR_BOX_W = 62                      # width of the value box
VAR_BOX_H = 24
VAR_BTN = 24                        # play/pause button size
VAR_VALUE_LIMIT = 1.0e9             # typed values are clamped to +-this
PICKER_COLS = 5
PICKER_CELL = 22
PICKER_GAP = 4
PICKER_PAD = 8
PICKER_FILL = (18, 22, 40)
PICKER_BORDER = (70, 90, 140)
SWITCH_ON_COLOR = (0, 200, 230)
SWITCH_OFF_COLOR = (70, 76, 100)

# Input box
INPUT_SIZE = (560, 42)
INPUT_BOTTOM_MARGIN = 20
INPUT_MIN_W = 300               # the input box never gets narrower than this when side by side with the panel
LAYOUT_GAP = 12                 # gap between the sidebar, input box and upgrades panel
INPUT_ERROR_GAP = 18
INPUT_PLACEHOLDER = "Type an equation, e.g. y = sin(x)   [Enter]"

# Player / enemy look
PLAYER_COLOR = (255, 255, 255)
PLAYER_RING_COLOR = (0, 220, 255)
PLAYER_RING_ALPHA = 90
PLAYER_RING_EXTRA = 8
PLAYER_BLINK_HZ = 10
ENEMY_COLOR = (230, 50, 60)
ENEMY_DARKEST = 0.4          # colour multiplier at 0 hp
ENEMY_FLASH_COLOR = (255, 255, 255)
ENEMY_CULL_MARGIN = 20

# Background / grid
DOT_RADIUS = 2
GRID_COLOR = (130, 170, 230)
GRID_TICK_COLOR = (170, 190, 230)
GRID_TICK_ALPHA = 110
GRID_TICK_FONT = 16

# Text / UI
TEXT_COLOR = (225, 232, 245)
DIM_TEXT_COLOR = (130, 140, 165)
ACCENT_COLOR = (0, 220, 255)
DANGER_COLOR = (255, 80, 90)
BUTTON_SIZE = (220, 52)
BUTTON_FONT = 32
BUTTON_FILL = (24, 30, 52)
BUTTON_HOVER_FILL = (40, 54, 92)
BUTTON_BORDER = (70, 90, 140)
TITLE_FONT = 84
SUBTITLE_FONT = 34
BODY_FONT = 26
PAUSE_DIM_ALPHA = 150

# HUD
HUD_TIMER_FONT = 60
HUD_TEXT_FONT = 28
HUD_MARGIN = 16
HUD_LINE_H = 30
HUD_KILL_COLOR = (230, 60, 60)
HUD_XP_COLOR = (80, 220, 120)
HUD_FPS_COLOR = (255, 160, 40)
SHOW_FPS_DEFAULT = True
SHOW_GRID_DEFAULT = True
FULLSCREEN_START = True          # Settings: start in full screen (applies on the next launch)

# Input box look / keys
KEY_REPEAT_DELAY = 400
KEY_REPEAT_INTERVAL = 35
INPUT_FONT = 30
INPUT_ERROR_FONT = 26
INPUT_LABEL_FONT = 22
INPUT_FILL = (14, 16, 30)
INPUT_BORDER = (70, 80, 120)
INPUT_BORDER_FOCUS = (0, 220, 255)
INPUT_PAD = 12
INPUT_SELECT_COLOR = (40, 90, 160)
CURSOR_BLINK = 0.5
DOUBLE_CLICK_MS = 350          # two clicks this close (ms) select a word in the equation box

# Menu flourish / text cache
MENU_CURVE = "y = 2sin(x + t) + 4"
MENU_CURVE_REBUILD = 0.1
MENU_CURVE_ALPHA = 90
TEXT_CACHE_MAX = 600

# Achievements
TOAST_TIME = 3.0
TOAST_FONT = 28
TOAST_BORDER = (255, 205, 60)
ACH_FULL_HOUSE = 6
ACH_CENTURION_KILLS = 100
ACH_SURVIVOR_TIME = 300.0
ACH_MARATHON_TIME = 900.0
ACH_DASH_COUNT = 100
ACH_ETERNITY_TIME = 3600.0
ACH_SPEED_DEMON_TIME = 60.0    # game seconds at 3x speed in one run
ACH_UNTOUCHABLE_TIME = 120.0   # game seconds without taking damage
ACH_MATHEMATICIAN = 50
ACH_RAINBOW = 6

# Widgets (Tabs, Slider, NumberField, ScrollArea, IconButton)
TAB_FONT = 26
TAB_ITEM_H = 40
TAB_PAD = 14
TAB_GAP = 4
TAB_ACTIVE_FILL = (30, 46, 80)
SLIDER_TRACK_H = 4
SLIDER_KNOB_R = 8
SCROLL_ROW_PX = 40
SCROLL_ROWS_PER_NOTCH = 3
SCROLLBAR_W = 4
SCROLLBAR_MIN_THUMB = 24
SCROLLBAR_COLOR = (90, 110, 160)
NUMBER_FIELD_FONT = 24
NUMBER_FIELD_MAX_CHARS = 14
ICON_BTN_SIZE = 24

# Library and Achievements pages (P13)
PAGE_MARGIN = 24
PAGE_HEADER_H = 70
PAGE_BACK_SIZE = (120, 40)
PAGE_TITLE_FONT = 44
LIB_TABS_W = 230
LIB_TEXT_FONT = 24
LIB_HEAD_FONT = 30
LIB_GROUP_FONT = 26
LIB_NAME_FONT = 32
LIB_SMALL_FONT = 22
LIB_CARD_PAD = 12
LIB_CARD_GAP = 10
LIB_CARD_FILL = (16, 20, 38)
LIB_CARD_BORDER = (50, 60, 100)
LIB_GRAPH_SIZE = (200, 120)
LIB_GRAPH_UNIT = 20
LIB_GRAPHS_PER_FRAME = 2         # mini graphs rendered per frame while cards scroll into view
LIB_PARA_GAP = 18
ACH_COLS = 4
ACH_ROWS = 5
ACH_GAP = 12
ACH_CARD_MIN_H = 120
ACH_WIDE_W = 1100             # at least this wide: ACH_COLS columns, otherwise ACH_NARROW_COLS
ACH_NARROW_COLS = 2
ACH_PAD = 10
ACH_ICON = 44
ACH_NAME_FONT = 26
ACH_DESC_FONT = 20
ACH_DATE_FONT = 18
ACH_COUNT_FONT = 34
ACH_LOCKED_FILL = (14, 16, 28)
ACH_UNLOCKED_BORDER = (150, 125, 40)
TOAST_PAD = 12
TOAST_GAP = 8
TOAST_FILL = (20, 18, 8)

# Settings and Stats pages (P12)
SET_ROW_H = 58
SET_LABEL_FONT = 26
SET_NOTE_FONT = 20
SET_FIELD_W = 110
SET_CTRL_H = 32
SET_SWITCH_SIZE = (52, 26)
SET_BOTTOM_H = 64                # strip under the rows with Reset tab / Reset all
STATS_FONT = 24
STATS_HEAD_FONT = 32
STATS_LINE_H = 32
STATS_WIDE_W = 1200              # at least this wide: four columns, otherwise two by two

SWATCH_HIT = 22               # clickable size of a row's colour swatch (px)
FONT_SCALE = 0.72              # freetype size = pygame.font pixel size * this (keeps the old text widths)
MIN_TEXT_SIZE = 12            # draw_text never shrinks below this unless asked
WINDOW_MIN_SIZE = (800, 600)  # smallest resizable window
UPG_MIN_FONT = 14              # upgrade button labels shrink to this before being cut

# --- P20: saves, Continue and undo (appended section) ---
SLOTS_PATH = Path(os.environ.get("ASCENSUS_SLOTS", ROOT / "save" / "slots"))
SAVE_SLOTS = 6
SAVE_VERSION = 1
THUMB_SIZE = (320, 180)
AUTOSAVE_PERIOD = 60.0           # seconds of play between autosaves
UNDO_MAX = 10                    # deleted equations remembered for undo
UNDO_TOAST_TIME = 5.0
UNDO_TOAST_FONT = 26
DELETE_CONFIRM_TIME = 3.0        # second click on Delete within this confirms
SAVES_NARROW_W = 1000            # narrower than this: 2 columns x 3 rows instead of 3 x 2
SAVES_GAP = 16
SAVES_PAD = 8
SAVES_BTN_H = 34
SAVES_TIME_FONT = 48
SAVES_SMALL_FONT = 22
SAVES_BTN_FONT = 24
SAVES_NOTE_TIME = 2.5            # seconds the "Saved" / "Could not load" note stays up
SAVES_SHADOW = (0, 0, 0)

# --- P19: controls, speed button and smooth curves (appended section) ---
MOVE_MODE = "WASD"               # "WASD" (keys) or "Mouse" (walk toward the cursor)
DASH_KEY = "j"                   # pygame key name; replaces R
MOUSE_DEAD_ZONE = float(PLAYER_RADIUS)   # px around the player where the cursor means "stand still"
SPEED_STEPS = (1, 2, 3)          # the speed button cycles through these
SIM_MAX_SUBSTEP = 1 / 30         # a game step never advances more than this many seconds
SIM_MAX_SUBSTEPS = 12            # cap per frame (a long hitch is simulated coarser instead of spiralling)
SPEED_BTN_SIZE = (92, 38)
SPEED_BTN_GAP = 14               # between the timer text and the button
SPEED_BTN_ALPHA = 120            # fill alpha (semi-transparent)
SPEED_BTN_FONT = 26
CURVE_KERNEL_FULL_R = 1.5        # smooth curve stamp: full alpha within this radius (px) ...
CURVE_KERNEL_END_R = 4.0         # ... falling to 0 here
CURVE_KERNEL_POWER = 2.0         # falloff exponent
CURVE_FILL_SPACING = 2.0         # px between filled-in points when a grid cell's two crossings are joined
DARK_LUMINANCE = 0.15            # relative luminance below this gets a light halo
HALO_COLOR = (200, 205, 220)
HALO_ALPHA = 110
HALO_FULL_R = 2.5
HALO_END_R = 5.0
KEYFIELD_FONT = 24

# Icons and colour picker (P18)
ICON_COLOR = (255, 255, 255)        # default tint of icon() (the PNGs are white)
ICON_INSET = 6                      # px a draw_icon() image is smaller than its rect (per axis)
SIDEBAR_BTN_ICON = 16               # px, pencil / trash icons on a sidebar row
PICKER_STRIP_H = 14                 # hue / brightness strip height in the colour popup
PICKER_STRIP_GAP = 5                # px between the two strips
PICKER_SEP = 6                      # px between the swatch grid and the Custom row (separator line)
PICKER_PREVIEW = 22                 # preview swatch and hex box height
PICKER_HEX_FONT = 18
PICKER_TIP_FONT = 18
PICKER_TIP_FILL = (30, 36, 62)
PICKER_TIP_PAD = 4
PICKER_HEX_MAX = 7                  # "#RRGGBB"

AUTOSAVE_MIN_TIME = 1.0          # no autosave for a run younger than this (seconds of game time)
STATS_MIN_LINE_H = 18          # stats rows never get tighter than this (short windows shrink them down to it)
