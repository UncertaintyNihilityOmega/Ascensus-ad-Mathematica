"""Parser tests: DESIGN section 5 examples, syntax variations, and rejections."""
import numpy as np
import pytest

from ascensus.mathparse import FormulaError, parse_formula

X = np.array([[-2.0, -0.5, 1.5, 3.0]])
Y = np.array([[1.0, 2.0, -3.0, 0.5]])


def F(text, t=0.0):
    return parse_formula(text).func(X, Y, t)


MUST_PASS = [
    "x^2", "x^3", "x = 2", "x = -4", "1 = x^2 + y^2", "sin(x)", "cos(x)", "x^(1/2)",
    "tan(sqrt(x^2 + y^2)) = y / x", "y = 2sin(x + t)", "x^2 + y^2 = (t % 5)^2",
]
VARIATIONS = ["2x", "3sin(x)", "(x+1)(x-1)", "xy=1", "y=2pi", "y=x^(1/2)", "√(x)", "X^2",
              "y = -x^2 + 3"]
REJECTS = ["sin x", "x==2", "2=3", "import os", "__import__('os')", "x.real", "foo(x)",
           "sin(x,y)", "", "x" * 121]


@pytest.mark.parametrize("text", MUST_PASS + VARIATIONS)
def test_accepts(text):
    pf = parse_formula(text)
    assert pf.func(X, Y, 0.0).shape == X.shape


@pytest.mark.parametrize("text", REJECTS)
def test_rejects(text):
    with pytest.raises(FormulaError):
        parse_formula(text)


def test_meaning_y_equals_expr():
    assert np.allclose(F("x^2"), Y - X**2)
    assert np.allclose(F("y = -x^2 + 3"), Y - (-X**2 + 3))


def test_meaning_expr_with_y_is_zero():
    assert np.allclose(F("x^2 + y^2 - 1"), X**2 + Y**2 - 1)


def test_meaning_two_sides():
    assert np.allclose(F("x = 2"), X - 2)
    assert np.allclose(F("1 = x^2 + y^2"), 1 - (X**2 + Y**2))


def test_implicit_multiplication():
    assert np.allclose(F("y=2x"), Y - 2 * X)
    assert np.allclose(F("y=3sin(x)"), Y - 3 * np.sin(X))
    assert np.allclose(F("y=(x+1)(x-1)"), Y - (X + 1) * (X - 1))
    assert np.allclose(F("xy=1"), X * Y - 1)
    assert np.allclose(F("y=2pi"), Y - 2 * np.pi)
    assert np.allclose(F("y=2pix"), Y - 2 * np.pi * X)
    assert np.allclose(F("y=xsin(x)"), Y - X * np.sin(X))
    assert np.allclose(F("y=exp(x)"), Y - np.exp(X))


def test_unicode_and_case():
    assert np.allclose(F("y = π x"), Y - np.pi * X)
    assert np.allclose(F("Y = X×2"), Y - X * 2)
    assert np.allclose(F("y = X ÷ 2 − 1"), Y - (X / 2 - 1))
    assert np.allclose(F("y=√(x)"), F("y=sqrt(x)"), equal_nan=True)
    assert np.allclose(F("y = x ** 2"), Y - X**2)


def test_sqrt_power_is_nan_for_negative_x():
    v = F("y=x^(1/2)")
    assert np.isnan(v[0, 0]) and np.isfinite(v[0, 2])


def test_t_flag_and_use():
    assert parse_formula("y = 2sin(x + t)").uses_t
    assert not parse_formula("y = sin(x)").uses_t
    assert np.allclose(F("y = t", t=2.5), Y - 2.5)
    assert np.allclose(F("x^2 + y^2 = (t % 5)^2", t=7.0), X**2 + Y**2 - 4.0)


def test_bare_constant_needs_x_or_y():
    with pytest.raises(FormulaError, match="needs x or y"):
        parse_formula("2pi")


def test_error_messages():
    for text, msg in [("sin x", "parentheses"), ("x==2", "Only one"), ("2=3", "needs x or y"),
                      ("foo(x)", "Unknown function"), ("x.real", "Unexpected character"),
                      ("x=", "Missing expression"), ("", "empty"), ("x+", "read"),
                      ("1/0 + x", "evaluate")]:
        with pytest.raises(FormulaError, match=msg):
            parse_formula(text)


def test_huge_power_cannot_hang():
    with pytest.raises(FormulaError):
        parse_formula("y=9^9^9^9^9")


def test_no_builtins_or_attribute_access():
    # ("lambda: x" is a named equation and "x if y else 1" a product of variables: both harmless)
    for bad in ["x.__class__", "(x)[0]", "lambda x: x", "x ? y : 1", "[x]", "'a'", "x, y", "(1, x)"]:
        with pytest.raises(FormulaError):
            parse_formula(bad)


def test_source_is_stripped():
    assert parse_formula("  x^2  ").source == "x^2"
