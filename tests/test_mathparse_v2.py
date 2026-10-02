"""Parser v2 tests (P7): functions, aliases, arity, variables, heuristic, named equations."""
import numpy as np
import pytest

from ascensus import config
from ascensus.mathparse import FormulaError, parse_formula

pytestmark = pytest.mark.filterwarnings("ignore::RuntimeWarning")

X = np.array([[-2.0, -0.5, 1.5, 3.0]])
Y = np.array([[1.0, 2.0, -3.0, 0.5]])
P = np.array([[0.3, 0.7, 0.9, 0.5]])           # inside (-1, 1) for the inverse trig functions
Q = np.array([[2.0, 3.0, 0.5, 1.5]])


def val(expr, x=P, y=Q, **kw):
    """F for 'y = expr' is y - F = expr, so expr = y - F."""
    return y - parse_formula("y = " + expr).func(x, y, **kw)


ONE_ARG_CASES = {
    "sin": np.sin, "cos": np.cos, "tan": np.tan,
    "sec": lambda a: 1 / np.cos(a), "csc": lambda a: 1 / np.sin(a), "cot": lambda a: 1 / np.tan(a),
    "asin": np.arcsin, "acos": np.arccos, "atan": np.arctan,
    "asec": lambda a: np.arccos(1 / a), "acsc": lambda a: np.arcsin(1 / a),
    "acot": lambda a: np.pi / 2 - np.arctan(a),
    "sinh": np.sinh, "cosh": np.cosh, "tanh": np.tanh,
    "asinh": np.arcsinh, "acosh": lambda a: np.arccosh(a + 1), "atanh": np.arctanh,
    "sqrt": np.sqrt, "cbrt": np.cbrt, "abs": np.abs, "sign": np.sign,
    "floor": np.floor, "ceil": np.ceil, "round": np.round,
    "exp": np.exp, "ln": np.log, "log": np.log10, "log2": np.log2,
}


@pytest.mark.parametrize("name", sorted(ONE_ARG_CASES))
def test_one_arg_function(name):
    arg = "x+1" if name == "acosh" else "x"
    assert np.allclose(val(f"{name}({arg})"), ONE_ARG_CASES[name](P), equal_nan=True)
    assert parse_formula(f"y = {name}({arg})").funcs == {name}


ALIAS_CASES = [("arcsin", "asin"), ("arccos", "acos"), ("arctan", "atan"), ("arcsec", "asec"),
               ("arccsc", "acsc"), ("arccot", "acot"), ("arsinh", "asinh"), ("arcsinh", "asinh"),
               ("arcosh", "acosh"), ("arccosh", "acosh"), ("artanh", "atanh"),
               ("arctanh", "atanh"), ("sgn", "sign"), ("in", "ln")]


@pytest.mark.parametrize("alias,canon", ALIAS_CASES)
def test_aliases(alias, canon):
    arg = "x+1" if canon == "acosh" else "x"
    pa, pc = parse_formula(f"y = {alias}({arg})"), parse_formula(f"y = {canon}({arg})")
    assert np.allclose(pa.func(P, Q), pc.func(P, Q), equal_nan=True)
    assert pa.funcs == {canon}


def test_two_arg_functions():
    assert np.allclose(val("min(x, y)"), np.minimum(P, Q))
    assert np.allclose(val("max(x, y)"), np.maximum(P, Q))
    assert np.allclose(val("mod(y, x)"), np.mod(Q, P))
    assert np.allclose(val("hypot(x, y)"), np.hypot(P, Q))
    assert np.allclose(val("atan2(y, x)"), np.arctan2(Q, P))
    assert np.allclose(val("arctan2(y, x)"), np.arctan2(Q, P))
    assert np.allclose(val("atan2(x, 2)"), np.arctan2(P, 2.0))
    assert parse_formula("y = arctan2(y, x)").funcs == {"atan2"}


def test_root():
    x = np.array([[-8.0, 8.0, -4.0, 4.0]])
    assert np.allclose(val("root(3, x)", x=x), [[-2.0, 2.0, -(4 ** (1 / 3)), 4 ** (1 / 3)]])
    r2 = val("root(2, x)", x=x)
    assert np.isnan(r2[0, 0]) and np.isnan(r2[0, 2]) and np.isclose(r2[0, 1], 8 ** 0.5)
    assert np.isnan(val("root(1/2, x)", x=x)[0, 0])             # non-integer n: negative x is nan


def test_log_one_and_two_args():
    assert np.allclose(val("log(2, x)", x=Q), np.log2(Q))
    assert np.allclose(val("log(10, x)", x=Q), np.log10(Q))
    assert np.allclose(val("log(x)"), np.log10(P))               # one argument: base 10
    assert np.allclose(val("log2(x)"), np.log2(P))
    assert np.allclose(val("xlog2(x)"), P * np.log2(P))


@pytest.mark.parametrize("text,msg", [
    ("sin(x, y)", "sin takes 1 argument"), ("sqrt()", "sqrt takes 1 argument"),
    ("min(x)", "min takes 2 arguments"), ("max(x, y, 1)", "max takes 2 arguments"),
    ("hypot(x)", "hypot takes 2"), ("atan2(x)", "atan2 takes 2"), ("root(x)", "root takes 2"),
    ("mod(1, 2, 3)", "mod takes 2"), ("log(1, 2, 3)", "log takes 1 or 2 arguments"),
    ("log()", "log takes 1 or 2 arguments"),
])
def test_arity_errors(text, msg):
    with pytest.raises(FormulaError, match=msg):
        parse_formula("y = " + text)


