"""EquationManager tests (no save/load yet): list ops, active set, status, pulses, t-rebuild."""
import numpy as np
import pytest

from ascensus import config, view
from ascensus.enemies import Swarm
from ascensus.equations import EquationManager, pulse_damage
from ascensus.mathparse import EquationError

ORIGIN = np.zeros(2)


def mgr(*texts):
    m = EquationManager()
    for t in texts:
        m.add(t)
    return m


def swarm_at(*screen_pts):
    """Swarm whose enemies sit at the given screen points (player at world origin)."""
    sw = Swarm(np.random.default_rng(0))
    for _ in screen_pts:
        sw.spawn(ORIGIN, 0.0)
    sw.pos = np.array(screen_pts, float).reshape(-1, 2) - np.array((view.W / 2, view.H / 2))
    return sw


def test_add_errors_and_colors():
    m = mgr("x^2", "sin(x)")
    assert [e.color for e in m.entries] == config.CURVE_PALETTE_AUTO[:2]
    with pytest.raises(EquationError):
        m.add("sin x")
    assert len(m.entries) == 2
    m.delete(0)
    assert m.add("cos(x)").color == config.CURVE_PALETTE_AUTO[0]      # first unused colour


def test_full_sidebar(monkeypatch):
    assert config.MAX_ROWS == 200
    monkeypatch.setattr(config, "MAX_ROWS", 5)
    m = mgr(*["x^2"] * config.MAX_ROWS)
    with pytest.raises(EquationError, match="Sidebar full"):
        m.add("x")


def test_replace_keeps_color_and_position():
    m = mgr("x^2", "sin(x)", "x = 2")
    color = m.entries[1].color
    m.entries[1].pulse_timer = 0.9
    m.replace(1, "cos(x)")
    assert m.entries[1].text == "cos(x)" and m.entries[1].color == color
    assert m.entries[1].pulse_timer == config.FIRST_PULSE_DELAY
    with pytest.raises(EquationError):
        m.replace(1, "nope(")
    assert m.entries[1].text == "cos(x)"


def test_move_delete_toggle():
    m = mgr("x^2", "sin(x)", "x = 2")
    m.move(2, 0)
    assert [e.text for e in m.entries] == ["x = 2", "x^2", "sin(x)"]
    m.move(0, 2)
    assert [e.text for e in m.entries] == ["x^2", "sin(x)", "x = 2"]
    m.toggle(1)
    assert not m.entries[1].enabled
    m.delete(0)
    assert [e.text for e in m.entries] == ["sin(x)", "x = 2"]


def test_active_set_and_status():
    m = mgr("x^2", "sin(x)", "x = 2", "x = -2", "x = 3", "x = 4", "x = 5", "x = 100")
    assert config.MAX_ACTIVE == 6
    assert [e.text for e in m.active()] == ["x^2", "sin(x)", "x = 2", "x = -2", "x = 3", "x = 4"]
    assert m.status(m.entries[6]) == "queued"
    m.toggle(0)
    assert m.status(m.entries[0]) == "off"
    assert m.active()[-1].text == "x = 5"             # queued row moves up
    assert m.status(m.entries[6]) == "active"
    m.move(7, 1)
    assert m.status(m.entries[1]) == "offscreen"      # x = 100 is now active but invisible
    assert m.status(m.entries[7]) == "queued"


def test_pulse_damage_values():
    assert pulse_damage(14.4) == pytest.approx(400 / 14.4)       # base 100 * DMG_SCALE 4
    assert pulse_damage(0.5) == 50.0                  # L_MIN then the base*0.5 cap
    assert pulse_damage(10_000) == config.DMG_MIN
    assert pulse_damage(8.0, 200.0) == pytest.approx(100.0)      # 200*4/8 = 100 = cap
    assert pulse_damage(1.0, 200.0) == 100.0
    assert pulse_damage(10_000, 3.0) == 1.0 and pulse_damage(1.0, 1.0) == 0.5   # cap below the floor wins


