"""Music Assistant connection manager: discovery/URL, token auth, backoff, status."""

from __future__ import annotations

import asyncio
import logging
from enum import StrEnum
from typing import Any, Awaitable, Callable, Protocol

from music_assistant_models.errors import (
    AuthenticationFailed,
    AuthenticationRequired,
    MusicAssistantError,
)

log = logging.getLogger(__name__)

BACKOFF = [1, 2, 4, 8, 16, 30]
INIT_TIMEOUT = 30.0  # seconds for MA's initial state fetch after connecting


def is_login_rejected(err: Exception) -> bool:
    """True when the server refused the token, False for a transport hiccup during login.

    music-assistant-client wraps *any* error from the `auth` command in
    AuthenticationFailed; the server's own refusal arrives as a MusicAssistantError
    cause (e.g. InvalidToken), a dropped socket or timeout as something else.
    """
    cause = err.__cause__
    return cause is None or isinstance(cause, MusicAssistantError)


class ConnState(StrEnum):
    IDLE = "idle"
    DISCOVERING = "discovering"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    AUTH_FAILED = "auth_failed"
    NO_SERVER = "no_server"


class ClientLike(Protocol):
    async def connect(self) -> None: ...
    async def start_listening(self, init_ready: asyncio.Event | None = None) -> None: ...
    async def disconnect(self) -> None: ...
    def subscribe(self, cb: Callable[[Any], None], event_filter: Any = None,
                  id_filter: Any = None) -> Callable[[], None]: ...
    # Used by Playback (Task 5): players, player_queues


def default_factory(url: str, token: str | None) -> ClientLike:
    from music_assistant_client import MusicAssistantClient

    # The client creates/owns its own aiohttp session when given None.
    return MusicAssistantClient(url, None, token=token)


class Connection:
    def __init__(
        self,
        get_url: Callable[[], Awaitable[str | None]],
        get_token: Callable[[], str | None],
        client_factory: Callable[[str, str | None], ClientLike] = default_factory,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        init_timeout: float = INIT_TIMEOUT,
    ) -> None:
        self._init_timeout = init_timeout
        self._get_url = get_url
        self._get_token = get_token
        self._factory = client_factory
        self._sleep = sleep
        self.state = ConnState.IDLE
        self.client: ClientLike | None = None
        self._state_cbs: list[Callable[[ConnState], None]] = []
        self._event_cbs: list[Callable[[Any], None]] = []
        self._wake = asyncio.Event()
        self._stopped = False
        self._attempt = 0
        self._ever_connected = False

    # --- listeners -------------------------------------------------------
    def on_state(self, cb: Callable[[ConnState], None]) -> None:
        self._state_cbs.append(cb)

    def on_event(self, cb: Callable[[Any], None]) -> None:
        self._event_cbs.append(cb)

    def _set_state(self, state: ConnState) -> None:
        if state is self.state:
            return
        self.state = state
        for cb in list(self._state_cbs):
            try:
                cb(state)
            except Exception:
                log.exception("state listener failed")

    def _emit(self, event: Any) -> None:
        for cb in list(self._event_cbs):
            try:
                cb(event)
            except Exception:
                log.exception("event listener failed")

    # --- control ---------------------------------------------------------
    def retry_now(self) -> None:
        self._attempt = 0
        self._wake.set()

    async def stop(self) -> None:
        self._stopped = True
        self._wake.set()
        client = self.client
        if client is not None:
            await client.disconnect()

    async def _backoff(self) -> None:
        delay = BACKOFF[min(self._attempt, len(BACKOFF) - 1)]
        self._attempt += 1
        await self._wait(self._sleep(delay))

    async def _wait(self, awaitable: Awaitable[None] | None) -> None:
        """Wait for `awaitable` (or forever if None), cut short by retry_now()/stop().

        `_wake` is cleared only at the top of each attempt, so a retry_now() that
        arrives mid-attempt (discovery, connect) still cuts the next wait short.
        """
        waiters = [asyncio.ensure_future(self._wake.wait())]
        if awaitable is not None:
            waiters.append(asyncio.ensure_future(awaitable))
        try:
            await asyncio.wait(waiters, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for w in waiters:
                w.cancel()

    # --- main loop -------------------------------------------------------
    async def run(self) -> None:
        while not self._stopped:
            self._wake.clear()
            try:
                url = await self._get_url()
            except Exception as e:
                log.warning("Finding the MA server failed (%s): %s", type(e).__name__, e)
                url = None
            if self._stopped:
                break
            if not url:
                self._set_state(ConnState.NO_SERVER)
                await self._backoff()
                continue
            token = self._get_token()
            if not token:
                self._set_state(ConnState.AUTH_FAILED)
                await self._wait(None)
                continue

            self._set_state(ConnState.RECONNECTING if self._ever_connected else ConnState.CONNECTING)
            client = self._factory(url, token)
            try:
                await client.connect()
            except AuthenticationFailed as e:
                if not is_login_rejected(e):
                    log.info("MA login interrupted, retrying: %s", e)
                    await self._backoff()
                    continue
                log.warning("MA login failed: %s", e)
                self._set_state(ConnState.AUTH_FAILED)
                await self._wait(None)
                continue
            except AuthenticationRequired as e:
                log.warning("MA login failed: %s", e)
                self._set_state(ConnState.AUTH_FAILED)
                await self._wait(None)
                continue
            except Exception as e:
                log.info("MA connect failed (%s): %s", type(e).__name__, e)
                await self._backoff()
                continue

            await self._listen(client)
            if self._wake.is_set() and not self._stopped:
                continue  # retry_now(): reconnect straight away (e.g. new URL/token)
            if not self._stopped:
                self._set_state(ConnState.RECONNECTING)
                await self._backoff()
        self._set_state(ConnState.IDLE)

    async def _listen(self, client: ClientLike) -> None:
        init_ready = asyncio.Event()
        unsubscribe = client.subscribe(self._emit)
        listener = asyncio.ensure_future(client.start_listening(init_ready))
        ready = asyncio.ensure_future(init_ready.wait())
        wake = asyncio.ensure_future(self._wake.wait())
        try:
            await asyncio.wait([listener, ready, wake], timeout=self._init_timeout,
                               return_when=asyncio.FIRST_COMPLETED)
            if wake.done() or listener.done():
                pass
            elif not init_ready.is_set():
                log.warning("MA initial state not received within %ss; reconnecting",
                            self._init_timeout)
            else:
                self.client = client
                self._attempt = 0
                self._ever_connected = True
                self._set_state(ConnState.CONNECTED)
                # Runs until the socket drops or retry_now()/stop() asks to reconnect.
                await asyncio.wait([listener, wake], return_when=asyncio.FIRST_COMPLETED)
            if listener.done() and not listener.cancelled() and listener.exception():
                e = listener.exception()
                log.info("MA connection lost (%s): %s", type(e).__name__, e)
        finally:
            ready.cancel()
            wake.cancel()
            if not listener.done():
                listener.cancel()
            self.client = None
            try:
                unsubscribe()
            except Exception:
                pass
            try:
                await client.disconnect()
            except Exception:
                pass
