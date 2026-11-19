"""Crossfade, as Music Assistant keeps it (Qt-free).

MA 2.10 splits it three ways: on/off per queue, the style per queue (standard, smart
beat-matched, or "global": the server's default), and the standard crossfade's length for
the whole server (Settings → Player Queues, 1-15 s; Home Assistant shows it as a number).
Smart crossfade picks its own length, so the length only matters for the standard style.

Commands are sent raw (no schema check) so older and newer servers both take them.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

log = logging.getLogger(__name__)

DOMAIN = "player_queues"
MIN_SECONDS, MAX_SECONDS = 1, 15
MODES = (("global", "Music Assistant's default"),
         ("standard_crossfade", "Standard"),
         ("smart_crossfade", "Smart (beat-matched)"))
_KNOWN = {m for m, _ in MODES}


@dataclass(frozen=True)
class Crossfade:
    enabled: bool
    mode: str          # this queue's style: global | standard_crossfade | smart_crossfade
    server_mode: str   # the server's default style (what "global" means)
    seconds: int       # the standard crossfade's length, for the whole server

    @property
    def effective_mode(self) -> str:
        return self.server_mode if self.mode == "global" else self.mode

    @property
    def length_applies(self) -> bool:
        return self.effective_mode == "standard_crossfade"


def label(mode: str) -> str:
    return dict(MODES).get(mode, mode)


async def load(client: Any, queue_id: str | None) -> Crossfade | None:
    if client is None or not queue_id:
        return None
    try:
        queue = client.player_queues.get(queue_id)
        mode = await client.send_command("config/player_queues/get_value", queue_id=queue_id,
                                         key="crossfade_mode")
        server_mode = await client.send_command("config/core/get_value", domain=DOMAIN,
                                                key="crossfade_mode")
        seconds = await client.send_command("config/core/get_value", domain=DOMAIN,
                                            key="crossfade_duration")
    except Exception as err:
        log.info("Couldn't read the crossfade settings: %s", err)
        return None
    return Crossfade(enabled=bool(getattr(queue, "crossfade_enabled", False)),
                     mode=str(mode or "global"), server_mode=str(server_mode or "standard_crossfade"),
                     seconds=int(seconds or 8))


async def _send(client: Any, command: str, **args: Any) -> bool:
    if client is None:
        return False
    try:
        await client.send_command(command, **args)
        return True
    except Exception as err:
        log.warning("%s failed: %s", command, err)
        return False


async def set_enabled(client: Any, queue_id: str, on: bool) -> bool:
    return await _send(client, "player_queues/crossfade", queue_id=queue_id, crossfade_enabled=bool(on))


async def set_mode(client: Any, queue_id: str, mode: str) -> bool:
    if mode not in _KNOWN:
        return False
    return await _send(client, "config/player_queues/save", queue_id=queue_id,
                       values={"crossfade_mode": mode})


async def set_seconds(client: Any, seconds: int) -> bool:
    seconds = max(MIN_SECONDS, min(MAX_SECONDS, int(seconds)))
    return await _send(client, "config/core/save", domain=DOMAIN, values={"crossfade_duration": seconds})
