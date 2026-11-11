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
from couchside.core.lyrics import HttpClient, LyricsFetcher, TrackInfo
from couchside.core.guest_server import PORT as GUEST_PORT
from couchside.core.guest_server import GuestServer, lan_ip
from couchside.core.guests import GuestRules, GuestSession
from couchside.core.lyrics_text import is_english, romanize
from couchside.core.translate import DeepLTranslator, GoogleTranslator, LibreTranslator
from couchside.core.playback import Playback, find_local_player
from couchside.core.settings import (
    AppSettings,
    load_token,
    normalize_server_url,
    load_secret,
    save_secret,
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
    lyricsChanged = Signal()
    guestChanged = Signal()

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
        self._http = HttpClient()
        self._lyrics_fetcher = LyricsFetcher(self._http.get, ma_lookup=self._ma_lrc)
        self._lyrics_key: str | None = None
        self._lyric_lines: list[dict] = []
        self._lyrics_pending = False
        self._guest_session: GuestSession | None = None
        self._guest_server = None
        self._guest_last_current: str | None = None
        self._raw_lyrics: list = []          # LyricLine list as found, current song
        self._raw_english = False
        self._translation: list[str] | None = None
        self._translations: dict[tuple[str, str], list[str]] = {}  # (song, service)
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

    async def close(self) -> None:
        """Release network resources on shutdown."""
        if self._guest_server is not None:
            await self._guest_server.stop()
        await self._http.close()

    # --- lyrics --------------------------------------------------------------------
    async def _ma_lrc(self, uri: str) -> str | None:
        """LRC stored on the track in MA (MA < schema 101 has no lyrics lookup command)."""
        client = self.conn.client
        if client is None or self.conn.state is not ConnState.CONNECTED:
            return None
        item = await client.music.get_item_by_uri(uri)
        meta = getattr(item, "metadata", None)
        return getattr(meta, "lrc_lyrics", None)

    def _track_key(self) -> str | None:
        np = self.playback.now_playing
        if np is None:
            return None
        # uri + title: a stream keeps its uri while the song (metadata) changes
        return f"{np.uri or ''}|{np.title}|{np.artist}"

    def _check_lyrics(self) -> None:
        key = self._track_key()
        if key == self._lyrics_key:
            return
        self._lyrics_key = key
        self._lyric_lines = []
        self._raw_lyrics = []
        self._translation = None
        np = self.playback.now_playing
        self._lyrics_pending = bool(key and np and self._settings.lyrics_enabled)
        self.lyricsChanged.emit()
        if not self._lyrics_pending:
            return
        info = TrackInfo(key=key, title=np.title, artist=np.artist, album=np.album,
                         duration=np.duration, uri=np.uri)

        async def fetch():
            lines = await self._lyrics_fetcher.get(info)
            if key != self._lyrics_key:
                return  # the song changed while looking: drop it
            self._raw_lyrics = list(lines or [])
            self._raw_english = is_english(self._raw_lyrics)
            self._translation = None
            self._lyrics_pending = False
            self._rebuild_lyrics()
            self._maybe_translate()
        self._spawn(fetch())

    def _rebuild_lyrics(self) -> None:
        """Displayed lines from the raw lyrics + language setting + translation."""
        language = self.lyricsLanguage
        raw = self._raw_lyrics
        if language == "english_only" and not self._raw_english:
            raw = []  # not sung in English: artwork layout
        sub = self._translation if (self._settings.lyrics_translate and self._translation) else None
        self._lyric_lines = [
            {"t": line.time,
             "text": romanize(line.text) if language == "romanized" else line.text,
             "sub": sub[i] if sub and i < len(sub) else ""}
            for i, line in enumerate(raw)]
        self.lyricsChanged.emit()

    def _translator(self):
        service = self._settings.translate_service
        if service == "deepl":
            return DeepLTranslator(self._http, load_secret("deepl_key") or "")
        if service == "libretranslate":
            return LibreTranslator(self._http, self._settings.libretranslate_url or "")
        return GoogleTranslator(self._http)

    def _maybe_translate(self) -> None:
        """English underneath: only when switched on, only for songs not in English."""
        key = self._lyrics_key
        if (not self._settings.lyrics_translate or not self._raw_lyrics or self._raw_english
                or key is None):
            return
        service = self._settings.translate_service
        cached = self._translations.get((key, service))
        if cached is not None:
            self._translation = cached
            self._rebuild_lyrics()
            return
        texts = [line.text for line in self._raw_lyrics]
        translator = self._translator()

        async def run():
            out = await translator.translate(texts)
            if out is None or key != self._lyrics_key or service != self._settings.translate_service:
                return  # failed, or the song / service changed meanwhile
            self._translations[(key, service)] = out
            while len(self._translations) > 100:
                self._translations.pop(next(iter(self._translations)))
            self._translation = out
            self._rebuild_lyrics()
        self._spawn(run())

    _LANGUAGES = ("romanized", "original", "english_only")
    _SERVICES = ("google", "deepl", "libretranslate")

    @Property(str, notify=lyricsChanged)
    def lyricsLanguage(self) -> str:
        lang = self._settings.lyrics_language
        return lang if lang in self._LANGUAGES else "romanized"

    @Slot()
    def cycleLyricsLanguage(self) -> None:
        langs = self._LANGUAGES
        self._settings.lyrics_language = langs[(langs.index(self.lyricsLanguage) + 1) % len(langs)]
        save_settings(self._settings)
        self._rebuild_lyrics()

    @Property(bool, notify=lyricsChanged)
    def lyricsTranslate(self) -> bool:
        return self._settings.lyrics_translate

    @Slot()
    def toggleLyricsTranslate(self) -> None:
        self._settings.lyrics_translate = not self._settings.lyrics_translate
        save_settings(self._settings)
        self._rebuild_lyrics()
        self._maybe_translate()

    @Property(str, notify=lyricsChanged)
    def translateService(self) -> str:
        svc = self._settings.translate_service
        return svc if svc in self._SERVICES else "google"

    @Slot()
    def cycleTranslateService(self) -> None:
        svcs = self._SERVICES
        self._settings.translate_service = svcs[(svcs.index(self.translateService) + 1) % len(svcs)]
        save_settings(self._settings)
        self._translation = None
        self._rebuild_lyrics()
        self._maybe_translate()

    @Property(bool, notify=lyricsChanged)
    def hasDeeplKey(self) -> bool:
        return load_secret("deepl_key") is not None

    @Slot(str)
    def saveDeeplKey(self, key: str) -> None:
        if key.strip():
            save_secret("deepl_key", key)
        self.lyricsChanged.emit()
        self._maybe_translate()

    @Property(str, notify=lyricsChanged)
    def libretranslateUrl(self) -> str:
        return self._settings.libretranslate_url or ""

    @Slot(str)
    def setLibretranslateUrl(self, url: str) -> None:
        self._settings.libretranslate_url = url.strip() or None
        save_settings(self._settings)
        self.lyricsChanged.emit()
        self._maybe_translate()

    @Property(bool, notify=lyricsChanged)
    def lyricsPending(self) -> bool:
        """A lookup for the current song is running (QML holds the layout meanwhile)."""
        return self._lyrics_pending

    @Property(bool, notify=lyricsChanged)
    def hasLyrics(self) -> bool:
        return bool(self._lyric_lines)

    @Property("QVariantList", notify=lyricsChanged)
    def lyricLines(self) -> list:
        return self._lyric_lines

    @Property(bool, notify=lyricsChanged)
    def lyricsEnabled(self) -> bool:
        return self._settings.lyrics_enabled

    _LYRICS_SIZES = ("small", "medium", "large")

    @Property(str, notify=lyricsChanged)
    def lyricsSize(self) -> str:
        size = self._settings.lyrics_size
        return size if size in self._LYRICS_SIZES else "medium"

    @Slot()
    def cycleLyricsSize(self) -> None:
        sizes = self._LYRICS_SIZES
        self._settings.lyrics_size = sizes[(sizes.index(self.lyricsSize) + 1) % len(sizes)]
        save_settings(self._settings)
        self.lyricsChanged.emit()

    @lyricsEnabled.setter
    def lyricsEnabled(self, enabled: bool) -> None:
        self._settings.lyrics_enabled = bool(enabled)
        save_settings(self._settings)
        self._lyrics_key = None  # look again for the current song (or clear when off)
        self._lyric_lines = []
        self.lyricsChanged.emit()
        self._check_lyrics()

    def _on_update(self) -> None:
        self._check_lyrics()
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
        self._notify_guests(kind, getattr(event, "object_id", None))
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

    def _notify_guests(self, kind: str, object_id) -> None:
        """Phones refresh when the controlled queue's items or current song change."""
        if self._guest_server is None or self._guest_session is None:
            return
        if kind not in _QUEUE_EVENTS or object_id not in (None, self._queue_id()):
            return
        current = self._current_item_id(self._queue_id())
        if kind == "queue_items_updated" or current != self._guest_last_current:
            self._guest_last_current = current
            self._guest_server.notify_changed()
            self.guestChanged.emit()

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
                                 "current": r.current, "addedBy": self._added_by(r.item_id)}
                                for r in rows]
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

    # --- guest mode --------------------------------------------------------------
    def _added_by(self, item_id: str | None) -> str:
        return (self._guest_session.added_by(item_id) if self._guest_session else None) or ""

    def _guest_rules(self) -> GuestRules:
        st = self._settings
        return GuestRules(skips=st.guest_skips, boosts=st.guest_boosts,
                          max_waiting=st.guest_max_waiting, cooldown=float(st.guest_cooldown))

    def _guest_context(self):
        client, pid = self.conn.client, self.playback.active_player_id
        if client is None or pid is None or self.conn.state is not ConnState.CONNECTED:
            return None
        return client, self._queue_id() or pid, pid

    def _make_guest_server(self):
        from pathlib import Path

        import couchside
        page = Path(couchside.__file__).parent / "web" / "guest.html"
        return GuestServer(lambda: self._guest_session, self._guest_context, page,
                           on_change=self.guestChanged.emit)

    @Property(bool, notify=guestChanged)
    def guestMode(self) -> bool:
        return self._guest_session is not None

    @Slot()
    def toggleGuestMode(self) -> None:
        if self._guest_session is None:
            self._guest_session = GuestSession(self._guest_rules())  # fresh token = new QR
            if self._guest_server is None:
                self._guest_server = self._make_guest_server()
            server = self._guest_server

            async def start():
                try:
                    await server.start()
                except OSError as e:
                    log.warning("guest server failed to start: %s", e)
                    self._guest_session = None
                    self._set_toast(f"Couldn't start guest mode (port {GUEST_PORT} busy?)")
                    self.guestChanged.emit()
            self._spawn(start())
        else:
            self._guest_session = None
            if self._guest_server is not None:
                self._spawn(self._guest_server.stop())
        self.guestChanged.emit()
        self.queueChanged.emit()

    @Property(str, notify=guestChanged)
    def guestUrl(self) -> str:
        if self._guest_session is None:
            return ""
        base = (self._settings.guest_public_url or "").strip().rstrip("/")
        if not base:
            host = None
            url = self._settings.server_url
            if url:
                from urllib.parse import urlsplit
                host = urlsplit(url).hostname
            base = f"http://{lan_ip(host or '192.168.0.1')}:{GUEST_PORT}"
        return f"{base}/g/{self._guest_session.token}/"

    @Property("QVariantList", notify=guestChanged)
    def qrRows(self) -> list:
        url = self.guestUrl
        if not url:
            return []
        import segno
        return ["".join("1" if m else "0" for m in row) for row in segno.make(url, error="m").matrix]

    @Property(str, notify=guestChanged)
    def nowPlayingCredit(self) -> str:
        return self._added_by(self._current_item_id(self._queue_id()))

    @Property(int, notify=guestChanged)
    def guestCount(self) -> int:
        return len(self._guest_session.guests) if self._guest_session else 0

    @Property(str, notify=guestChanged)
    def qrCaption(self) -> str:
        return self._settings.qr_caption

    @Slot(str)
    def setQrCaption(self, text: str) -> None:
        self._settings.qr_caption = text.strip()[:60] or "Scan to add songs"
        save_settings(self._settings)
        self.guestChanged.emit()

    @Property(str, notify=guestChanged)
    def guestPublicUrl(self) -> str:
        return self._settings.guest_public_url or ""

    @Slot(str)
    def setGuestPublicUrl(self, url: str) -> None:
        self._settings.guest_public_url = url.strip().rstrip("/") or None
        save_settings(self._settings)
        self.guestChanged.emit()

    def _cycle_rule(self, field: str, choices: tuple[int, ...]) -> None:
        value = getattr(self._settings, field)
        later = [c for c in choices if c > value]
        setattr(self._settings, field, later[0] if later else choices[0])
        save_settings(self._settings)
        if self._guest_session is not None:
            self._guest_session.rules = self._guest_rules()  # applies straight away
        self.guestChanged.emit()

    @Property(int, notify=guestChanged)
    def guestSkips(self) -> int:
        return self._settings.guest_skips

    @Slot()
    def cycleGuestSkips(self) -> None:
        self._cycle_rule("guest_skips", (0, 1, 2, 3, 5, 10))

    @Property(int, notify=guestChanged)
    def guestBoosts(self) -> int:
        return self._settings.guest_boosts

    @Slot()
    def cycleGuestBoosts(self) -> None:
        self._cycle_rule("guest_boosts", (0, 1, 2, 3, 5))

    @Property(int, notify=guestChanged)
    def guestMaxWaiting(self) -> int:
        return self._settings.guest_max_waiting

    @Slot()
    def cycleGuestMaxWaiting(self) -> None:
        self._cycle_rule("guest_max_waiting", (1, 2, 3, 5, 10))

    @Property(int, notify=guestChanged)
    def guestCooldown(self) -> int:
        return self._settings.guest_cooldown

    @Slot()
    def cycleGuestCooldown(self) -> None:
        self._cycle_rule("guest_cooldown", (0, 30, 60, 120, 300))

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
