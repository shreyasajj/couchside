"""AppController: the single QObject QML talks to."""

from __future__ import annotations

import asyncio
import logging

from PySide6.QtCore import Property, QObject, Signal, Slot

from couchside.core.connection import Connection, ConnState
from couchside.core.discovery import choose_server, discover_mass
from couchside.core.paths import sendspin_settings_dir
from couchside.core.playback import Playback
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


class AppController(QObject):
    changed = Signal()

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
        self.conn.on_state(lambda _s: self._on_update())
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
        if self.conn.state is ConnState.CONNECTED and self._pending_server_id:
            self._preferred_server_id = self._pending_server_id
        if self.playback.local_player_found and self._pairing_code:
            self._pairing_code = ""
        self.changed.emit()

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
        return self._np("image_url") or ""

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

    @Slot(str, str)
    def saveConnection(self, url: str, token: str) -> None:
        self._settings.server_url = normalize_server_url(url)
        save_settings(self._settings)
        if token.strip():
            save_token(token)
        self.conn.retry_now()
        self.changed.emit()
