"""Library page content as plain data (no pygame): editing text here never touches layout code.

TABS lists the tab names in order. `FUNCTIONS` is the card list of the Functions tab (one dict per
canonical function: name, aliases, syntax, explanation, example, group); every other tab is a list of
(title, [lines]) paragraphs, reached with `paragraphs(tab)`. Examples are checked by the tests: each
one parses, uses x or y, and renders a 200x120 mini graph.
"""
from __future__ import annotations

TABS = ["Functions", "Syntax", "Variables", "Combat", "Upgrades & XP", "Enemies & Bosses", "Controls"]


def _fn(group, name, aliases, syntax, explanation, example) -> dict:
    return {"group": group, "name": name, "aliases": list(aliases), "syntax": syntax,
            "explanation": explanation, "example": example}


TRIG, INVERSE, HYPER, ROOTS, ROUND, EXPLOG, TWO = (
    "Trigonometry", "Inverse trigonometry", "Hyperbolic", "Roots", "Rounding and sign",
    "Exponentials and logarithms", "Two arguments")

FUNCTIONS: list[dict] = [
    _fn(TRIG, "sin", [], "sin(a)", "Sine of a, in radians. Waves between -1 and 1.", "y = sin(x)"),
    _fn(TRIG, "cos", [], "cos(a)", "Cosine of a, in radians: a sine shifted left by a quarter turn.", "y = cos(x)"),
    _fn(TRIG, "tan", [], "tan(a)", "Tangent of a: sin over cos, with vertical asymptotes.", "y = tan(x)"),
    _fn(TRIG, "sec", [], "sec(a)", "Secant: 1 / cos(a).", "y = sec(x)"),
    _fn(TRIG, "csc", [], "csc(a)", "Cosecant: 1 / sin(a).", "y = csc(x)"),
    _fn(TRIG, "cot", [], "cot(a)", "Cotangent: 1 / tan(a).", "y = cot(x)"),
    _fn(INVERSE, "asin", ["arcsin"], "asin(a)", "Inverse sine, in radians. Defined for a between -1 and 1.", "y = 2asin(x/5)"),
    _fn(INVERSE, "acos", ["arccos"], "acos(a)", "Inverse cosine, in radians. Defined for a between -1 and 1.", "y = 2acos(x/5) - 3"),
    _fn(INVERSE, "atan", ["arctan"], "atan(a)", "Inverse tangent, in radians. Flattens out at +-pi/2.", "y = 2atan(x)"),
    _fn(INVERSE, "asec", ["arcsec"], "asec(a)", "Inverse secant: acos(1/a). Defined for |a| of at least 1.", "y = asec(x)"),
    _fn(INVERSE, "acsc", ["arccsc"], "acsc(a)", "Inverse cosecant: asin(1/a). Defined for |a| of at least 1.", "y = acsc(x)"),
    _fn(INVERSE, "acot", ["arccot"], "acot(a)", "Inverse cotangent: pi/2 - atan(a), between 0 and pi.", "y = 2acot(x) - 3"),
    _fn(HYPER, "sinh", [], "sinh(a)", "Hyperbolic sine: (e^a - e^-a) / 2.", "y = sinh(x)/3"),
    _fn(HYPER, "cosh", [], "cosh(a)", "Hyperbolic cosine: (e^a + e^-a) / 2, a hanging-chain curve.", "y = cosh(x)/3 - 2"),
    _fn(HYPER, "tanh", [], "tanh(a)", "Hyperbolic tangent: an S-curve between -1 and 1.", "y = 2tanh(x)"),
    _fn(HYPER, "asinh", ["arsinh", "arcsinh"], "asinh(a)", "Inverse hyperbolic sine. Defined everywhere.", "y = 2asinh(x)"),
    _fn(HYPER, "acosh", ["arcosh", "arccosh"], "acosh(a)", "Inverse hyperbolic cosine. Defined for a of at least 1.", "y = 2acosh(x)"),
    _fn(HYPER, "atanh", ["artanh", "arctanh"], "atanh(a)", "Inverse hyperbolic tangent. Defined for a between -1 and 1.", "y = atanh(x)"),
    _fn(ROOTS, "sqrt", [], "sqrt(a)", "Square root. Negative inputs give no curve.", "y = sqrt(x)"),
    _fn(ROOTS, "cbrt", [], "cbrt(a)", "Cube root, defined for negative numbers too.", "y = 2cbrt(x)"),
    _fn(ROUND, "abs", [], "abs(a)", "Absolute value: drops the sign, so the graph is mirrored upward.", "y = abs(x) - 2"),
    _fn(ROUND, "sign", ["sgn"], "sign(a)", "-1, 0 or 1 by the sign of a. Handy as a multiplier.", "y = sign(x) * x^2 / 3"),
    _fn(ROUND, "floor", [], "floor(a)", "Round down to the nearest whole number.", "y = floor(x)"),
    _fn(ROUND, "ceil", [], "ceil(a)", "Round up to the nearest whole number.", "y = ceil(x)"),
    _fn(ROUND, "round", [], "round(a)", "Round to the nearest whole number (halves go to the even one).", "y = round(x)"),
    _fn(EXPLOG, "exp", [], "exp(a)", "e raised to the power a.", "y = exp(x/2) - 3"),
    _fn(EXPLOG, "ln", ["in"], "ln(a)", "Natural logarithm (base e). 'in' is accepted as a typo-friendly alias.", "y = ln(x)"),
    _fn(EXPLOG, "log", [], "log(a)  or  log(b, a)",
        "log(a) is the base 10 logarithm; log(b, a) is the logarithm of a in base b.", "y = log(2, x)"),
    _fn(EXPLOG, "log2", [], "log2(a)", "Base 2 logarithm.", "y = log2(x)"),
    _fn(TWO, "min", [], "min(a, b)", "The smaller of a and b.", "y = min(x/2, 2)"),
    _fn(TWO, "max", [], "max(a, b)", "The larger of a and b.", "y = max(x/2, -1)"),
    _fn(TWO, "mod", [], "mod(a, b)", "Remainder of a / b with the sign of b: a sawtooth wave. The % operator does the same.",
        "y = mod(x, 2)"),
    _fn(TWO, "hypot", [], "hypot(a, b)", "Length of the hypotenuse: sqrt(a^2 + b^2).", "y = hypot(x, 1)"),
    _fn(TWO, "atan2", ["arctan2"], "atan2(y, x)",
        "The angle of the point (x, y) in radians, in the correct quadrant. Note the order: y first.", "y = atan2(x, 2)"),
    _fn(TWO, "root", [], "root(n, a)",
        "The real n-th root of a. For odd whole n negative a works too (root(3, -8) is -2).", "y = root(3, x)"),
]

