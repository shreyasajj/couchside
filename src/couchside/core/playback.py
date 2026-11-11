"""Select this TV's Sendspin player in MA and drive basic transport."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Literal

from couchside.core.connection import ConnState

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class NowPlaying:
    title: str
    artist: str
    album: str
    image_url: str | None
    state: Literal["playing", "paused", "idle"]


def player_matches(player: Any, client_id: str) -> bool:
    """Match on ids only: the player itself, or one of its output protocols."""
    if player.player_id == client_id:
        return True
    return any(
        getattr(op, "output_protocol_id", None) == client_id
        for op in (getattr(player, "output_protocols", None) or [])
    )


def find_local_player(players: Iterable[Any], client_id: str) -> Any | None:
    for p in players:
        if player_matches(p, client_id):
            return p
    return None


def _state_str(value: Any) -> Literal["playing", "paused", "idle"]:
    s = str(getattr(value, "value", value) or "idle").lower()
    return s if s in ("playing", "paused") else "idle"  # type: ignore[return-value]


class Playback:
    def __init__(self, conn: Any, get_client_id: Callable[[], str | None]) -> None:
        self._conn = conn
        self._get_client_id = get_client_id
        self.user_player_id: str | None = None  # Phase 3: speaker picker
        self.active_player_id: str | None = None
        self.local_player_found = False
        self.now_playing: NowPlaying | None = None
        self._cbs: list[Callable[[], None]] = []
        conn.on_state(lambda _state: self.refresh())
        conn.on_event(lambda _event: self.refresh())

    def on_change(self, cb: Callable[[], None]) -> None:
        self._cbs.append(cb)

    def refresh(self) -> None:
        client = self._conn.client
        players = list(client.players) if client is not None else []
        client_id = self._get_client_id()
        local = find_local_player(players, client_id) if client_id else None

        active = None
        if self.user_player_id and client is not None:
            active = client.players.get(self.user_player_id)
        if active is None:
            active = local

        now = None
        media = getattr(active, "current_media", None) if active is not None else None
        if media is not None and (media.title or media.artist):
            now = NowPlaying(
                title=media.title or "",
                artist=media.artist or "",
                album=media.album or "",
                image_url=media.image_url,
                state=_state_str(active.playback_state),
            )

        new = (active.player_id if active is not None else None, local is not None, now)
        old = (self.active_player_id, self.local_player_found, self.now_playing)
        self.active_player_id, self.local_player_found, self.now_playing = new
        if new != old:
            for cb in list(self._cbs):
                try:
                    cb()
                except Exception:
                    log.exception("playback listener failed")

    async def _command(self, name: str) -> None:
        client = self._conn.client
        pid = self.active_player_id
        if client is None or pid is None or self._conn.state is not ConnState.CONNECTED:
            return
        try:
            await getattr(client.players, name)(pid)
        except Exception as e:
            log.warning("%s on %s failed: %s", name, pid, e)

    async def play_pause(self) -> None:
        await self._command("play_pause")

    async def next(self) -> None:
        await self._command("next_track")

    async def previous(self) -> None:
        await self._command("previous_track")
