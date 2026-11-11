"""The guest web server: the phone page and its JSON + WebSocket API (aiohttp, Qt-free).

Everything lives under /g/<token>/ so the page can use relative URLs and works behind a
reverse proxy at any path. A wrong or old token is 403. Rule violations are 400 with
{"error": message for the guest}; MA not connected is 503.
"""

from __future__ import annotations

import asyncio
import json
import logging
import secrets
import socket
import time
import weakref
from pathlib import Path
from typing import Any, Callable

from aiohttp import WSMsgType, web

from couchside.core import guest_actions
from couchside.core.guests import GuestError, GuestSession

log = logging.getLogger(__name__)

PORT = 8765
MAX_BODY = 16 * 1024
NOT_CONNECTED = "The TV isn't connected to Music Assistant right now — try again in a moment"

# (client, queue id, player id) of the controlled speaker, or None when not connected
Context = Callable[[], tuple[Any, str, str] | None]


def lan_ip(probe: str = "192.168.0.1") -> str:
    """This machine's address on the LAN (no packet is sent)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((probe, 9))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


class GuestServer:
    def __init__(self, get_session: Callable[[], GuestSession | None], get_context: Context,
                 page_path: Path, port: int = PORT, clock: Callable[[], float] = time.time,
                 on_change: Callable[[], None] | None = None):
        self._session = get_session
        self._context = get_context
        self._page = Path(page_path)
        self._port = port
        self._clock = clock
        self._on_change = on_change or (lambda: None)
        self._sockets: weakref.WeakSet = weakref.WeakSet()
        self._runner: web.AppRunner | None = None
        self.app = web.Application(client_max_size=MAX_BODY)
        r = self.app.router
        r.add_get("/", self._root)
        r.add_get("/g/{token}", self._slash)
        r.add_get("/g/{token}/", self._page_handler)
        r.add_post("/g/{token}/api/join", self._join)
        r.add_get("/g/{token}/api/state", self._state)
        r.add_get("/g/{token}/api/search", self._search)
        r.add_post("/g/{token}/api/add", self._add)
        r.add_post("/g/{token}/api/skip", self._skip)
        r.add_post("/g/{token}/api/boost", self._boost)
        r.add_get("/g/{token}/api/ws", self._ws)
        r.add_get("/g/{token}/api/img", self._img)

    # --- lifecycle --------------------------------------------------------------------
    async def start(self) -> None:
        if self._runner is not None:
            return
        self._runner = web.AppRunner(self.app, access_log=None)
        await self._runner.setup()
        await web.TCPSite(self._runner, host="0.0.0.0", port=self._port).start()
        log.info("guest server on port %s", self._port)

    async def stop(self) -> None:
        for ws in list(self._sockets):
            await ws.close()
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None

    def notify_changed(self) -> None:
        """Tell every open phone to refresh (queue/now playing changed)."""
        for ws in list(self._sockets):
            if not ws.closed:
                asyncio.ensure_future(ws.send_json({"type": "changed"}))

    # --- helpers ----------------------------------------------------------------------
    def _check_token(self, request: web.Request) -> GuestSession:
        session = self._session()
        given = request.match_info.get("token", "")
        if session is None or not secrets.compare_digest(given.encode(), session.token.encode()):
            raise web.HTTPForbidden(text=json.dumps({"error": "This link has expired — scan the QR code on the TV again"}),
                                    content_type="application/json")
        return session

    @staticmethod
    def _error(status: int, message: str) -> web.Response:
        return web.json_response({"error": message}, status=status)

    async def _body(self, request: web.Request) -> dict:
        try:
            data = await request.json()
        except Exception:
            raise web.HTTPBadRequest(text=json.dumps({"error": "Bad request"}), content_type="application/json")
        if not isinstance(data, dict):
            raise web.HTTPBadRequest(text=json.dumps({"error": "Bad request"}), content_type="application/json")
        return data

    def _ctx(self):
        ctx = self._context()
        if ctx is None:
            raise web.HTTPServiceUnavailable(text=json.dumps({"error": NOT_CONNECTED}),
                                             content_type="application/json")
        return ctx

    async def _run(self, request: web.Request, action) -> web.Response:
        """Validate, run a guest action, map rule errors to 400."""
        session = self._check_token(request)
        try:
            return await action(session)
        except GuestError as e:
            return self._error(400, str(e))

    # --- pages ------------------------------------------------------------------------
    async def _root(self, request: web.Request) -> web.Response:
        return web.Response(text="Scan the QR code on the TV to add songs.", content_type="text/plain")

    async def _slash(self, request: web.Request) -> web.Response:
        self._check_token(request)
        raise web.HTTPFound(f"{request.match_info['token']}/")

    async def _page_handler(self, request: web.Request) -> web.Response:
        self._check_token(request)
        return web.Response(text=self._page.read_text(encoding="utf-8"), content_type="text/html",
                            headers={"Cache-Control": "no-store"})

    # --- API --------------------------------------------------------------------------
    async def _join(self, request: web.Request) -> web.Response:
        async def act(session):
            data = await self._body(request)
            guest = session.join(data.get("deviceId"), data.get("name"))
            self._on_change()
            return web.json_response({"name": guest.name})
        return await self._run(request, act)

    async def _state(self, request: web.Request) -> web.Response:
        async def act(session):
            guest = session.guest(request.query.get("deviceId", ""))
            client, queue_id, _ = self._ctx()
            return web.json_response(await guest_actions.guest_state(client, queue_id, session, guest))
        return await self._run(request, act)

    async def _search(self, request: web.Request) -> web.Response:
        async def act(session):
            session.guest(request.query.get("deviceId", ""))
            client, _, _ = self._ctx()
            try:
                results = await guest_actions.guest_search(client, request.query.get("q", ""))
            except Exception as e:
                log.warning("guest search failed: %s", e)
                raise GuestError("Search didn't work — try again")
            return web.json_response({"results": results})
        return await self._run(request, act)

    async def _add(self, request: web.Request) -> web.Response:
        async def act(session):
            data = await self._body(request)
            guest = session.guest(data.get("deviceId"))
            client, queue_id, player_id = self._ctx()
            await guest_actions.add_track(client, queue_id, player_id, session, guest,
                                          data.get("uri"), now=self._clock())
            self._on_change()
            return web.json_response({"ok": True})
        return await self._run(request, act)

    async def _skip(self, request: web.Request) -> web.Response:
        async def act(session):
            data = await self._body(request)
            guest = session.guest(data.get("deviceId"))
            client, _, player_id = self._ctx()
            await guest_actions.skip(client, player_id, session, guest)
            self._on_change()
            return web.json_response({"ok": True})
        return await self._run(request, act)

    async def _boost(self, request: web.Request) -> web.Response:
        async def act(session):
            data = await self._body(request)
            guest = session.guest(data.get("deviceId"))
            client, queue_id, _ = self._ctx()
            item_id = data.get("itemId")
            if not isinstance(item_id, str) or len(item_id) > 100:
                raise GuestError("Bad request")
            await guest_actions.boost(client, queue_id, session, guest, item_id)
            self._on_change()
            return web.json_response({"ok": True})
        return await self._run(request, act)

    async def _ws(self, request: web.Request) -> web.StreamResponse:
        self._check_token(request)
        ws = web.WebSocketResponse(heartbeat=30)
        await ws.prepare(request)
        self._sockets.add(ws)
        try:
            async for msg in ws:  # the phone only listens; ignore anything it sends
                if msg.type == WSMsgType.ERROR:
                    break
        finally:
            self._sockets.discard(ws)
        return ws

    async def _img(self, request: web.Request) -> web.StreamResponse:
        """Artwork for phones that can't reach Music Assistant themselves (e.g. via the
        public URL): only MA image-proxy URLs are fetched."""
        self._check_token(request)
        url = request.query.get("u", "")
        ctx = self._context()
        base = getattr(getattr(ctx[0], "server_info", None), "base_url", None) if ctx else None
        if not base or not url.startswith(f"{base}/imageproxy/"):
            return self._error(400, "Bad request")
        import aiohttp

        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8)) as s:
                async with s.get(url) as r:
                    if r.status != 200:
                        return self._error(502, "Image not available")
                    body = await r.read()
                    return web.Response(body=body, content_type=r.content_type or "image/jpeg",
                                        headers={"Cache-Control": "max-age=86400"})
        except Exception:
            return self._error(502, "Image not available")
