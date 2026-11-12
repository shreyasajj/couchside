"""Versions for the Settings screen: the Sendspin bundled in this build, the newest on
PyPI, and this build's own version (written by the release workflow). Qt-free."""

from __future__ import annotations

import json
import logging
import re
from importlib import metadata
from pathlib import Path
from typing import Any, Awaitable, Callable

log = logging.getLogger(__name__)

PYPI_URL = "https://pypi.org/pypi/sendspin/json"
BUILD_INFO = Path(__file__).resolve().parents[1] / "build_info.json"
CHECK_EVERY = 24 * 3600.0
_VERSION = re.compile(r"^\d+(\.\d+){0,3}([a-z0-9.+-]*)$", re.I)

HttpGet = Callable[[str, dict], Awaitable[tuple[int, Any]]]


def bundled_sendspin_version() -> str | None:
    try:
        return metadata.version("sendspin")
    except metadata.PackageNotFoundError:
        return None


async def latest_sendspin_version(http_get: HttpGet) -> str | None:
    """Newest Sendspin on PyPI, or None when it can't be found out."""
    try:
        status, data = await http_get(PYPI_URL, {})
    except Exception as e:
        log.info("Sendspin version check failed: %s", e)
        return None
    version = (data or {}).get("info", {}).get("version") if status == 200 and isinstance(data, dict) else None
    if not isinstance(version, str) or len(version) > 40 or not _VERSION.match(version):
        return None
    return version


def _key(v: str) -> tuple[int, ...]:
    return tuple(int(p) for p in re.findall(r"\d+", v.split("+")[0])[:4])


def is_newer(candidate: str | None, current: str | None) -> bool:
    if not candidate or not current:
        return False
    return _key(candidate) > _key(current)


def build_info() -> dict:
    """{"version", "commit", "feed"} of this build ("dev" and no feed when not built by
    the release workflow). `feed` is the published latest.json for this release channel."""
    try:
        data = json.loads(BUILD_INFO.read_text())
        return {"version": str(data.get("version") or "dev"), "commit": str(data.get("commit") or ""),
                "feed": str(data.get("feed") or "")}
    except (OSError, ValueError, AttributeError):
        return {"version": "dev", "commit": "", "feed": ""}


async def latest_app_version(http_get: HttpGet, feed: str) -> str | None:
    """Newest published Couchside (the release workflow writes latest.json next to the
    repo). Flatpak's own check runs only every 30 minutes; this one is immediate."""
    if not feed:
        return None
    try:
        status, data = await http_get(feed, {})
    except Exception as e:
        log.info("Couchside version check failed: %s", e)
        return None
    version = data.get("version") if status == 200 and isinstance(data, dict) else None
    if not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+\.\d+", version):
        return None
    return version
