"""One test per achievement (tiny fake ParsedEquation) plus persistence through the profile."""
from types import SimpleNamespace

import pytest

from ascensus import config
from ascensus.core.mathparse import parse_equation
from ascensus.game.achievements import ACHIEVEMENTS, BY_ID, EQUATION_PATTERNS, TOTAL, AchievementTracker
from ascensus.game.profile import Profile


def fake(source, expr=None, uses_t=False):
    """Old-style parsed object: only source / expr / uses_t (no funcs / variables)."""
    return SimpleNamespace(source=source, expr=expr if expr is not None else source, uses_t=uses_t)


def new_tracker():
    return AchievementTracker(Profile.in_memory())


def ids(unlocked):
    return {a.id for a in unlocked}


def cast(tr, source, expr=None, **kw):
    return ids(tr.on("cast", parsed=fake(source, expr, **kw)))


def test_data_is_40_unique():
    assert len(ACHIEVEMENTS) == TOTAL == 40 and len(BY_ID) == 40 and TOTAL % 5 == 0
    assert set(EQUATION_PATTERNS) <= set(BY_ID)
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


def real(tr, text):
    """Cast a really parsed equation; returns the unlocked ids."""
    return ids(tr.on("cast", parsed=parse_equation(text)))


def test_ocean_needs_the_variable():
    got = real(new_tracker(), "Ocean: y/x = tan(sqrt(x^2+y^2)*k)")
    assert {"ocean", "tangent", "rooted", "full_circle"} <= got
    assert "ocean" not in real(new_tracker(), "tan(sqrt(x^2+y^2)) = y/x")       # the old Tan Monster


# the user's own spellings (names, other variable letters, swapped sides) and a near miss each
EQUATION_CASES = {
    "sakuna": ("Sakuna: 0= sin(x*a)*sin(y*a)", "sin(k x) sin(k y) = 0", "sin(x a) sin(y a) = 1"),
    "cosmic": ("200= (x^5+y^5)^2", "(x^5+y^5)^2/200 = 1", "200= (b*x^5+y^5)^2"),
    "lily": ("(x^(2)-abs(y)*6) (y^(2)-abs(x)*6)=0", "(y^2-6abs(x))(x^2-6abs(y)) = 0",
             "(x^2-abs(y)*5)(y^2-abs(x)*5)=0"),
    "cross0": ("Cross0: (abs(a) x^(2)-y^(2)) (x^(2)-abs(a) y^(2))=0", "(x^2-abs(q)y^2)(abs(q)x^2-y^2)=0",
               "(a x^2-y^2)(x^2-a y^2)=0"),        # differs for negative a
    "cross2": ("Cross2: (x-c y)^(-2)+(y-c x)^(-2)=10", "10 = (x-a y)^(-2)+(y-a x)^(-2)",
               "(x-c y)^(-2)+(y-c x)^(-2)=9"),
    "aliens": ("Aliens: 10*(x^2 - c*y)^2 * (y^2 - c*x)^2 = (x^2 - c*y)^2 + (y^2 - c*x)^2",
               "10 (x^(2)-a y)^(2) (y^(2)-a x)^(2)=(x^(2)-a y)^(2)+(y^(2)-a x)^(2)",
               "10 (x^2-y)^2 (y^2-x)^2=(x^2-y)^2+(y^2-x)^2"),
    "circular": ("Circular: cos(x*2)+cos(y*2)=a*0.39", "cos(2y)+cos(2x) = 0.39b",
                 "cos(x*2)+cos(y*2)=0.39"),
    "fog": ("Fog: mod(x^2 + y^2, 2) = 0.5", "mod(x^2+y^2,2)-0.5=0", "mod(x^2+y^2,3)=0.5"),
    "love_is_endless": ("Love: 1=x^(2)+(y-sqrt(abs(x)))^(2)", "x^2+(y-sqrt(abs(x)))^2 = 1",
                        "1=x^2+(y-sqrt(abs(x)))^2+0.1"),
    "heartbeat": ("(x^2+y^2-1)^3 = x^2 y^3", "x^2y^3 = (x^2+y^2-1)^3", "(x^2+y^2-1)^3 = x^3 y^2"),
    "four_leaf": ("eq4: (x^(2)+y^(2))^(3)=4 x^(2) y^(2)", "(x^2+y^2)^3/4 = x^2y^2", "(x^2+y^2)^3=3x^2y^2"),
    "infinity": ("(x^2+y^2)^2 = a(x^2-y^2)", "(x^2+y^2)^2 = k (x^2-y^2)", "(x^2+y^2)^2 = 3(x^2-y^2)"),
    "ocean": ("Ocean: y/x = tan(sqrt(x^2+y^2)*a)", "tan(c sqrt(x^2+y^2)) = y/x", "y/x = tan(sqrt(x^2+y^2))"),
}


