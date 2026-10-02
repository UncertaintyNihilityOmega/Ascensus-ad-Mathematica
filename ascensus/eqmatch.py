"""Is a typed equation "the same curve" as a pattern? Used by the equation achievements. No pygame.

Two equations F_user = 0 and F_pattern = 0 match when F_user is a constant non-zero multiple of F_pattern
at a set of sample points, for some renaming of the user's variables onto the pattern's (so sides may be
swapped, terms rearranged, the whole equation scaled, and "a" may be called "c" or "k_1").
"""
from __future__ import annotations

import itertools
from functools import lru_cache

import numpy as np

from .mathparse import EquationError, ParsedEquation, parse_equation

SAMPLES = 64            # sample points per check
MIN_VALID = 16          # finite, non-zero samples needed to decide
REL_TOL = 1e-6          # how constant the ratio F_user / F_pattern must be
_XY = np.random.default_rng(20261002).uniform(-6.0, 6.0, (2, SAMPLES))
_VALUES = np.random.default_rng(7).uniform(0.6, 2.4, (2, 8))
_VAR_SETS = np.stack([_VALUES[0], -_VALUES[1]])    # one positive and one negative variable assignment


@lru_cache(maxsize=None)
def pattern(text: str) -> ParsedEquation:
    """The parsed pattern (cached; the patterns are constants of the game)."""
    return parse_equation(text)


def _proportional(fu: np.ndarray, fp: np.ndarray) -> bool:
    """fu == k * fp for one non-zero k (zeros of fp must be zeros of fu)."""
    ok = np.isfinite(fu) & np.isfinite(fp)
    if ok.sum() < MIN_VALID:
        return False
    fu, fp = fu[ok], fp[ok]
    scale = float(np.abs(fp).max())
    if scale == 0.0:
        return False
    nz = np.abs(fp) > 1e-9 * scale
    if nz.sum() < MIN_VALID:
        return False
    ratio = fu[nz] / fp[nz]
    k = float(np.median(ratio))
    if not np.isfinite(k) or abs(k) < 1e-12:
        return False
    if np.any(np.abs(ratio - k) > REL_TOL * abs(k)):
        return False
    return bool(np.all(np.abs(fu[~nz]) <= REL_TOL * abs(k) * scale))


def equivalent(user: ParsedEquation, target: ParsedEquation) -> bool:
    """True when `user` draws the same curve as `target` (see the module docstring)."""
    uv, pv = sorted(user.variables), sorted(target.variables)
    if len(uv) != len(pv) or user.uses_t != target.uses_t or len(pv) > _VAR_SETS.shape[1]:
        return False
    x, y = _XY
    with np.errstate(all="ignore"):
        targets = []
        for values in _VAR_SETS:
            pvars = dict(zip(pv, values))
            fp = np.asarray(target.func(x, y, 0.0, pvars), dtype=float)
            if np.isfinite(fp).sum() >= MIN_VALID:             # e.g. sqrt(a) is undefined for a < 0
                targets.append((pvars, fp))
        if not targets:
            return False
        for perm in itertools.permutations(uv):
            if all(_proportional(np.asarray(user.func(x, y, 0.0, {u: pvars[p] for u, p in zip(perm, pv)}),
                                            dtype=float), fp)
                   for pvars, fp in targets):
                return True
    return False


def matches(user: ParsedEquation, text: str) -> bool:
    """equivalent() against a pattern given as text; a pattern that does not parse never matches."""
    try:
        return equivalent(user, pattern(text))
    except EquationError:
        return False
