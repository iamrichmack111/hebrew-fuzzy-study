from __future__ import annotations

import shutil
from importlib.resources import as_file, files
from pathlib import Path

from platformdirs import user_data_dir


APP_NAME = "hebrew-fuzzy-study"
APP_AUTHOR = "Richmack"


def data_dir() -> Path:
    """Return the writable per-user application data directory."""
    path = Path(user_data_dir(APP_NAME, APP_AUTHOR))
    path.mkdir(parents=True, exist_ok=True)
    return path


def database_path() -> Path:
    """
    Return the user's working SQLite database.

    On first run, copy the packaged seed database into the
    writable application-data directory.
    """
    destination = data_dir() / "hebrew.db"

    if destination.exists():
        return destination

    seed = files("hebrew_fuzzy_study").joinpath("hebrew.db")

    with as_file(seed) as seed_path:
        shutil.copy2(seed_path, destination)

    return destination


def export_dir() -> Path:
    path = Path.home() / "Documents" / "hebrew-fuzzy-exports"
    path.mkdir(parents=True, exist_ok=True)
    return path
