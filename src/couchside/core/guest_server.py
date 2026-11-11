"""The guest web server: the phone page and its JSON + WebSocket API (aiohttp, Qt-free).

Everything lives under /g/<token>/ so the page can use relative URLs and works behind a
reverse proxy at any path. A wrong or old token is 403. Rule violations are 400 with
{"error": message for the guest}; MA not connected is 503.
"""

from __future__ import annotations

import asyncio
import json
import ipaddress
import logging
import re
import secrets
import socket
import time
import weakref
from pathlib import Path
from typing import Any, Callable

from aiohttp import WSMsgType, web

from couchside.core import admin_actions, guest_actions
from couchside.core.admin_actions import AdminHost
from couchside.core.guests import GuestError, GuestSession, NotAdmin

log = logging.getLogger(__name__)

PORT = 8765
MAX_BODY = 16 * 1024
MAX_SOCKETS = 100             # open WebSockets (each phone holds one)
DEVICES_PER_ADDRESS = 3       # on the LAN: phones per network address (stops one phone
                              # posing as many guests); off behind a reverse proxy
MAX_IMAGE = 2 * 1024 * 1024
IMAGE_SIZES = ("256", "512", "1024")
_PROXY_ID = re.compile(r"^/imageproxy/[A-Za-z0-9_-]{1,128}$")
NOT_CONNECTED = "The TV isn't connected to Music Assistant right now — try again in a moment"

# (client, queue id, player id) of the controlled speaker, or None when not connected
Context = Callable[[], tuple[Any, str, str] | None]


class RateLimiter:
    """Token buckets: `burst` requests at once, then one every `per` seconds."""

    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self._clock = clock
        self._buckets: dict[tuple, tuple[float, float]] = {}

    def allow(self, key: tuple, burst: int, per: float) -> bool:
        now = self._clock()
        tokens, last = self._buckets.get(key, (float(burst), now))
        tokens = min(float(burst), tokens + (now - last) / per)
        if tokens < 1:
            self._buckets[key] = (tokens, now)
            return False
        self._buckets[key] = (tokens - 1, now)
        if len(self._buckets) > 5000:  # forget the oldest keys
            for k in list(self._buckets)[:1000]:
                del self._buckets[k]
        return True


def is_loopback(ip: str) -> bool:
    try:
        return ipaddress.ip_address(ip).is_loopback
    except ValueError:
        return False


def lan_ip(probe: str = "192.168.0.1") -> str:
    """This machine's address on the LAN (no packet is sent). Blocking (may resolve a
    host name): call it off the UI thread. Falls back to a public probe when the answer
    would be loopback (e.g. Music Assistant on this same box)."""
    for target in (probe, "192.168.0.1", "8.8.8.8"):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect((target, 9))
            ip = s.getsockname()[0]
            if not is_loopback(ip):
                return ip
        except OSError:
            pass
        finally:
            s.close()
    return "127.0.0.1"


