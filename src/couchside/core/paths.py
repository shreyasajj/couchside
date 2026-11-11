"""XDG locations. Inside the Flatpak these resolve under ~/.var/app/<app-id>/."""

from __future__ import annotations

import os
from pathlib import Path


def _xdg(var: str, fallback: str) -> Path:
    value = os.environ.get(var)
    if value:
        return Path(value)
    return Path(os.environ.get("HOME", str(Path.home()))) / fallback


def config_dir() -> Path:
    return _xdg("XDG_CONFIG_HOME", ".config") / "couchside"


def state_dir() -> Path:
    return _xdg("XDG_STATE_HOME", ".local/state") / "couchside"


def sendspin_settings_dir() -> Path:
    return _xdg("XDG_CONFIG_HOME", ".config") / "sendspin"
