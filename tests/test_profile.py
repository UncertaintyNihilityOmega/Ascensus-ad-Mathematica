"""Profile persistence: defaults, round trip, corrupt/missing files, env override."""
import json
import os
import subprocess
import sys
from pathlib import Path

from ascensus.profile import Profile


def test_defaults_and_missing_file(tmp_path):
    p = Profile(tmp_path / "nope" / "profile.json")
    assert (p.best_time, p.best_kills) == (0.0, 0)
    assert p.lifetime == {"dashes": 0, "kills": 0} and p.achievements == {}
    assert p.best_text() == "Best run: --:--"


def test_round_trip(tmp_path):
    path = tmp_path / "save" / "profile.json"
    p = Profile(path)
    assert p.record_run(452.0, 154) is True
    p.add_lifetime("dashes", 5)
    p.add_lifetime("kills", 154)
    assert p.unlock("first_blood") is True
    q = Profile(path)
    assert q.best_time == 452.0 and q.best_kills == 154
    assert q.lifetime["dashes"] == 5 and q.lifetime["kills"] == 154
    assert "first_blood" in q.achievements and len(q.achievements["first_blood"]) == 10
    assert q.best_text() == "Best run: 07:32 - 154 kills"


def test_record_run_keeps_bests(tmp_path):
    p = Profile(tmp_path / "p.json")
    p.record_run(100.0, 10)
    assert p.record_run(50.0, 5) is False
    assert (p.best_time, p.best_kills) == (100.0, 10)
    assert p.record_run(60.0, 30) is True          # kills improved, time kept
    assert (p.best_time, p.best_kills) == (100.0, 30)


def test_unlock_is_once(tmp_path):
    p = Profile(tmp_path / "p.json")
    assert p.unlock("a") and not p.unlock("a")
    assert p.is_unlocked("a") and not p.is_unlocked("b")


def test_corrupt_files_fall_back(tmp_path):
    path = tmp_path / "p.json"
    for bad in ("{not json", "[]", json.dumps({"best_time": "abc"}), "", json.dumps({"lifetime": [1]})):
        path.write_text(bad, encoding="utf-8")
        p = Profile(path)
        assert (p.best_time, p.best_kills) == (0.0, 0) and p.achievements == {}
        assert p.lifetime == {"dashes": 0, "kills": 0}
    p.unlock("x")                                   # a corrupt file is overwritten by the next save
    assert Profile(path).is_unlocked("x")


def test_unwritable_path_does_not_raise(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    p = Profile(blocker / "sub" / "profile.json")   # parent is a file: mkdir fails
    assert p.save() is False
    assert p.unlock("a") is True                    # still recorded in memory


def test_in_memory_profile():
    p = Profile.in_memory()
    p.record_run(10, 1)
    assert p.save() is False and p.best_kills == 1


def test_env_override_path():
    root = Path(__file__).resolve().parent.parent
    env = dict(os.environ, ASCENSUS_PROFILE=str(root / "x" / "custom.json"))
    out = subprocess.run([sys.executable, "-c", "from ascensus import config; print(config.PROFILE_PATH)"],
                         cwd=root, env=env, capture_output=True, text=True)
    assert Path(out.stdout.strip()) == root / "x" / "custom.json"