class GuestServer:
    def __init__(self, get_session: Callable[[], GuestSession | None], get_context: Context,
                 page_path: Path, port: int = PORT, clock: Callable[[], float] = time.time,
                 on_change: Callable[[], None] | None = None,
                 limit_per_address: Callable[[], bool] = lambda: True,
                 get_admin_host: Callable[[], AdminHost | None] = lambda: None,
                 on_admin_event: Callable[[str, str], None] | None = None):
        self._limit_per_address = limit_per_address
        self._admin_host = get_admin_host
        # ("admin", name) when a code is used; ("code_cancelled", "") after too many wrong tries
        self._on_admin_event = on_admin_event or (lambda kind, name: None)
        self._limits = RateLimiter()
        self._addresses: dict[tuple[str, str], set[str]] = {}  # (token, ip) -> device ids
        self._lifecycle = asyncio.Lock()
        self._http = None
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
        r.add_post("/g/{token}/api/code", self._code)
        r.add_post("/g/{token}/api/admin/queue", self._admin_queue)
        r.add_post("/g/{token}/api/admin/shuffle", self._admin_shuffle)
        r.add_post("/g/{token}/api/admin/volume", self._admin_volume)
        r.add_post("/g/{token}/api/admin/speaker", self._admin_speaker)
        r.add_post("/g/{token}/api/admin/guest", self._admin_guest)

    # --- lifecycle --------------------------------------------------------------------
    async def start(self) -> None:
        """Start listening (a no-op when already running). Start and stop take turns, so a
        quick off/on always ends with the server running; a failed bind leaves nothing
        half-started behind, so the next start can try again."""
        async with self._lifecycle:
            if self._runner is not None:
                return
            runner = web.AppRunner(self.app, access_log=None)
            await runner.setup()
            try:
                await web.TCPSite(runner, host="0.0.0.0", port=self._port).start()
            except BaseException:
                await runner.cleanup()
                raise
            self._runner = runner
            log.info("guest server on port %s", self._port)

    async def stop(self) -> None:
        async with self._lifecycle:
            runner, self._runner = self._runner, None
            for ws in list(self._sockets):
                await ws.close()
            if runner is not None:
                await runner.cleanup()
            if self._http is not None:
                await self._http.close()
                self._http = None

    def notify_changed(self) -> None:
        """Tell every open phone to refresh (queue/now playing changed)."""
        async def send(ws):
            try:
                await ws.send_json({"type": "changed"})
            except Exception:
                pass  # the phone went away
        for ws in list(self._sockets):
            if not ws.closed:
                asyncio.ensure_future(send(ws))

    def _rate(self, request: web.Request, what: str, who: str, burst: int, per: float) -> None:
        if not self._limits.allow((what, who), burst, per):
            raise web.HTTPTooManyRequests(text=json.dumps({"error": "Slow down a little and try again"}),
                                          content_type="application/json")

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
        """Validate, run a guest action, map rule errors to 400 and MA trouble to 503."""
        session = self._check_token(request)
        try:
            return await action(session)
        except NotAdmin as e:
            return self._error(403, str(e))
        except GuestError as e:
            return self._error(400, str(e))
        except web.HTTPException:
            raise
        except Exception as e:
            log.warning("guest request failed: %s", e)
            return self._error(503, NOT_CONNECTED)

    # --- pages ------------------------------------------------------------------------
    async def _root(self, request: web.Request) -> web.Response:
        return web.Response(text="Scan the QR code on the TV to add songs.", content_type="text/plain")

    async def _slash(self, request: web.Request) -> web.Response:
        session = self._check_token(request)
        # the session's own token (equal to the one given), never the request's text
        raise web.HTTPFound(f"{session.token}/")

    async def _page_handler(self, request: web.Request) -> web.Response:
        self._check_token(request)
        return web.Response(text=self._page.read_text(encoding="utf-8"), content_type="text/html",
                            headers={"Cache-Control": "no-store"})

    # --- API --------------------------------------------------------------------------
    async def _join(self, request: web.Request) -> web.Response:
        async def act(session):
            ip = request.remote or "?"
            self._rate(request, "join", ip, burst=10, per=6)
            data = await self._body(request)
            device = data.get("deviceId")
            if self._limit_per_address() and device not in session.guests:
                seen = self._addresses.setdefault((session.token, ip), set())
                # a removed guest on a fresh browser (private tab, cleared data) is still
                # on the same address
                if any(session.is_banned(d) for d in seen):
                    raise web.HTTPForbidden(
                        text=json.dumps({"error": "The host removed you from this party"}),
                        content_type="application/json")
                if device not in seen and len(seen) >= DEVICES_PER_ADDRESS:
                    raise web.HTTPTooManyRequests(
                        text=json.dumps({"error": "Too many guests from this phone"}),
                        content_type="application/json")
            guest = session.join(device, data.get("name"))
            if self._limit_per_address():
                self._addresses.setdefault((session.token, ip), set()).add(guest.device_id)
            self._on_change()
            return web.json_response({"name": guest.name})
        return await self._run(request, act)

    async def _state(self, request: web.Request) -> web.Response:
        async def act(session):
            guest = session.guest(request.query.get("deviceId", ""))
            client, queue_id, _ = self._ctx()
            st = await guest_actions.guest_state(client, queue_id, session, guest)
            st["admin"] = guest.admin
            host = self._admin_host() if guest.admin else None
            if host is not None:
                st["adminInfo"] = admin_actions.admin_info(session, host, guest)
            return web.json_response(st)
        return await self._run(request, act)

    async def _search(self, request: web.Request) -> web.Response:
        async def act(session):
            guest = session.guest(request.query.get("deviceId", ""))
            self._rate(request, "search", guest.device_id, burst=8, per=2)
            client, _, _ = self._ctx()
            try:
                results = await guest_actions.guest_search(client, request.query.get("q", ""), guest=guest)
            except Exception as e:
                log.warning("guest search failed: %s", e)
                raise GuestError("Search didn't work — try again")
            return web.json_response({"results": results})
        return await self._run(request, act)

    async def _add(self, request: web.Request) -> web.Response:
        async def act(session):
            data = await self._body(request)
            guest = session.guest(data.get("deviceId"))
            self._rate(request, "act", guest.device_id, burst=5, per=3)
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
            self._rate(request, "act", guest.device_id, burst=5, per=3)
            item_id = data.get("currentItemId")
            if not isinstance(item_id, str) or len(item_id) > 100:
                raise GuestError("That song already changed — have a look again")
            client, queue_id, player_id = self._ctx()
            await guest_actions.skip(client, queue_id, player_id, session, guest, item_id)
            self._on_change()
            return web.json_response({"ok": True})
        return await self._run(request, act)

    async def _boost(self, request: web.Request) -> web.Response:
        async def act(session):
            data = await self._body(request)
            guest = session.guest(data.get("deviceId"))
            self._rate(request, "act", guest.device_id, burst=5, per=3)
            client, queue_id, _ = self._ctx()
            item_id = data.get("itemId")
            if not isinstance(item_id, str) or len(item_id) > 100:
                raise GuestError("Bad request")
            await guest_actions.boost(client, queue_id, session, guest, item_id)
            self._on_change()
            return web.json_response({"ok": True})
        return await self._run(request, act)

    # --- admin ------------------------------------------------------------------------
    async def _code(self, request: web.Request) -> web.Response:
        async def act(session):
            data = await self._body(request)
            guest = session.guest(data.get("deviceId"))
            self._rate(request, "code", guest.device_id, burst=3, per=10)
            self._rate(request, "code-ip", request.remote or "?", burst=6, per=10)
            code = data.get("code")
            if not isinstance(code, str) or len(code) > 12:
                raise GuestError("That code isn't right")
            try:
                session.redeem_code(guest, code, now=self._clock())
            except GuestError:
                if session.code_cancelled and session.admin_code is None:
                    session.code_cancelled = False  # tell the TV once
                    self._on_admin_event("code_cancelled", "")
                raise
            self._on_admin_event("admin", guest.name)
            self._on_change()
            self.notify_changed()
            return web.json_response({"admin": True})
        return await self._run(request, act)

    @staticmethod
    def _text(data: dict, key: str, limit: int = 100) -> str:
        v = data.get(key)
        if not isinstance(v, str) or not v or len(v) > limit:
            raise GuestError("Bad request")
        return v

    async def _admin(self, request: web.Request, action) -> web.Response:
        """Admin endpoint: joined guest, admin flag checked here and again in the action."""
        async def act(session):
            data = await self._body(request)
            guest = session.guest(data.get("deviceId"))
            if not guest.admin:
                raise NotAdmin("Only an admin can do that")
            self._rate(request, "admin", guest.device_id, burst=10, per=1)
            await action(session, guest, data)
            self._on_change()
            self.notify_changed()
            return web.json_response({"ok": True})
        return await self._run(request, act)

    def _host(self) -> AdminHost:
        host = self._admin_host()
        if host is None:
            raise web.HTTPServiceUnavailable(text=json.dumps({"error": NOT_CONNECTED}),
                                             content_type="application/json")
        return host

    async def _admin_queue(self, request: web.Request) -> web.Response:
        async def act(session, guest, data):
            client, queue_id, _ = self._ctx()
            await admin_actions.admin_queue(client, queue_id, session, guest,
                                            self._text(data, "itemId"), self._text(data, "action", 20))
        return await self._admin(request, act)

    async def _admin_shuffle(self, request: web.Request) -> web.Response:
        async def act(session, guest, data):
            on = data.get("on")
            if not isinstance(on, bool):
                raise GuestError("Bad request")
            await admin_actions.admin_shuffle(self._host(), guest, on)
        return await self._admin(request, act)

    async def _admin_volume(self, request: web.Request) -> web.Response:
        async def act(session, guest, data):
            def number(key):
                v = data.get(key)
                if v is None:
                    return None
                if isinstance(v, bool) or not isinstance(v, (int, float)) or not -1000 <= v <= 1000:
                    raise GuestError("Bad request")
                return int(v)
            level, step = number("level"), number("step")
            if level is None and step is None:
                raise GuestError("Bad request")
            await admin_actions.admin_volume(self._host(), guest, level=level, step=step)
        return await self._admin(request, act)

    async def _admin_speaker(self, request: web.Request) -> web.Response:
        async def act(session, guest, data):
            await admin_actions.admin_speaker(self._host(), guest, self._text(data, "playerId", 200),
                                              self._text(data, "action", 20))
        return await self._admin(request, act)

    async def _admin_guest(self, request: web.Request) -> web.Response:
        async def act(session, guest, data):
            async with session.lock:
                await admin_actions.admin_guest(session, guest, self._text(data, "guestId", 40),
                                                self._text(data, "action", 20))
        return await self._admin(request, act)

    async def _ws(self, request: web.Request) -> web.StreamResponse:
        self._check_token(request)
        if len(self._sockets) >= MAX_SOCKETS:
            return self._error(503, "Too many phones connected — the page will refresh on its own")
        ws = web.WebSocketResponse(heartbeat=30, max_msg_size=1024)
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
        public URL). Allow-list: exactly MA's own `/imageproxy/<id>?size=<n>` on MA's
        scheme, host and port; rebuilt from its parts, no redirects, images only, capped."""
        self._check_token(request)
        from yarl import URL

        ctx = self._context()
        base_s = getattr(getattr(ctx[0], "server_info", None), "base_url", None) if ctx else None
        try:
            u, base = URL(request.query.get("u", "")), URL(base_s or "")
        except (ValueError, TypeError):
            return self._error(400, "Bad request")
        raw_path = u.raw_path
        if (not base_s or u.scheme != base.scheme or u.host != base.host or u.port != base.port
                or u.user or u.password or "%" in raw_path or not _PROXY_ID.match(raw_path)
                or set(u.query) - {"size"} or u.query.get("size", "256") not in IMAGE_SIZES):
            return self._error(400, "Bad request")
        target = base.with_path(raw_path, encoded=True).with_query({"size": u.query.get("size", "256")})
        import aiohttp

        if self._http is None or self._http.closed:
            self._http = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8))
        try:
            async with self._http.get(target, allow_redirects=False) as r:
                ctype = (r.content_type or "").lower()
                if r.status != 200 or not ctype.startswith("image/") or "svg" in ctype:
                    return self._error(502, "Image not available")
                body = await r.content.read(MAX_IMAGE + 1)
                if len(body) > MAX_IMAGE:
                    return self._error(502, "Image too large")
                return web.Response(body=body, content_type=ctype,
                                    headers={"Cache-Control": "max-age=86400",
                                             "X-Content-Type-Options": "nosniff"})
        except Exception:
            return self._error(502, "Image not available")
