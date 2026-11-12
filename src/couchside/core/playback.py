"""Select this TV's Sendspin player in MA and drive basic transport."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Literal

from couchside.core.connection import ConnState

log = logging.getLogger(__name__)


Repeat = Literal["off", "all", "one"]
_REPEAT_CYCLE: dict[str, str] = {"off": "all", "all": "one", "one": "off"}


@dataclass(frozen=True)
class NowPlaying:
    title: str
    artist: str
    album: str
    image_url: str | None
    state: Literal["playing", "paused", "idle"]
    duration: float | None = None
    elapsed: float = 0.0
    elapsed_at: float = 0.0  # server epoch seconds when `elapsed` was measured
    shuffle: bool = False
    repeat: Repeat = "off"
    volume: int | None = None  # None: the player has no volume control
    palette_dark: tuple[int, int, int] | None = None
    queue_id: str | None = None
    uri: str | None = None  # identifies the track (lyrics lookup, change detection)
    next_title: str = ""    # the song after this one ("Up next"); empty when unknown
    next_artist: str = ""
    next_image_url: str | None = None


def position_at(np: NowPlaying, now: float) -> float:
    """Playback position at epoch `now`: ticks only while playing, clamped to the track."""
    pos = np.elapsed + (now - np.elapsed_at if np.state == "playing" else 0.0)
    pos = max(0.0, pos)
    if np.duration:
        pos = min(float(np.duration), pos)
    return pos


def _repeat_str(value: Any) -> Repeat:
    s = str(getattr(value, "value", value) or "off").lower()
    return s if s in ("all", "one") else "off"  # type: ignore[return-value]


def _num(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


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
        self.user_player_id: str | None = None  # speaker picked on the Speakers page
        self.active_player_id: str | None = None
        self.local_player_found = False
        self.now_playing: NowPlaying | None = None
        self._local_stamp: tuple[float, float] | None = None  # (elapsed, local time)
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
            chosen = client.players.get(self.user_player_id)
            if chosen is not None and getattr(chosen, "available", True):
                active = chosen
            else:  # chosen speaker went offline or was deleted: back to this TV
                log.info("controlled speaker %s gone; back to this TV", self.user_player_id)
                self.user_player_id = None
        if active is None:
            active = local

        now = None
        media = getattr(active, "current_media", None) if active is not None else None
        if media is not None and (media.title or media.artist):
            now = self._snapshot(client, active, media)

        new = (active.player_id if active is not None else None, local is not None, now)
        old = (self.active_player_id, self.local_player_found, self.now_playing)
        self.active_player_id, self.local_player_found, self.now_playing = new
        if new != old:
            for cb in list(self._cbs):
                try:
                    cb()
                except Exception:
                    log.exception("playback listener failed")

    def _stamp(self, elapsed: float) -> float:
        """Local time for a position report that came without a timestamp; kept while
        the reported position is unchanged so progress does not jump back on refresh."""
        if self._local_stamp is None or self._local_stamp[0] != elapsed:
            self._local_stamp = (elapsed, time.time())
        return self._local_stamp[1]

    def _snapshot(self, client: Any, active: Any, media: Any) -> NowPlaying:
        queue = None
        queues = getattr(client, "player_queues", None)
        if queues is not None:
            qid = getattr(active, "active_source", None) or active.player_id
            try:
                queue = queues.get(qid)
            except Exception:
                queue = None

        # MA's own queue keeps the accurate position; other sources only report via the player.
        src = queue if queue is not None else media
        elapsed = _num(getattr(src, "elapsed_time", None)) or 0.0
        elapsed_at = _num(getattr(src, "elapsed_time_last_updated", None))
        if not elapsed_at or elapsed_at <= 0:
            elapsed_at = self._stamp(elapsed)
        duration = _num(getattr(media, "duration", None))
        if not duration and queue is not None:
            duration = _num(getattr(getattr(queue, "current_item", None), "duration", None))

        volume = None
        if getattr(active, "volume_control", "none") not in (None, "none"):
            level = _num(getattr(active, "volume_level", None))
            volume = int(level) if level is not None else None

        dark = getattr(getattr(media, "palette", None), "background_dark", None)
        palette = tuple(dark) if isinstance(dark, (tuple, list)) and len(dark) == 3 else None

        next_title, next_artist, next_image = self._next_song(client, queue)

        return NowPlaying(
            title=media.title or "",
            artist=media.artist or "",
            album=media.album or "",
            image_url=media.image_url,
            state=_state_str(active.playback_state),
            duration=duration or None,
            elapsed=elapsed,
            elapsed_at=elapsed_at,
            shuffle=bool(getattr(queue, "shuffle_enabled", False)),
            repeat=_repeat_str(getattr(queue, "repeat_mode", None)),
            volume=volume,
            palette_dark=palette,  # type: ignore[arg-type]
            queue_id=getattr(queue, "queue_id", None),
            uri=getattr(media, "uri", None) or None,
            next_title=next_title,
            next_artist=next_artist,
            next_image_url=next_image,
        )

    @staticmethod
    def _next_song(client: Any, queue: Any) -> tuple[str, str, str | None]:
        """Title, artist and artwork of the queue's next item ("", "", None when unknown)."""
        item = getattr(queue, "next_item", None)
        if item is None:
            return "", "", None
        from couchside.core.library import image_url
        media = getattr(item, "media_item", None)
        title = getattr(media, "name", None) or getattr(item, "name", "") or ""
        artist = getattr(media, "artist_str", None) or ""
        try:
            art = image_url(client, media if media is not None else item)
        except Exception:
            art = None
        return str(title), str(artist), art

    def _ready(self) -> bool:
        return (self._conn.client is not None and self.active_player_id is not None
                and self._conn.state is ConnState.CONNECTED)

    async def _queue_command(self, name: str, *args: Any) -> None:
        np = self.now_playing
        if not self._ready() or np is None or np.queue_id is None:
            return
        try:
            await getattr(self._conn.client.player_queues, name)(np.queue_id, *args)
        except Exception as e:
            log.warning("%s on queue %s failed: %s", name, np.queue_id, e)

    async def toggle_shuffle(self) -> None:
        np = self.now_playing
        if np is not None:
            await self._queue_command("shuffle", not np.shuffle)

    async def cycle_repeat(self) -> None:
        from music_assistant_models.enums import RepeatMode

        np = self.now_playing
        if np is not None:
            await self._queue_command("repeat", RepeatMode(_REPEAT_CYCLE[np.repeat]))

    async def set_volume(self, level: int) -> None:
        if not self._ready():
            return
        level = max(0, min(100, int(level)))
        try:
            await self._conn.client.players.volume_set(self.active_player_id, level)
        except Exception as e:
            log.warning("volume_set on %s failed: %s", self.active_player_id, e)

    async def step_volume(self, delta: int) -> None:
        np = self.now_playing
        if np is not None and np.volume is not None:
            await self.set_volume(np.volume + delta)

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
