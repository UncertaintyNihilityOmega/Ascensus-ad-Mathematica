"""Settings registry: keys exist in config, clamping, reset, persistence round trip, bad files."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from ascensus import config, settings


@pytest.fixture(autouse=True)
def _restore():
    """Every test starts from, and leaves, the defaults."""
    settings.reset_all()
    yield
    settings.reset_all()


def test_every_key_exists_in_config_and_matches_kind():
    for s in settings.SETTINGS:
        assert hasattr(config, s.key), s.key
        d = settings.default(s.key)
        if s.kind == "bool":
            assert isinstance(d, bool), s.key
        elif s.kind == "choice":
            assert d in s.choices, s.key
        elif s.kind == "key":
            assert isinstance(d, str) and d, s.key
        else:
            assert isinstance(d, (int, float)) and not isinstance(d, bool), s.key
            assert s.min <= d <= s.max, f"{s.key} default {d} outside [{s.min}, {s.max}]"
            assert s.step > 0, s.key
        assert s.label and s.tab


def test_tabs_exactly_as_designed():
    assert settings.tabs() == ["Display", "Controls", "Player", "Enemies", "Boss", "Combat",
                               "Upgrades & XP", "Equations & Variables"]
    for tab in settings.tabs():
        assert settings.settings_for(tab)
    keys = {s.key for s in settings.settings_for("Display")}
    assert {"FULLSCREEN_START", "UNIT_PX", "SHOW_FPS_DEFAULT", "SHOW_GRID_DEFAULT", "GRID_STEP"} <= keys
    assert any(s.next_run for s in settings.SETTINGS)


def test_set_value_clamps_and_converts():
    assert settings.set_value("UNIT_PX", 5000) == 100 and config.UNIT_PX == 100
    assert settings.set_value("UNIT_PX", -3) == 25
    assert settings.set_value("GRID_STEP", 3.6) == 4 and isinstance(config.GRID_STEP, int)
    assert settings.set_value("SHOW_GRID_DEFAULT", False) is False and config.SHOW_GRID_DEFAULT is False
    with pytest.raises(ValueError):
        settings.set_value("UNIT_PX", float("nan"))
    with pytest.raises(ValueError):
        settings.set_value("UNIT_PX", "50")
    with pytest.raises(KeyError):
        settings.set_value("NOT_A_KEY", 1)


def test_nudge_uses_step_and_toggles_bools():
    base = settings.get("UNIT_PX")
    assert settings.nudge("UNIT_PX", +1) == base + 5
    assert settings.nudge("UNIT_PX", -1) == base
    assert abs(settings.nudge("TYPING_TIME_SCALE", +1) - (settings.default("TYPING_TIME_SCALE") + 0.05)) < 1e-9
    settings.nudge("UNIT_PX", -1)
    for _ in range(20):
        settings.nudge("UNIT_PX", -1)
    assert settings.get("UNIT_PX") == 25                                   # stops at min
    assert settings.nudge("SHOW_FPS_DEFAULT", +1) is (not settings.default("SHOW_FPS_DEFAULT"))


def test_reset_key_tab_all():
    settings.set_value("UNIT_PX", 80)
    settings.set_value("PLAYER_SPEED", 400)
    settings.set_value("BOSS_RADIUS", 60)
    assert not settings.is_default("UNIT_PX")
    settings.reset("UNIT_PX")
    assert config.UNIT_PX == settings.default("UNIT_PX") and settings.is_default("UNIT_PX")
    settings.reset_tab("Player")
    assert settings.is_default("PLAYER_SPEED") and config.BOSS_RADIUS == 60
    settings.reset_all()
    assert settings.is_default("BOSS_RADIUS")


def test_save_load_round_trip_only_changed(tmp_path):
    p = tmp_path / "save" / "settings.json"
    settings.set_value("UNIT_PX", 75)
    settings.set_value("SHOW_FPS_DEFAULT", False)
    assert settings.save(p)
    data = json.loads(p.read_text())
    assert data["values"] == {"UNIT_PX": 75.0, "SHOW_FPS_DEFAULT": False}
    settings.reset_all()
    assert settings.apply_saved(p) == 2
    assert config.UNIT_PX == 75 and config.SHOW_FPS_DEFAULT is False


def test_load_ignores_unknown_bad_and_clamps(tmp_path):
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"version": 1, "values": {
        "UNIT_PX": 9999, "NOPE": 1, "GRID_STEP": "x", "SHOW_GRID_DEFAULT": 0.5,
        "PLAYER_SPEED": True, "BOSS_RADIUS": 55}}))
    assert settings.apply_saved(p) == 2
    assert config.UNIT_PX == 100 and config.BOSS_RADIUS == 55
    assert settings.is_default("GRID_STEP") and settings.is_default("PLAYER_SPEED")
    assert not hasattr(config, "NOPE")


@pytest.mark.parametrize("content", ["", "{not json", "[]", "null", '{"values": []}', '{"values": 5}',
                                     '{"version": 1}', '{"values": {"UNIT_PX": [1]}}'])
def test_corrupt_or_odd_files_are_harmless(tmp_path, content):
    p = tmp_path / "s.json"
    p.write_text(content)
    assert settings.apply_saved(p) == 0
    assert settings.is_default("UNIT_PX")


def test_missing_file_and_unwritable_path(tmp_path):
    assert settings.apply_saved(tmp_path / "missing.json") == 0
    blocker = tmp_path / "file"
    blocker.write_text("x")
    assert settings.save(blocker / "sub" / "settings.json") is False


def test_env_override_path():
    root = Path(__file__).resolve().parent.parent
    env = dict(os.environ, ASCENSUS_SETTINGS=str(root / "x" / "custom.json"))
    out = subprocess.run([sys.executable, "-c", "from ascensus import config; print(config.SETTINGS_PATH)"],
                         cwd=root, env=env, capture_output=True, text=True)
    assert Path(out.stdout.strip()) == root / "x" / "custom.json"
