"""Keep the tests away from the real save/ files: point the settings and profile paths at a temp folder."""
import os
import tempfile
from pathlib import Path

_tmp = Path(tempfile.gettempdir()) / "ascensus_pytest"
os.environ.setdefault("ASCENSUS_SETTINGS", str(_tmp / "settings.json"))
os.environ.setdefault("ASCENSUS_PROFILE", str(_tmp / "profile.json"))
_slots = _tmp / "slots"
os.environ.setdefault("ASCENSUS_SLOTS", str(_slots))      # autosaves of test games never touch save/slots

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_slots(tmp_path, monkeypatch):
    """Every test gets an empty save/slots folder (no leftover autosave, never the real one)."""
    from ascensus import config
    monkeypatch.setattr(config, "SLOTS_PATH", tmp_path / "slots")
