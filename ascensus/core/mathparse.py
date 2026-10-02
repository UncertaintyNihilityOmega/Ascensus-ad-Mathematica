"""Equation text -> ParsedEquation (numpy only, no pygame). See ARCHITECTURE section 2."""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from typing import Callable

import numpy as np

from ascensus import config


class EquationError(ValueError):
    """Raised for any bad equation; the message is shown to the player verbatim."""


def _recip(fn: Callable) -> Callable:
    return lambda a: 1.0 / fn(a)


def _log(a, b=None):
    """log(x) is base 10; log(b, x) is log base b of x."""
    return np.log10(a) if b is None else np.log(b) / np.log(a)


def _root(n, x):
    """Real n-th root: odd integer n keeps the sign of x; otherwise x < 0 gives nan."""
    n, x = np.asarray(n, dtype=float), np.asarray(x, dtype=float)
    r = np.abs(x) ** (1.0 / n)
    odd = np.mod(n, 2.0) == 1.0
    return np.where(odd, np.sign(x) * r, np.where(x >= 0, r, np.nan))


NS: dict[str, object] = {
    "sin": np.sin, "cos": np.cos, "tan": np.tan,
    "sec": _recip(np.cos), "csc": _recip(np.sin), "cot": _recip(np.tan),
    "asin": np.arcsin, "acos": np.arccos, "atan": np.arctan,
    "asec": lambda a: np.arccos(1.0 / a), "acsc": lambda a: np.arcsin(1.0 / a),
    "acot": lambda a: np.pi / 2 - np.arctan(a),
    "sinh": np.sinh, "cosh": np.cosh, "tanh": np.tanh,
    "asinh": np.arcsinh, "acosh": np.arccosh, "atanh": np.arctanh,
    "sqrt": np.sqrt, "cbrt": np.cbrt,
    "abs": np.abs, "sign": np.sign, "floor": np.floor, "ceil": np.ceil, "round": np.round,
    "exp": np.exp, "ln": np.log, "log": _log, "log2": np.log2,
    "min": np.minimum, "max": np.maximum, "mod": np.mod, "hypot": np.hypot,
    "atan2": np.arctan2, "root": _root,
    "pi": np.pi, "e": np.e,
}
ONE_ARG = ("sin cos tan sec csc cot asin acos atan asec acsc acot sinh cosh tanh asinh acosh "
           "atanh sqrt cbrt abs sign floor ceil round exp ln log2").split()
FUNC_ARITY: dict[str, tuple[int, ...]] = {
    **{name: (1,) for name in ONE_ARG},
    "log": (1, 2),
    **{name: (2,) for name in ("min", "max", "mod", "hypot", "atan2", "root")},
}
ALIASES = {
    "arcsin": "asin", "arccos": "acos", "arctan": "atan", "arcsec": "asec", "arccsc": "acsc",
    "arccot": "acot", "arsinh": "asinh", "arcsinh": "asinh", "arcosh": "acosh",
    "arccosh": "acosh", "artanh": "atanh", "arctanh": "atanh", "sgn": "sign", "in": "ln",
    "arctan2": "atan2",
}
FUNCS = frozenset(FUNC_ARITY)
CONSTS = frozenset({"pi", "e"})
VARS = frozenset({"x", "y", "t"})
_NAMES = sorted(FUNCS | set(ALIASES) | CONSTS | VARS, key=len, reverse=True)  # longest first
_DIGIT_FUNCS = {"log": "log2", "atan": "atan2"}   # names written with a trailing 2: log2(, atan2(
_VAR_NAME_RE = re.compile(r"^[a-z](_\d+)?$")

_TOKEN_RE = re.compile(r"\s+|\d+\.?\d*|\.\d+|[a-z]+(?:_\d+)?|\*\*|[-+*/%(),]")
_REPLACEMENTS = (("^", "**"), ("×", "*"), ("÷", "/"), ("−", "-"), ("π", "pi"), ("√", "sqrt"))

_ALLOWED_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.Mod)
_ALLOWED_UNARY = (ast.UAdd, ast.USub)
_CANT_READ = "Can't read equation"
_NAME_RE = r"^\s*([A-Za-z][A-Za-z0-9_]{{0,{n}}})\s*:\s*(.*)$"
_NAME_LIKE_RE = re.compile(r"^\s*[A-Za-z][A-Za-z0-9_]*\s*:")


