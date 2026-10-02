"""Library data: every parser function/alias is documented, every example parses and renders."""
import numpy as np
import pytest

from ascensus.core import mathparse
from ascensus.core.curvefield import build_curve
from ascensus.core.mathparse import parse_equation
from ascensus.data import library_data as lib


def test_every_function_and_alias_is_documented():
    names = {f["name"] for f in lib.FUNCTIONS}
    aliases = {a for f in lib.FUNCTIONS for a in f["aliases"]}
    assert names == set(mathparse.FUNCS)                      # no missing and no invented functions
    assert aliases == set(mathparse.ALIASES)
    for f in lib.FUNCTIONS:
        for a in f["aliases"]:
            assert mathparse.ALIASES[a] == f["name"], (a, f["name"])
    assert len(names) == len(lib.FUNCTIONS)


def test_card_fields_present():
    for f in lib.FUNCTIONS:
        assert set(f) >= {"name", "aliases", "syntax", "explanation", "example", "group"}
        assert f["syntax"].startswith(f["name"]) and f["explanation"].strip() and f["group"]


def test_other_tabs_have_content():
    assert lib.TABS == ["Functions", "Syntax", "Variables", "Combat", "Upgrades & XP",
                        "Enemies & Bosses", "Controls"]
    for tab in lib.TABS[1:]:
        paras = lib.paragraphs(tab)
        assert paras, tab
        for title, lines in paras:
            assert title and lines and all(isinstance(l, str) and l for l in lines)


def test_controls_mention_every_key():
    text = " ".join(l for _, lines in lib.paragraphs("Controls") for l in lines)
    for token in ("WASD", "arrow", "Enter", "J ", "G ", "F3", "F11", "Esc", "Ctrl+V", "Ctrl+C", "Ctrl+X", "Ctrl+A"):
        assert token in text, token


@pytest.mark.parametrize("card", lib.FUNCTIONS, ids=lambda f: f["name"])
def test_example_parses_uses_function_and_renders(card):
    p = parse_equation(card["example"])
    assert p.funcs & ({card["name"]} | set(card["aliases"]) | {mathparse.ALIASES.get(card["name"], card["name"])}), \
        "the example does not use its own function"
    src = card["example"].lower()
    assert "x" in src or "y" in src
    curve = build_curve(p.func, 0.0, size=(200, 120), unit=20)
    assert curve.points.shape[1] == 2
    assert len(curve.points) > 5, "the mini graph would be empty"
    assert np.isfinite(curve.points).all()
