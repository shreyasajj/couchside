"""Read the bundled Sendspin daemon's client id (never writes its files)."""

from __future__ import annotations

import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)


def read_client_id(settings_dir: Path) -> str | None:
    """The Sendspin client_id is the base64url public key of identity-daemon.json."""
    from aiosendspin.noise import Identity, b64url_decode

    path = Path(settings_dir) / "identity-daemon.json"
    try:
        data = json.loads(path.read_text())
        return Identity.from_private_bytes(b64url_decode(data["private_key"])).peer_id
    except FileNotFoundError:
        return None
    except Exception as e:  # corrupt file, bad key, wrong shape
        log.warning("Cannot read Sendspin identity %s: %s", path, e)
        return None