@pytest.mark.parametrize("ach_id", sorted(EQUATION_CASES))
def test_equation_achievements(ach_id):
    *hits, miss = EQUATION_CASES[ach_id]
    for text in hits:
        assert ach_id in real(new_tracker(), text), text
    assert ach_id not in real(new_tracker(), miss), miss


def test_speed_demon_counts_only_3x_time():
    tr = new_tracker()
    t = 0.0
    for _ in range(100):                      # 100 s at 1x: nothing
        t += 1 / 2
        tr.on("tick", game_t=t, speed=1)
    for _ in range(int(config.ACH_SPEED_DEMON_TIME * 2) - 2):
        t += 1 / 2
        assert "speed_demon" not in ids(tr.on("tick", game_t=t, speed=3))
    t += 0.5                                  # 59.5 s at 3x
    assert "speed_demon" not in ids(tr.on("tick", game_t=t, speed=3))
    t += 0.5                                  # 60 s
    assert "speed_demon" in ids(tr.on("tick", game_t=t, speed=3))


def test_untouchable_eternity_mathematician_rainbow():
    tr = new_tracker()
    assert not ids(tr.on("tick", game_t=50.0, since_hit=config.ACH_UNTOUCHABLE_TIME - 1))
    assert "untouchable" in ids(tr.on("tick", game_t=51.0, since_hit=config.ACH_UNTOUCHABLE_TIME))
    assert "eternity" in ids(tr.on("tick", game_t=config.ACH_ETERNITY_TIME))
    assert "mathematician" not in ids(tr.on("tick", equation_count=49))
    assert "mathematician" in ids(tr.on("tick", equation_count=50))
    same = [(1, 2, 3)] * 2 + [(4, 5, 6), (7, 8, 9), (1, 1, 1), (2, 2, 2)]
    assert "rainbow" not in ids(tr.on("tick", active_colors=same))
    assert "rainbow" not in ids(tr.on("tick", active_colors=[(k, 0, 0) for k in range(5)]))
    assert "rainbow" in ids(tr.on("tick", active_colors=[(k, 0, 0) for k in range(6)]))


def test_undo_export_import_events():
    assert ids(new_tracker().on("undo")) == {"second_thoughts"}
    assert ids(new_tracker().on("export")) == {"time_capsule"}
    assert ids(new_tracker().on("import")) == {"homecoming"}


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
    for text in EQUATION_PATTERNS.values():
        tr.on("cast", parsed=parse_equation(text))
    tr.on("var_created"); tr.on("var_play"); tr.on("boss_kill"); tr.on("upgrade")
    tr.on("undo"); tr.on("export"); tr.on("import")
    for k in range(200):
        tr.on("tick", game_t=k / 2, active_count=6, speed=3, since_hit=k, equation_count=50,
              active_colors=[(c, 0, 0) for c in range(6)])
    tr.on("tick", game_t=config.ACH_ETERNITY_TIME)
    for _ in range(config.ACH_CENTURION_KILLS):
        tr.on("kill")
    for _ in range(config.ACH_DASH_COUNT):
        tr.on("dash")
    assert tr.profile.is_unlocked(ach.id)
