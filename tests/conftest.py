"""Keep the tests away from the real save/ files: every save path points at a temp folder, and a
session guard fails the run if anything in the real save/ folder was created, changed or deleted."""
import hashlib
import os
import tempfile
from pathlib import Path

_tmp = Path(tempfile.gettempdir()) / "ascensus_pytest"
os.environ["ASCENSUS_SAVE"] = str(_tmp / "equations.json")
os.environ["ASCENSUS_SETTINGS"] = str(_tmp / "settings.json")
os.environ["ASCENSUS_PROFILE"] = str(_tmp / "profile.json")
os.environ["ASCENSUS_SLOTS"] = str(_tmp / "slots")      # autosaves of test games never touch save/slots

import pytest  # noqa: E402

REAL_SAVE_DIR = Path(__file__).resolve().parent.parent / "save"


def _fingerprint(folder: Path) -> dict[str, str]:
    """{relative path: sha1} of every file under the real save folder."""
    if not folder.exists():
        return {}
    return {str(p.relative_to(folder)): hashlib.sha1(p.read_bytes()).hexdigest()
            for p in sorted(folder.rglob("*")) if p.is_file()}


@pytest.fixture(autouse=True, scope="session")
def _real_save_untouched():
    """The player's own save/ folder must be byte-for-byte the same after the whole test run."""
    before = _fingerprint(REAL_SAVE_DIR)
    yield
    after = _fingerprint(REAL_SAVE_DIR)
    assert after == before, f"tests modified the real save folder: {sorted(set(before.items()) ^ set(after.items()))}"


@pytest.fixture(autouse=True)
def _fresh_saves(tmp_path, monkeypatch):
    """Every test gets its own empty equations file and slots folder (never the real ones)."""
    from ascensus import config
    monkeypatch.setattr(config, "SAVE_PATH", tmp_path / "equations.json")
    monkeypatch.setattr(config, "SLOTS_PATH", tmp_path / "slots")