def test_pulse_timing_and_damage():
    m = mgr("x = 0")
    sw = swarm_at((640, 100), (900, 100))             # first is on the line, second is far
    sw.hp[:] = sw.max_hp[:] = 100.0
    assert m.update(0.2, 0.2, sw, ORIGIN) == 0
    assert sw.hp.tolist() == [100.0, 100.0]            # first pulse only after 0.3 s
    m.update(0.2, 0.4, sw, ORIGIN)
    expected = 100.0 - pulse_damage(m.entries[0].curve.length_units)
    assert sw.hp[0] == pytest.approx(expected) and sw.hp[1] == 100.0
    assert m.entries[0].flash == pytest.approx(config.PULSE_FADE)
    m.update(0.5, 0.9, sw, ORIGIN)                    # next pulse due at 1.3 s
    assert sw.hp[0] == pytest.approx(expected)
    m.update(0.5, 1.4, sw, ORIGIN)
    assert sw.hp[0] == pytest.approx(expected - pulse_damage(m.entries[0].curve.length_units))


def test_pulse_kills_are_counted_and_removed():
    m = mgr("x = 0")
    sw = swarm_at((640, 100), (641, 400), (1000, 300))
    sw.hp[:] = 5.0
    assert m.update(0.31, 0.31, sw, ORIGIN) == 2
    assert len(sw) == 1


def test_queued_and_off_do_not_fire():
    m = mgr("x = 0")
    m.toggle(0)
    sw = swarm_at((640, 100))
    m.update(2.0, 2.0, sw, ORIGIN)
    assert sw.hp[0] == 20.0


def test_player_offset_moves_world_enemy_into_curve():
    m = mgr("x = 0")
    sw = swarm_at((640, 100))
    sw.pos += np.array((500.0, 0))                    # enemy now far right of the line...
    m.update(0.31, 0.31, sw, ORIGIN)
    assert sw.hp[0] == 20.0
    m.entries[0].pulse_timer = 0.0
    m.update(0.01, 0.32, sw, np.array((500.0, 0)))    # ...but the player walked right with it
    assert len(sw) == 0                               # hit (27.8 dmg) and killed


def test_t_equation_rebuild_rate_and_round_robin():
    m = mgr("y = sin(x + t)", "y = cos(x - t)", "x^2")
    sw = swarm_at()
    calls = []
    orig = m._rebuild
    m._rebuild = lambda e, **kw: (calls.append(e.text), orig(e, **kw))
    for i in range(60):                               # one second at 60 fps
        m.update(1 / 60, (i + 1) / 60, sw, ORIGIN)
    assert "x^2" not in calls                                # only t rows rebuild
    for text in ("y = sin(x + t)", "y = cos(x - t)"):         # each at most T_REBUILD_HZ
        assert 7 <= calls.count(text) <= config.T_REBUILD_HZ
    assert set(calls) == {"y = sin(x + t)", "y = cos(x - t)"}
    assert calls[0] != calls[1]                       # alternates between the two rows
    assert m.entries[0].parsed.uses_t and not m.entries[2].parsed.uses_t


# --- persistence -------------------------------------------------------
def test_save_load_round_trip(tmp_path):
    path = tmp_path / "sub" / "equations.json"
    m = EquationManager(path)
    for t in ("x^2", "sin(x)", "x = 2"):
        m.add(t)
    m.toggle(1)
    m.move(2, 0)
    m2 = EquationManager(path)
    m2.load()
    assert [(e.text, e.enabled) for e in m2.entries] == [("x = 2", True), ("x^2", True), ("sin(x)", False)]
    assert [e.color for e in m2.entries] == [m.entries[i].color for i in range(3)]   # colours are saved
    assert all(e.curve is not None for e in m2.entries if e.enabled)      # off rows build when enabled


def test_every_change_saves(tmp_path):
    path = tmp_path / "f.json"
    m = EquationManager(path)

    def saved():
        import json
        return [r["text"] for r in json.loads(path.read_text())["equations"]]

    m.add("x^2"); m.add("sin(x)")
    assert saved() == ["x^2", "sin(x)"]
    m.replace(0, "cos(x)")
    assert saved() == ["cos(x)", "sin(x)"]
    m.move(1, 0)
    assert saved() == ["sin(x)", "cos(x)"]
    m.toggle(0)
    assert '"enabled": false' in path.read_text()
    m.delete(0)
    assert saved() == ["cos(x)"]


