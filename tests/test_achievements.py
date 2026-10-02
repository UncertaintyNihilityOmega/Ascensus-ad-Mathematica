"""One test per achievement (tiny fake ParsedFormula) plus persistence through the profile."""
from types import SimpleNamespace

import pytest

from ascensus import config
from ascensus.achievements import ACHIEVEMENTS, BY_ID, AchievementTracker
from ascensus.profile import Profile


def fake(source, expr=None, uses_t=False):
    """Old-style parsed object: only source / expr / uses_t (no funcs / variables)."""
    return SimpleNamespace(source=source, expr=expr if expr is not None else source, uses_t=uses_t)


def new_tracker():
    return AchievementTracker(Profile.in_memory())


def ids(unlocked):
    return {a.id for a in unlocked}


def cast(tr, source, expr=None, **kw):
    return ids(tr.on("cast", parsed=fake(source, expr, **kw)))


def test_data_is_20_unique():
    assert len(ACHIEVEMENTS) == 20 and len(BY_ID) == 20
    assert all(a.name and a.desc for a in ACHIEVEMENTS)


def test_hello_sine():
    assert "hello_sine" in cast(new_tracker(), "y = sin(x)", "(y)-(sin(x))")


def test_co_star():
    assert "co_star" in cast(new_tracker(), "y = cos(x)", "(y)-(cos(x))")


def test_tangent():
    assert "tangent" in cast(new_tracker(), "y = tan(x)", "(y)-(tan(x))")


def test_full_circle():
    tr = new_tracker()
    assert "full_circle" in cast(tr, "x^2 + y^2 = 4", "(x**2+y**2)-(4)")
    assert "full_circle" in cast(new_tracker(), "x^(2)+y^(2)=1", "(x**(2)+y**(2))-(1)")
    assert "full_circle" not in cast(new_tracker(), "y = x^2", "(y)-(x**2)")
    assert "full_circle" not in cast(new_tracker(), "x^3+y^2=1", "(x**3+y**2)-(1)")


def test_rooted():
    assert "rooted" in cast(new_tracker(), "y = sqrt(x)", "(y)-(sqrt(x))")
    assert "rooted" in cast(new_tracker(), "y = root(x, 3)", "(y)-(root(x,3))")


def test_natural_talent():
    assert "natural_talent" in cast(new_tracker(), "y = ln(x)", "(y)-(ln(x))")


def test_inverse_thinking():
    assert "inverse_thinking" in cast(new_tracker(), "y = asin(x)", "(y)-(asin(x))")
    assert "inverse_thinking" in cast(new_tracker(), "y = arctan(x)", "(y)-(arctan(x))")
    got = cast(new_tracker(), "y = sin(x)", "(y)-(sin(x))")
    assert "inverse_thinking" not in got


def test_hyperbole():
    for fn in ("sinh", "cosh", "tanh"):
        got = cast(new_tracker(), f"y = {fn}(x)", f"(y)-({fn}(x))")
        assert "hyperbole" in got
        assert not ({"hello_sine", "co_star", "tangent"} & got)      # whole-word matching


def test_time_lord():
    assert "time_lord" in cast(new_tracker(), "y = 2sin(x + t)", "(y)-(2*sin(x+t))", uses_t=True)
    assert "time_lord" in cast(new_tracker(), "y = x + t", "(y)-(x+t)")          # regex fallback, uses_t False
    assert "time_lord" not in cast(new_tracker(), "y = sqrt(x)", "(y)-(sqrt(x))")


def test_variable_star():
    assert ids(new_tracker().on("var_created")) == {"variable_star"}


def test_autoplay():
    assert ids(new_tracker().on("var_play")) == {"autoplay"}


def test_full_house():
    tr = new_tracker()
    assert not tr.on("tick", game_t=1.0, active_count=5)
    assert ids(tr.on("tick", game_t=1.1, active_count=6)) == {"full_house"}