def test_comma_rules():
    for bad in ["y = (x, 1)", "y = x, 1", "y = max(,x)", "y = max(x,)", "y = max(x,,1)"]:
        with pytest.raises(FormulaError):
            parse_formula(bad)
    assert np.allclose(val("max(2x, 3y)"), np.maximum(2 * P, 3 * Q))     # no '*' next to commas
    assert np.allclose(val("max(x, y) min(x, y)"), np.maximum(P, Q) * np.minimum(P, Q))


def test_variables():
    pf = parse_formula("y = a x + b")
    assert pf.variables == {"a", "b"} and not pf.uses_t
    assert np.allclose(pf.func(P, Q, 0.0, {"a": 2.0, "b": 3.0}), Q - (2 * P + 3))
    assert np.allclose(pf.func(P, Q, 0.0, {"a": 2.0}), Q - (2 * P + config.VAR_DEFAULT))  # b missing
    assert np.allclose(pf.func(P, Q), Q - (config.VAR_DEFAULT * P + config.VAR_DEFAULT))
    assert parse_formula("y = x").variables == frozenset()
    assert parse_formula("y = t x + e").variables == frozenset()     # t and e are not variables
    assert config.VAR_DEFAULT == 1.0


def test_variable_default_is_read_at_use_time(monkeypatch):
    pf = parse_formula("y = a x")
    monkeypatch.setattr(config, "VAR_DEFAULT", 4.0)
    assert np.allclose(pf.func(P, Q), Q - 4.0 * P)


def test_variable_subscripts_and_runs():
    pf = parse_formula("y = a_1 x + b_12")
    assert pf.variables == {"a_1", "b_12"}
    assert np.allclose(pf.func(P, Q, 0.0, {"a_1": 2.0, "b_12": 1.0}), Q - (2 * P + 1))
    pf = parse_formula("ab_1 y = x")
    assert pf.variables == {"a", "b_1"}
    assert np.allclose(pf.func(P, Q, 0.0, {"a": 2.0, "b_1": 3.0}), 6 * Q - P)
    assert parse_formula("y = a2 x").variables == {"a"}              # a2 is a * 2
    assert parse_formula("y = sin(k x)").variables == {"k"}
    for bad in ["y = x_1", "y = t_2", "y = sin_1(x)", "y = pi_1 x"]:
        with pytest.raises(FormulaError, match="subscript"):
            parse_formula(bad)


def test_variable_needs_x_or_y():
    with pytest.raises(FormulaError, match="needs x or y"):
        parse_formula("a = b")


def test_unknown_function_heuristic():
    with pytest.raises(FormulaError,
                       match=r"Unknown function 'sni' \(for variables write s\*n\*i\(\.\.\.\)\)"):
        parse_formula("y = sni(x)")
    with pytest.raises(FormulaError, match="Unknown function 'foo'"):
        parse_formula("foo(x)")
    assert parse_formula("y = a(x+1)").variables == {"a"}           # one variable then '(': a * (x+1)
    assert parse_formula("y = ab (x)").variables == {"a", "b"}      # a space: not directly followed
    assert parse_formula("y = xsin(x)").funcs == {"sin"}
    assert parse_formula("y = a*b(x)").variables == {"a", "b"}


def test_funcs_field():
    pf = parse_formula("y = sin(x) + arcsin(x) + cos(ln(x)) + log(2, x)")
    assert pf.funcs == {"sin", "asin", "cos", "ln", "log"}
    assert parse_formula("x^2 + y^2 = 1").funcs == frozenset()


def test_limit_is_120_on_the_body():
    assert config.MAX_FORMULA_LEN == 120
    parse_formula("y=" + "x" * 118)                                           # exactly 120
    with pytest.raises(FormulaError, match="too long"):
        parse_formula("y=" + "x" * 119)
    parse_formula("eq1: y=" + "x" * 118)                                      # the name is not counted
    with pytest.raises(FormulaError, match="too long"):
        parse_formula("eq1: y=" + "x" * 119)


EQ4 = "eq4: (x^(2)+y^(2))^(3)=4 x^(2) y^(2)"


def test_named_equations():
    pf = parse_formula(EQ4)
    assert pf.name == "eq4" and pf.source == "(x^(2)+y^(2))^(3)=4 x^(2) y^(2)"
    assert pf.text == EQ4 and not pf.uses_t and pf.variables == frozenset()
    assert np.allclose(pf.func(X, Y), (X**2 + Y**2) ** 3 - 4 * X**2 * Y**2)
    pf = parse_formula("r1: x^2+y^2=1")
    assert pf.name == "r1" and pf.source == "x^2+y^2=1" and pf.text == "r1: x^2+y^2=1"
    assert np.allclose(pf.func(X, Y), X**2 + Y**2 - 1)


def test_name_syntax():
    pf = parse_formula("  My_Curve2 :  y = x ")
    assert pf.name == "My_Curve2" and pf.source == "y = x" and pf.text == "My_Curve2: y = x"
    assert parse_formula("y = x").name is None and parse_formula("y = x").text == "y = x"
    parse_formula("a234567890123456: y = x")                                  # 16 characters
    with pytest.raises(FormulaError, match="Name too long"):
        parse_formula("a2345678901234567: y = x")
    for bad in ["eq4:", "eq4:   ", "1ab: y = x", ": y = x", "eq 4: y = x", "eq4: y = x: 2"]:
        with pytest.raises(FormulaError):
            parse_formula(bad)


def test_named_body_follows_all_normal_rules():
    with pytest.raises(FormulaError, match="needs x or y"):
        parse_formula("c: 2pi")
    with pytest.raises(FormulaError, match="Only one"):
        parse_formula("c: x==2")