@dataclass(frozen=True)
class ParsedEquation:
    """A validated equation: the curve is F(x, y, t) = 0 (variables default to VAR_DEFAULT)."""
    source: str                    # the body, without any "name:" prefix
    expr: str
    uses_t: bool
    func: Callable[..., np.ndarray]    # func(x, y, t=0.0, vars=None)
    name: str | None = None
    funcs: frozenset[str] = frozenset()        # canonical function names used
    variables: frozenset[str] = frozenset()    # free variables used (not x, y, t, e)

    @property
    def text(self) -> str:
        """The full normalised text: "name: body", or just the body when unnamed."""
        return f"{self.name}: {self.source}" if self.name else self.source


def _tokenize(side: str) -> list[tuple[str, str]]:
    """Split one side into (kind, text) tokens; alpha runs are split into known names."""
    tokens: list[tuple[str, str]] = []
    pos = 0
    while pos < len(side):
        m = _TOKEN_RE.match(side, pos)
        if m is None:
            raise EquationError(f"Unexpected character '{side[pos]}'")
        pos = m.end()
        text = m.group()
        if text.isspace():
            continue
        if text[0].isdigit() or text[0] == ".":
            tokens.append(("num", text))
        elif text[0].isalpha():
            letters, _, sub = text.partition("_")
            run = _split_alpha(letters)
            if sub:                                  # a_1: the subscript belongs to the last letter
                kind, last = run[-1]
                if kind != "var" or last in VARS:
                    raise EquationError(f"'{last}' can't take a subscript")
                run[-1] = (kind, f"{last}_{sub}")
            elif run[-1][1] in _DIGIT_FUNCS and side.startswith("2(", pos):
                run[-1] = ("func", _DIGIT_FUNCS[run[-1][1]])      # log2( / atan2(
                pos += 1
            elif side.startswith("(", pos) and not any(k == "func" for k, _ in run):
                free = [n for k, n in run if k == "var" and n not in VARS]
                if len(free) >= 2:
                    raise EquationError(f"Unknown function '{letters}' "
                                       f"(for variables write {'*'.join(letters)}(...))")
            tokens.extend(run)
        elif text == "(":
            tokens.append(("lp", text))
        elif text == ")":
            tokens.append(("rp", text))
        elif text == ",":
            tokens.append(("comma", text))
        else:
            tokens.append(("op", text))
    return tokens


def _split_alpha(run: str) -> list[tuple[str, str]]:
    """Greedy longest-name split: 'xsin' -> x sin, 'arcsin' -> asin; leftover letters are variables."""
    out: list[tuple[str, str]] = []
    i = 0
    while i < len(run):
        for name in _NAMES:
            if run.startswith(name, i):
                i += len(name)
                name = ALIASES.get(name, name)
                kind = "func" if name in FUNCS else "const" if name in CONSTS else "var"
                out.append((kind, name))
                break
        else:
            out.append(("var", run[i]))              # any other single letter is a free variable
            i += 1
    return out


_BEFORE_MUL = {"num", "var", "const", "rp"}
_AFTER_MUL = {"num", "var", "const", "func", "lp"}


