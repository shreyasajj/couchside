"""AppController: the single QObject QML talks to."""

from __future__ import annotations

import asyncio
import logging

from PySide6.QtCore import Property, QObject, Signal, Slot

from couchside.core.connection import Connection, ConnState
from couchside.core.discovery import choose_server, discover_mass
from couchside.core.paths import sendspin_settings_dir
from couchside.core import library, queue, speakers
from couchside.core.format import art_url, format_time, palette_colour
from couchside.core.playback import Playback, find_local_player
from couchside.core.settings import (
    AppSettings,
    load_token,
    normalize_server_url,
    save_settings,
    save_token,
)
from couchside.core.status import needs_setup, status_text
from couchside.sendspin.identity import read_client_id
from couchside.sendspin.pairing import PairingEvent

log = logging.getLogger(__name__)


_FAIL_TEXT = {
    "now": "Couldn't play that", "next": "Couldn't add it as next", "add": "Couldn't add to the queue",
    "play": "Couldn't play that song", "up": "Couldn't move it", "down": "Couldn't move it",
    "remove": "Couldn't remove it", "sync": "Couldn't sync that speaker",
    "unsync": "Couldn't stop syncing", "transfer": "Couldn't move the queue",
    "create_group": "Couldn't create the group", "edit_group": "Couldn't change the group",
    "delete_group": "Couldn't delete the group",
}
_QUEUE_EVENTS = {"queue_items_updated", "queue_updated"}
_PLAYER_EVENTS = {"player_added", "player_updated", "player_removed"}


def _card(c: library.MediaCard) -> dict:
    return {"key": c.key, "kind": c.kind, "title": c.title, "subtitle": c.subtitle,
            "imageUrl": art_url(c.image_url, 256), "uri": c.uri}