_PARAGRAPHS: dict[str, list[tuple[str, list[str]]]] = {
    "Syntax": [
        ("What you can type", [
            "Numbers, the variables x, y and t, the constants pi and e, and the operators",
            "+  -  *  /  ^  %  and parentheses. ** works like ^, and the typographic multiplication,",
            "division, minus, pi and square-root symbols are accepted too.",
            "Capital letters are fine: everything is read as lower case. Maximum 120 characters.",
        ]),
        ("Implicit multiplication", [
            "You can leave out the *: 2x, 3sin(x), (x+1)(x-1), xy and 2pi all work.",
            "A function name must be followed by parentheses: sin(x), never sin x.",
        ]),
        ("What a formula means", [
            "No '=' and no y: the formula is y = expression, so x^2 draws y = x^2.",
            "No '=' but a y: the formula means expression = 0.",
            "One '=': the curve is every point where the left side equals the right side,",
            "for example x = 2, 1 = x^2 + y^2 or tan(sqrt(x^2 + y^2)) = y / x.",
            "The formula must contain x or y, and only one '=' is allowed.",
        ]),
        ("The variable t", [
            "t is game time in seconds, so y = 2sin(x + t) is a wave that travels.",
            "Curves that use t are rebuilt about 10 times per second.",
        ]),
        ("Names", [
            "Start a line with name: to label it, for example  r1: x^2 + y^2 = 1.",
            "The name is only a label (up to 16 characters) and must be unique among your equations.",
            "Edit loads the whole 'name: formula' text back into the box.",
        ]),
        ("Functions with several arguments", [
            "Separate the arguments with a comma: min(x, 2), root(3, x), log(2, x), atan2(y, x).",
            "Each function checks its argument count and tells you if it is wrong.",
        ]),
    ],
    "Variables": [
        ("Free variables", [
            "Any single letter other than x, y, t and e is a variable: a, b, k, m ...",
            "Add a subscript with an underscore: b_1, k_2. Letters written together are split into",
            "variables: ab means a times b. Known function names win: sin is never s*i*n.",
            "Writing something like sni(x) shows the hint 'for variables write s*n*i(...)'.",
        ]),
        ("The Variables list", [
            "A variable appears in the VARIABLES section of the sidebar when you cast an equation that uses it",
            "and disappears when no equation uses it any more. There can be up to 200 variables.",
            "A new variable starts at 1.0.",
        ]),
        ("Changing a value", [
            "Drag or click the slider (from -5 to 5, in steps of 0.01), or click the value box and type",
            "any number, even beyond the slider range. Enter applies it and Esc cancels.",
            "Typing a value slows time just like typing an equation.",
        ]),
        ("Play", [
            "The play button sweeps the variable back and forth between -5 and 5 in steps of 0.01,",
            "60 steps per second of game time. Curves that use a moving variable rebuild about 10 times a second.",
            "Try y = a sin(x) and press play on a.",
        ]),
    ],
    "Combat": [
        ("Active and queued equations", [
            "The first 6 enabled equations in the sidebar are active: they draw bright and deal damage.",
            "The rest are queued: drawn very faint, no damage. Drag rows to choose which ones fire.",
            "You can keep up to 200 equations in the list.",
        ]),
        ("Pulses", [
            "Each active equation pulses once per cooldown (starts at 1.00 s, never below 0.05 s).",
            "A new equation fires its first pulse after 0.3 s. On a pulse every enemy touching",
            "the curve (about 16 px either side) takes damage and the curve flashes bright.",
        ]),
        ("Damage", [
            "damage = base DMG x 4 / curve length, kept between 1 and half of the base DMG.",
            "The curve length L is how much of the curve is visible, in math units (at least 4).",
            "Short curves hit hard, long curves hit softly: with base DMG 100, x = 2 does about 28,",
            "the unit circle about 64, sin(x) about 12 and the tan(sqrt(x^2+y^2)) = y/x monster about 4.",
        ]),
        ("Slow motion", [
            "While you type an equation, edit a variable or drag a row, time runs at 20%.",
            "The run clock slows with it.",
        ]),
        ("The player", [
            "You have 100 HP and regenerate 10 HP per minute. After a hit you are invulnerable",
            "and blinking for 0.6 s. Your HP is the green number under you.",
            "Dash with R: 160 px toward the direction you face, invulnerable while dashing, no cooldown.",
        ]),
    ],
    "Upgrades & XP": [
        ("Earning XP", [
            "Every kill gives XP equal to half the enemy's maximum HP. Bosses give a lot.",
            "XP is shown in green in the top-right; XP spent is tracked too.",
        ]),
        ("The upgrade panel (bottom-right)", [
            "Max HP: +10 maximum HP and heals 10.",
            "Base DMG: +10 base damage, which makes every pulse stronger.",
            "Cooldown: multiplies the cooldown by 0.95, down to 0.05 s.",
            "Auto: toggles automatic buying.",
        ]),
        ("Costs", [
            "The price of each stat is round(20 x 1.12 ^ level), where level is how many times you bought it.",
            "Each stat has its own level. Levels reset at the start of every run.",
            "A button is greyed out while you cannot afford it.",
        ]),
        ("Auto", [
            "With Auto on, the game buys the cheapest affordable upgrade every frame until nothing is",
            "affordable. Ties go to Max HP, then Base DMG, then Cooldown.",
        ]),
    ],
    "Enemies & Bosses": [
        ("Enemies", [
            "Red circles (radius 12) that chase you directly. They appear just off-screen, up to 250 at once.",
            "Their HP is the red number under each enemy. They darken as they lose HP.",
            "They push each other apart, and they never push you.",
        ]),
        ("Difficulty over time (m = game minutes)", [
            "HP = 20 x (1 + 0.15 m).   Contact damage = 8 x (1 + 0.10 m).",
            "Speed = 70 x (1 + 0.03 m) px/s, capped at 140.",
            "One enemy spawns every max(0.15, 1 / (1 + 0.35 m)) seconds.",
        ]),
        ("Contact", [
            "When an enemy touches you, you take its damage and get 0.6 s of invulnerability.",
            "Every enemy touching you is knocked back 40 px when the damage lands.",
        ]),
        ("Bosses", [
            "A boss arrives every 5:00 of game time (a 'BOSS INCOMING' banner shows first).",
            "It has 40 times the current enemy HP, 3 times the damage, 0.75 times the speed",
            "and radius 40. It is purple, and it does not count toward the 250 enemy limit.",
            "Its hitbox is its whole body: any part of a curve crossing it counts.",
        ]),
    ],
    "Controls": [
        ("Moving", [
            "WASD or the arrow keys move you (disabled while typing).",
            "R dashes toward the direction you last moved.",
        ]),
        ("Typing", [
            "Enter focuses the equation box and slows time; Enter again casts the equation.",
            "Esc cancels. Left, Right, Home and End move the cursor; Shift extends the selection.",
            "Ctrl+V pastes, Ctrl+C copies the selection (or everything), Ctrl+X cuts and Ctrl+A selects all.",
        ]),
        ("Interface", [
            "G toggles the grid. F3 toggles the FPS counter. F11 toggles full screen.",
            "Esc (not typing) pauses; Esc again resumes.",
            "Sidebar: drag rows to reorder, use the switch to enable or disable, click Edit or Del,",
            "click a color swatch to recolor, and scroll the lists with the mouse wheel.",
        ]),
    ],
}


def paragraphs(tab: str) -> list[tuple[str, list[str]]]:
    """(title, lines) paragraphs of a non-Functions tab."""
    return _PARAGRAPHS[tab]
