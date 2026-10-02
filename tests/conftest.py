"""Keep the tests away from the real save/ files: point the settings and profile paths at a temp folder."""
import os
import tempfile
from pathlib import Path

_tmp = Path(tempfile.gettempdir()) / "ascensus_pytest"
os.environ.setdefault("ASCENSUS_SETTINGS", str(_tmp / "settings.json"))
os.environ.setdefault("ASCENSUS_PROFILE", str(_tmp / "profile.json"))
