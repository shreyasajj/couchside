"""Follow the Sendspin daemon log for pairing codes (the daemon only logs them)."""

from __future__ import annotations

import asyncio
import re
from enum import Enum
from pathlib import Path
from typing import Callable


class PairingEvent(Enum):
    CODE = "code"
    FAILED = "failed"
    STARTED = "started"


# Messages from sendspin 9.1.0 sendspin/daemon/daemon.py
_PATTERNS = [
    (PairingEvent.CODE, re.compile(r"Pairing required: enter pairing code (?P<v>.+?) on the server\.")),
    (PairingEvent.FAILED, re.compile(r"Pairing failed: (?P<v>.+)")),
    (PairingEvent.STARTED, re.compile(r"Starting Sendspin daemon: (?P<v>\S+)")),
]


def parse_log_line(line: str) -> tuple[PairingEvent, str] | None:
    for event, pattern in _PATTERNS:
        m = pattern.search(line)
        if m:
            return event, m.group("v").strip()
    return None


async def tail_log(
    path: Path, on_event: Callable[[PairingEvent, str], None], poll: float = 0.5
) -> None:
    """Report events from lines appended after start. Survives a missing or truncated file."""
    path = Path(path)
    try:
        offset = path.stat().st_size
    except FileNotFoundError:
        offset = 0
    buffer = ""
    while True:
        try:
            size = path.stat().st_size
        except FileNotFoundError:
            await asyncio.sleep(poll)
            continue
        if size < offset:
            offset, buffer = 0, ""
        if size > offset:
            with path.open("r", encoding="utf-8", errors="replace") as fh:
                fh.seek(offset)
                chunk = fh.read()
                offset = fh.tell()
            buffer += chunk
            *lines, buffer = buffer.split("\n")
            for line in lines:
                parsed = parse_log_line(line)
                if parsed:
                    on_event(*parsed)
        await asyncio.sleep(poll)
