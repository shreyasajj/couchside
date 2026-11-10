"""App settings (JSON) and the MA token (separate 0600 file)."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from couchside.core.paths import config_dir

log = logging.getLogger(__name__)


@dataclass
class AppSettings:
    server_url: str | None = None
    player_name: str = "Living Room TV"
    qr_caption: str = "Scan to add songs"
    guest_public_url: str | None = None
    autostart_requested: bool = False


def _settings_path() -> Path:
    return config_dir() / "settings.json"


def _token_path() -> Path:
    return config_dir() / "token"


def load_settings(path: Path | None = None) -> AppSettings:
    path = path or _settings_path()
    try:
        data = json.loads(path.read_text())
    except FileNotFoundError:
        return AppSettings()
    except (OSError, ValueError) as e:
        log.warning("Ignoring unreadable settings %s: %s", path, e)
        return AppSettings()
    if not isinstance(data, dict):
        return AppSettings()
    defaults = AppSettings()
    values = {}
    for f in fields(AppSettings):
        if f.name not in data:
            continue
        value = data[f.name]
        default = getattr(defaults, f.name)
        if isinstance(default, bool):
            ok = isinstance(value, bool)
        elif default is None:
            ok = value is None or isinstance(value, str)
        else:
            ok = isinstance(value, type(default))
        if ok:
            values[f.name] = value
        else:
            log.warning("Ignoring setting %s with wrong type", f.name)
    return AppSettings(**values)


def _atomic_write(path: Path, text: str, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def save_settings(settings: AppSettings, path: Path | None = None) -> None:
    _atomic_write(path or _settings_path(), json.dumps(asdict(settings), indent=2))


def load_token(path: Path | None = None) -> str | None:
    try:
        token = (path or _token_path()).read_text().strip()
    except OSError:
        return None
    return token or None


def save_token(token: str, path: Path | None = None) -> None:
    _atomic_write(path or _token_path(), token.strip(), mode=0o600)


def normalize_server_url(url: str) -> str | None:
    """Turn what a user typed with a remote into an MA base URL (None = use discovery)."""
    url = url.strip().rstrip("/")
    if not url:
        return None
    if "://" not in url:
        url = f"http://{url}"
    if url.startswith("http://") and url.count(":") < 2:  # plain LAN host, no port
        url = f"{url}:8095"
    return url