def _insert_multiplication(tokens: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Insert '*' for implicit multiplication; a function must be followed by '('."""
    out: list[tuple[str, str]] = []
    for i, tok in enumerate(tokens):
        if tok[0] == "func" and (i + 1 >= len(tokens) or tokens[i + 1][0] != "lp"):
            raise EquationError("Use parentheses: sin(x)")
        if out and out[-1][0] in _BEFORE_MUL and tok[0] in _AFTER_MUL:
            out.append(("op", "*"))
        out.append(tok)
    return out


def _check_tree(tree: ast.AST) -> None:
    """Whitelist walk: only arithmetic, numbers, x/y/t/pi/e, variables and known functions."""
    if not isinstance(tree, ast.Expression):
        raise EquationError(_CANT_READ)
    call_funcs: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Expression, ast.Load, *_ALLOWED_BINOPS, *_ALLOWED_UNARY)):
            continue
        if isinstance(node, ast.BinOp) and isinstance(node.op, _ALLOWED_BINOPS):
            continue
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, _ALLOWED_UNARY):
            continue
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            continue
        if isinstance(node, ast.Name) and (node.id in (VARS | CONSTS) or _VAR_NAME_RE.match(node.id)):
            continue
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id in FUNCS and not node.keywords):
            arity = FUNC_ARITY[node.func.id]
            if len(node.args) not in arity:
                n = " or ".join(str(a) for a in arity)
                raise EquationError(f"{node.func.id} takes {n} argument{'' if arity == (1,) else 's'}")
            call_funcs.add(id(node.func))
            continue
        if isinstance(node, ast.Name) and id(node) in call_funcs:
            continue  # the func part of an allowed Call (ast.walk visits the Call first)
        raise EquationError(_CANT_READ)


def _side_to_expr(side: str) -> tuple[str, set[str], set[str]]:
    """Tokenize + implicit-mul one side; validate it; return (python expr, variables, functions)."""
    tokens = _insert_multiplication(_tokenize(side))
    expr = "".join(text for _, text in tokens)
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError:
        raise EquationError(_CANT_READ) from None
    _check_tree(tree)
    return (expr, {text for kind, text in tokens if kind == "var"},
            {text for kind, text in tokens if kind == "func"})


class _Floatify(ast.NodeTransformer):
    """Turn int constants into floats so huge integer powers can't hang the game."""

    def visit_Constant(self, node: ast.Constant) -> ast.AST:
        return ast.copy_location(ast.Constant(float(node.value)), node)


def parse_equation(text: str) -> ParsedEquation:
    """Parse player text into a ParsedEquation, or raise EquationError."""
    source, name = text.strip(), None
    m = re.match(_NAME_RE.format(n=config.NAME_MAX_LEN - 1), source)
    if m:
        name, source = m.group(1), m.group(2).strip()
    elif _NAME_LIKE_RE.match(source):
        raise EquationError(f"Name too long (max {config.NAME_MAX_LEN} characters)")
    if not source or len(source) > config.MAX_EQUATION_LEN:
        raise EquationError(f"Equation is empty / too long (max {config.MAX_EQUATION_LEN})")
    s = source.lower()
    for old, new in _REPLACEMENTS:
        s = s.replace(old, new)

    sides = s.split("=")
    if len(sides) > 2:
        raise EquationError("Only one '=' allowed")
    if any(not side.strip() for side in sides):
        raise EquationError("Missing expression on one side of '='")

    parts = [_side_to_expr(side) for side in sides]
    used: set[str] = set().union(*(p[1] for p in parts))
    funcs: set[str] = set().union(*(p[2] for p in parts))
    if not used & {"x", "y"}:
        raise EquationError("Equation needs x or y")

    if len(parts) == 2:
        expr = f"({parts[0][0]})-({parts[1][0]})"
    elif "y" in used:
        expr = f"({parts[0][0]})"
    else:
        expr = f"(y)-({parts[0][0]})"

    tree = ast.parse(expr, mode="eval")
    _check_tree(tree)
    tree = ast.fix_missing_locations(_Floatify().visit(tree))
    code = compile(tree, "<equation>", "eval")

    variables = frozenset(used - VARS)

    def func(x: np.ndarray, y: np.ndarray, t: float = 0.0,
             vars: dict[str, float] | None = None) -> np.ndarray:
        """Evaluate F(x, y, t); a variable missing from `vars` takes config.VAR_DEFAULT."""
        env = {**NS, "x": x, "y": y, "t": np.float64(t)}
        for v in variables:
            env[v] = np.float64(vars.get(v, config.VAR_DEFAULT) if vars else config.VAR_DEFAULT)
        with np.errstate(all="ignore"):
            v = eval(code, {"__builtins__": {}}, env)
            return np.broadcast_to(np.asarray(v, dtype=float), np.shape(x))

    try:
        probe = np.array([[-1.5, 0.5, 2.0]] * 3)
        func(probe, probe.T, 0.0, {v: 1.0 for v in variables})
    except Exception:
        raise EquationError("Can't evaluate equation") from None

    return ParsedEquation(source=source, expr=expr, uses_t="t" in used, func=func, name=name,
                         funcs=frozenset(funcs), variables=variables)