class AppController(QObject):
    changed = Signal()
    libraryChanged = Signal()
    queueChanged = Signal()
    speakersChanged = Signal()
    toastChanged = Signal()

    def __init__(self, settings: AppSettings, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._client_id: str | None = None
        self._pairing_code = ""
        self._pairing_error = ""
        self._tasks: set[asyncio.Task] = set()
        # Discovered server we last connected to: kept for this run so a network blip
        # never moves us to another MA server (where the token would fail).
        self._preferred_server_id: str | None = None
        self._pending_server_id: str | None = None
        self.conn = Connection(self._get_url, load_token)
        self.playback = Playback(self.conn, self._get_client_id)
        self._library_rows: list[dict] = []
        self._library_error = ""
        self._library_busy = False
        self._search_gen = 0
        self._queue_rows: list[dict] = []
        self._queue_visible = False
        self._toast = ""
        self._last_speaker_rows: list[dict] = []
        self._last_current_item: str | None = None
        self._last_queue_id: str | None = None
        self.conn.on_state(lambda _s: self._on_update())
        self.conn.on_event(self._on_event)
        self.playback.on_change(self._on_update)

    # --- core hooks ------------------------------------------------------
    async def _get_url(self) -> str | None:
        if self._settings.server_url:
            return self._settings.server_url
        server = choose_server(await discover_mass(), self._preferred_server_id)
        self._pending_server_id = server.server_id if server else None
        return server.base_url if server else None

    def _get_client_id(self) -> str | None:
        if self._client_id is None:
            self._client_id = read_client_id(sendspin_settings_dir())
        return self._client_id

    def on_pairing_event(self, event: PairingEvent, value: str) -> None:
        if event is PairingEvent.CODE:
            self._pairing_code, self._pairing_error = value, ""
        elif event is PairingEvent.FAILED:
            self._pairing_code, self._pairing_error = "", f"Pairing failed: {value}"
        elif event is PairingEvent.STARTED:
            self._client_id = value
            self.playback.refresh()
        self.changed.emit()

    def _on_update(self) -> None:
        self._emit_speakers_if_changed()  # controlled speaker may have changed
        qid = self._queue_id()
        if qid != self._last_queue_id:
            self._last_queue_id = qid
            self._last_current_item = None
            if self._queue_visible:
                self.loadQueue()  # the Queue page follows the controlled speaker
        if self.conn.state is ConnState.CONNECTED and self._pending_server_id:
            self._preferred_server_id = self._pending_server_id
        if self.playback.local_player_found and self._pairing_code:
            self._pairing_code = ""
        self.changed.emit()

    def _on_event(self, event) -> None:
        kind = str(getattr(getattr(event, "event", None), "value", "") or "")
        if kind in _PLAYER_EVENTS:
            self._emit_speakers_if_changed()
        if self._queue_visible and kind in _QUEUE_EVENTS:
            if getattr(event, "object_id", None) not in (None, self._queue_id()):
                return
            # queue_updated arrives several times a second; reload only when the
            # items or the current song changed (keeps the remote's focus steady).
            current = self._current_item_id(self._queue_id())
            if kind == "queue_items_updated" or current != self._last_current_item:
                self._last_current_item = current
                self.loadQueue()

    def _emit_speakers_if_changed(self) -> None:
        rows = self._speaker_rows()
        if rows != self._last_speaker_rows:
            self._last_speaker_rows = rows
            self.speakersChanged.emit()

    def _local_id(self) -> str | None:
        client, cid = self.conn.client, self._get_client_id()
        if client is None or not cid:
            return None
        local = find_local_player(list(client.players), cid)
        return local.player_id if local is not None else None

    def _queue_id(self) -> str | None:
        """The controlled speaker's MA queue (its active source if that is a queue)."""
        client, pid = self.conn.client, self.playback.active_player_id
        if client is None or pid is None:
            return None
        player = client.players.get(pid)
        source = getattr(player, "active_source", None)
        try:
            if source and client.player_queues.get(source) is not None:
                return source
        except Exception:
            pass
        return pid

    def _current_item_id(self, queue_id: str | None) -> str | None:
        client = self.conn.client
        try:
            q = client.player_queues.get(queue_id) if client is not None and queue_id else None
        except Exception:
            q = None
        return getattr(getattr(q, "current_item", None), "queue_item_id", None)

    def _set_toast(self, text: str) -> None:
        self._toast = text
        self.toastChanged.emit()

    async def _run(self, coro, action: str, after=None) -> None:
        ok = await coro
        if not ok:
            self._set_toast(_FAIL_TEXT.get(action, "That didn't work"))
        if after is not None:
            after()

    def _spawn(self, coro) -> None:
        task = asyncio.ensure_future(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    # --- properties ------------------------------------------------------
    def _np(self, attr: str, default=""):
        np = self.playback.now_playing
        return getattr(np, attr) if np is not None else default

    @Property(str, notify=changed)
    def connState(self) -> str:
        return str(self.conn.state)

    @Property(str, notify=changed)
    def statusText(self) -> str:
        if self._pairing_error:
            return self._pairing_error
        return status_text(self.conn.state, self.playback.local_player_found,
                           has_token=load_token() is not None)

    @Property(str, notify=changed)
    def title(self) -> str:
        return self._np("title")

    @Property(str, notify=changed)
    def artist(self) -> str:
        return self._np("artist")

    @Property(str, notify=changed)
    def album(self) -> str:
        return self._np("album")

    @Property(str, notify=changed)
    def artUrl(self) -> str:
        return art_url(self._np("image_url", None), 600)

    @Property(str, notify=changed)
    def artUrlLarge(self) -> str:
        return art_url(self._np("image_url", None), 1024)

    @Property(float, notify=changed)
    def duration(self) -> float:
        return float(self._np("duration", None) or 0)

    @Property(bool, notify=changed)
    def hasDuration(self) -> bool:
        return bool(self._np("duration", None))

    @Property(float, notify=changed)
    def positionBase(self) -> float:
        return float(self._np("elapsed", 0.0))

    @Property(float, notify=changed)
    def positionAt(self) -> float:
        return float(self._np("elapsed_at", 0.0))

    @Property(bool, notify=changed)
    def shuffle(self) -> bool:
        return bool(self._np("shuffle", False))

    @Property(str, notify=changed)
    def repeatMode(self) -> str:
        return self._np("repeat", "off")

    @Property(int, notify=changed)
    def volume(self) -> int:
        v = self._np("volume", None)
        return -1 if v is None else int(v)

    @Property(bool, notify=changed)
    def hasVolume(self) -> bool:
        return self._np("volume", None) is not None

    @Property(str, notify=changed)
    def backgroundColour(self) -> str:
        return palette_colour(self._np("palette_dark", None))

    @Property(bool, notify=changed)
    def isPlaying(self) -> bool:
        return self._np("state", "idle") == "playing"

    @Property(bool, notify=changed)
    def hasLocalPlayer(self) -> bool:
        return self.playback.local_player_found

    @Property(str, notify=changed)
    def pairingCode(self) -> str:
        return self._pairing_code

    @Property(str, notify=changed)
    def serverUrl(self) -> str:
        return self._settings.server_url or ""

    @Property(bool, notify=changed)
    def hasToken(self) -> bool:
        return load_token() is not None

    @Property(bool, notify=changed)
    def needsSetup(self) -> bool:
        return needs_setup(self.conn.state, has_token=load_token() is not None)

    # --- slots -----------------------------------------------------------
    @Slot()
    def playPause(self) -> None:
        self._spawn(self.playback.play_pause())

    @Slot()
    def next(self) -> None:
        self._spawn(self.playback.next())

    @Slot()
    def previous(self) -> None:
        self._spawn(self.playback.previous())

    @Slot()
    def toggleShuffle(self) -> None:
        self._spawn(self.playback.toggle_shuffle())

    @Slot()
    def cycleRepeat(self) -> None:
        self._spawn(self.playback.cycle_repeat())

    @Slot(int)
    def setVolume(self, level: int) -> None:
        self._spawn(self.playback.set_volume(level))

    @Slot()
    def volumeUp(self) -> None:
        self._spawn(self.playback.step_volume(5))

    @Slot()
    def volumeDown(self) -> None:
        self._spawn(self.playback.step_volume(-5))

    @Slot(float, result=str)
    def formatTime(self, seconds: float) -> str:
        return format_time(seconds)

    # --- library ---------------------------------------------------------------
    @Property("QVariantList", notify=libraryChanged)
    def libraryRows(self) -> list:
        return self._library_rows

    @Property(str, notify=libraryChanged)
    def libraryError(self) -> str:
        return self._library_error

    @Property(bool, notify=libraryChanged)
    def libraryBusy(self) -> bool:
        return self._library_busy

    def _set_library(self, rows, error: str = "", busy: bool = False) -> None:
        self._library_rows = [{"title": t, "items": [_card(c) for c in cards]} for t, cards in rows]
        self._library_error, self._library_busy = error, busy
        self.libraryChanged.emit()

    @Slot(str)
    def search(self, query: str) -> None:
        self._search_gen += 1
        gen = self._search_gen
        if not query.strip():
            self.loadRecents()
            return
        self._library_busy = True
        self.libraryChanged.emit()

        async def run():
            client = self.conn.client
            out = await library.search(client, query) if client is not None else \
                library.SearchOutcome(error=library.SEARCH_ERROR)
            if gen == self._search_gen:  # a newer search wins
                self._set_library(out.rows, out.error)
        self._spawn(run())

    @Slot()
    def loadRecents(self) -> None:
        self._search_gen += 1
        gen = self._search_gen
        self._library_busy = True
        self.libraryChanged.emit()

        async def run():
            client = self.conn.client
            rows = await library.recents(client) if client is not None else []
            if gen == self._search_gen:
                self._set_library(rows)
        self._spawn(run())

    @Slot(str, str)
    def playUri(self, uri: str, mode: str) -> None:
        client, pid = self.conn.client, self.playback.active_player_id
        if client is None or pid is None:
            self._set_toast(_FAIL_TEXT.get(mode, "That didn't work"))
            return

        async def done():
            return await library.play(client, pid, uri, mode)
        self._spawn(self._run(done(), mode, after=self.loadQueue if self._queue_visible else None))

    # --- queue -----------------------------------------------------------------
    @Property("QVariantList", notify=queueChanged)
    def queueRows(self) -> list:
        return self._queue_rows

    @Property(bool, notify=queueChanged)
    def queueVisible(self) -> bool:
        return self._queue_visible

    @queueVisible.setter
    def queueVisible(self, visible: bool) -> None:
        self._queue_visible = bool(visible)
        if visible:
            self.loadQueue()

    @Slot()
    def loadQueue(self) -> None:
        client = self.conn.client
        qid = self._queue_id()

        async def run():
            rows = await queue.load_queue(client, qid, self._current_item_id(qid)) if client else []
            self._queue_rows = [{"itemId": r.item_id, "title": r.title, "subtitle": r.subtitle,
                                 "imageUrl": art_url(r.image_url, 256), "duration": r.duration or 0,
                                 "current": r.current} for r in rows]
            self.queueChanged.emit()
        self._spawn(run())

    @Slot(str, str)
    def queueAction(self, item_id: str, action: str) -> None:
        client = self.conn.client
        if client is None:
            self._set_toast(_FAIL_TEXT.get(action, "That didn't work"))
            return
        self._spawn(self._run(queue.queue_action(client, self._queue_id(), item_id, action),
                              action, after=self.loadQueue))

    # --- speakers --------------------------------------------------------------
    @Property("QVariantList", notify=speakersChanged)
    def speakerRows(self) -> list:
        return self._speaker_rows()

    def _speaker_rows(self) -> list:
        client = self.conn.client
        if client is None:
            return []
        rows = speakers.speaker_rows(list(client.players), self.playback.active_player_id, self._local_id())
        return [{"playerId": r.player_id, "name": r.name, "isGroup": r.is_group,
                 "available": r.available, "controlled": r.controlled, "local": r.local,
                 "syncedTo": r.synced_to or "", "members": list(r.members),
                 "canSync": r.can_sync, "playing": r.playing} for r in rows]

    @Slot(str)
    def controlSpeaker(self, player_id: str) -> None:
        self.playback.user_player_id = player_id or None
        self.playback.refresh()
        self._emit_speakers_if_changed()
        if self._queue_visible:
            self.loadQueue()

    def _speaker(self, player_id: str, action: str, members=()) -> None:
        client = self.conn.client
        if client is None:
            self._set_toast(_FAIL_TEXT.get(action, "That didn't work"))
            return
        coro = speakers.speaker_action(client, self.playback.active_player_id, player_id, action, members)
        self._spawn(self._run(coro, action, after=self._emit_speakers_if_changed))

    @Slot(str, str)
    def speakerAction(self, player_id: str, action: str) -> None:
        self._speaker(player_id, action)

    @Slot("QVariantList")
    def createGroup(self, member_ids: list) -> None:
        self._speaker("", "create_group", [str(m) for m in member_ids])

    @Slot(str, "QVariantList")
    def editGroup(self, group_id: str, member_ids: list) -> None:
        self._speaker(group_id, "edit_group", [str(m) for m in member_ids])

    # --- toast -----------------------------------------------------------------
    @Property(str, notify=toastChanged)
    def toast(self) -> str:
        return self._toast

    @Slot()
    def clearToast(self) -> None:
        self._set_toast("")

    @Slot(str, str)
    def saveConnection(self, url: str, token: str) -> None:
        self._settings.server_url = normalize_server_url(url)
        save_settings(self._settings)
        if token.strip():
            save_token(token)
        self.conn.retry_now()
        self.changed.emit()