def test_load_skips_bad_entries_and_files(tmp_path):
    path = tmp_path / "f.json"
    path.write_text('{"version":1,"equations":[{"text":"x^2","enabled":true},{"text":"sin x"},'
                    '{"nope":1},"junk",{"text":"x = 2","enabled":false}]}')
    m = EquationManager(path)
    m.load()
    assert [(e.text, e.enabled) for e in m.entries] == [("x^2", True), ("x = 2", False)]
    for bad in ("not json", '{"equations": 5}', "[]", ""):
        path.write_text(bad)
        m.load()
        assert m.entries == []
    EquationManager(tmp_path / "missing.json").load()      # no file: fine
    EquationManager(None).save()                           # no path: no-op


# --- named equations (P7) ----------------------------------------------
def test_names_must_be_unique():
    m = mgr("eq4: x^2+y^2=1", "y = x")
    with pytest.raises(EquationError, match="Name 'eq4' already used"):
        m.add("eq4: y = 2x")
    with pytest.raises(EquationError, match="Name 'EQ4' already used"):     # case-insensitive
        m.add("EQ4: y = 2x")
    assert len(m.entries) == 2
    m.add("eq5: y = 2x")
    assert [e.parsed.name for e in m.entries] == ["eq4", None, "eq5"]


def test_named_text_is_full_and_edit_keeps_name_rules():
    m = mgr("r1: x^2+y^2=1", "y = x")
    assert m.entries[0].text == "r1: x^2+y^2=1" and m.entries[0].parsed.source == "x^2+y^2=1"
    m.replace(0, "r1:y=sin(x)")                          # re-saving a row under its own name is fine
    assert m.entries[0].text == "r1: y=sin(x)"
    with pytest.raises(EquationError, match="already used"):
        m.replace(1, "r1: y = x")                        # but another row can't take it
    m.replace(1, "r2: y = x")
    m.replace(0, "y = x^2")                              # dropping the name frees it
    m.add("r1: y = 3")
    assert [e.parsed.name for e in m.entries] == [None, "r2", "r1"]


def test_named_save_load_round_trip(tmp_path):
    path = tmp_path / "f.json"
    m = EquationManager(path)
    m.add("eq4: (x^(2)+y^(2))^(3)=4 x^(2) y^(2)")
    m.add("y = x")
    m2 = EquationManager(path)
    m2.load()
    assert [e.text for e in m2.entries] == ["eq4: (x^(2)+y^(2))^(3)=4 x^(2) y^(2)", "y = x"]
    assert m2.entries[0].parsed.name == "eq4"
    # duplicate names in a hand-edited file: the second one is skipped
    path.write_text('{"version":1,"equations":[{"text":"a: x"},{"text":"a: y"},{"text":"b: y"}]}')
    m2.load()
    assert [e.text for e in m2.entries] == ["a: x", "b: y"]


# --- migration of the old save/formulas.json -----------------------------------------------------
def test_old_formulas_json_migrates_to_equations_json(tmp_path):
    import json
    legacy = tmp_path / "formulas.json"
    legacy.write_text(json.dumps({"version": 1, "formulas": [
        {"text": "x^2", "enabled": True}, {"text": "eq1: y = sin(x)", "enabled": False}]}), encoding="utf-8")
    new = tmp_path / "equations.json"
    m = EquationManager(new)
    m.load()
    assert [e.text for e in m.entries] == ["x^2", "eq1: y = sin(x)"]
    assert [e.enabled for e in m.entries] == [True, False]
    assert new.exists() and legacy.exists()                       # the old file stays in place
    data = json.loads(new.read_text(encoding="utf-8"))
    assert "equations" in data and "formulas" not in data
    legacy.write_text("{}", encoding="utf-8")                      # the new file wins from now on
    m2 = EquationManager(new)
    m2.load()
    assert len(m2.entries) == 2


def test_no_migration_without_legacy_file(tmp_path):
    m = EquationManager(tmp_path / "equations.json")
    m.load()
    assert m.entries == [] and not (tmp_path / "equations.json").exists()