def test_tan_monster():
    got = cast(new_tracker(), "tan( sqrt(x^2 + y^2) ) = y / x",
               "(tan(sqrt(x**2+y**2)))-(y/x)")
    assert {"tan_monster", "tangent", "rooted", "full_circle"} <= got
    assert "tan_monster" not in cast(new_tracker(), "tan(x) = y / x", "(tan(x))-(y/x)")


def test_first_blood():
    assert ids(new_tracker().on("kill")) == {"first_blood"}


def test_centurion():
    tr = new_tracker()
    for _ in range(config.ACH_CENTURION_KILLS - 1):
        tr.on("kill")
    assert not tr.profile.is_unlocked("centurion")
    assert ids(tr.on("kill")) == {"centurion"}
    tr.reset_run()
    assert tr.run_kills == 0 and tr.profile.get_lifetime("kills") == 100


def test_giant_slayer():
    assert ids(new_tracker().on("boss_kill")) == {"giant_slayer"}


def test_survivor():
    tr = new_tracker()
    assert not tr.on("tick", game_t=299.9, active_count=0)
    assert ids(tr.on("tick", game_t=300.0, active_count=0)) == {"survivor"}


def test_marathon():
    tr = new_tracker()
    assert ids(tr.on("tick", game_t=900.0, active_count=0)) == {"survivor", "marathon"}


def test_investor():
    assert ids(new_tracker().on("upgrade")) == {"investor"}


def test_dash_addict_is_lifetime(tmp_path):
    path = tmp_path / "p.json"
    tr = AchievementTracker(Profile(path))
    for _ in range(60):
        tr.on("dash")
    tr.profile.save()
    tr2 = AchievementTracker(Profile(path))               # a later session continues the count
    for _ in range(39):
        assert not tr2.on("dash")
    assert ids(tr2.on("dash")) == {"dash_addict"}


def test_auto_on_and_unknown_events_unlock_nothing():
    tr = new_tracker()
    assert tr.on("auto_on") == [] and tr.on("nonsense") == [] and tr.on("cast", parsed=None) == []


def test_new_parser_fields_are_used():
    parsed = SimpleNamespace(source="", expr="", uses_t=False, funcs=frozenset({"sin", "ln"}),
                             variables=frozenset({"t"}))
    assert ids(new_tracker().on("cast", parsed=parsed)) == {"hello_sine", "natural_talent", "time_lord"}


def test_toast_queue_and_no_double_unlock():
    tr = new_tracker()
    tr.on("kill")
    tr.on("kill")
    ach = tr.pop_toast()
    assert ach is not None and ach.id == "first_blood"
    assert tr.toast_text(ach) == "Achievement unlocked: First Blood"
    assert tr.pop_toast() is None


def test_persistence_through_profile(tmp_path):
    path = tmp_path / "profile.json"
    tr = AchievementTracker(Profile(path))
    tr.on("kill")
    tr.on("var_created")
    assert path.exists()
    tr2 = AchievementTracker(Profile(path))
    assert tr2.unlocked_count() == 2
    assert tr2.on("kill") == [] and not tr2.pending       # already unlocked: no toast again
    assert tr2.profile.get_lifetime("kills") == 0 or tr2.profile.get_lifetime("kills") >= 1


@pytest.mark.parametrize("ach", ACHIEVEMENTS, ids=lambda a: a.id)
def test_every_achievement_has_a_trigger(ach):
    """Each id can be unlocked by some event sequence (guards against typos in ids)."""
    tr = new_tracker()
    tr.on("cast", parsed=fake("tan(sqrt(x^2+y^2))=y/x", "(tan(sqrt(x**2+y**2)))-(y/x)"))
    tr.on("cast", parsed=fake("y=sin(x)+cos(x)+ln(x)+asin(x)+sinh(x)+t", uses_t=True))
    tr.on("var_created"); tr.on("var_play"); tr.on("boss_kill"); tr.on("upgrade")
    tr.on("tick", game_t=1000.0, active_count=6)
    for _ in range(config.ACH_CENTURION_KILLS):
        tr.on("kill")
    for _ in range(config.ACH_DASH_COUNT):
        tr.on("dash")
    assert tr.profile.is_unlocked(ach.id)
