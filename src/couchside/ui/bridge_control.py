"""Single-instance session-bus endpoint and QML navigation acknowledgements."""
import asyncio
import json
import logging
import uuid

from dbus_next.aio import MessageBus
from dbus_next import Message, MessageType
from dbus_next.constants import NameFlag, RequestNameReply
from dbus_next.service import ServiceInterface, method
from PySide6.QtCore import QObject, Signal, Slot

from couchside.core import library
from couchside.core.bridge_control import BUS_NAME, OBJECT_PATH, CONTENT_TYPES, ControlError, Dispatcher
from couchside.core.connection import ConnState
from couchside.core.playback import find_local_player

LOG = logging.getLogger(__name__)


class Endpoint(ServiceInterface):
    def __init__(self, control):
        super().__init__(BUS_NAME)
        self.control = control

    @method()
    async def Execute(self, payload: 's') -> 's':
        # Serial dispatch also guarantees idempotency for simultaneous retries.
        async with self.control.lock:
            try:
                return await self.control.dispatcher.handle(payload)
            except Exception:
                LOG.exception("Couchside UI command failed")
                try:
                    value = json.loads(payload)
                    request_id = value.get("id") if isinstance(value, dict) else None
                except ValueError:
                    request_id = None
                return json.dumps({"id": request_id, "ok": False,
                                   "error": {"code": "internal_error", "message": "UI operation failed"}})


class UiControl(QObject):
    navigationRequested = Signal(str, str, str)

    def __init__(self):
        super().__init__()
        self.bus = None
        self.controller = None
        self.ready = asyncio.Event()
        self.pending = {}
        self.lock = asyncio.Lock()
        self.view = {"type": "now_playing", "id": ""}
        self.dispatcher = Dispatcher(self.snapshot, self.execute)

    async def acquire(self):
        self.bus = await MessageBus().connect()
        reply = await self.bus.request_name(BUS_NAME, NameFlag.DO_NOT_QUEUE)
        if reply == RequestNameReply.PRIMARY_OWNER:
            self.bus.export(OBJECT_PATH, Endpoint(self))
            return True
        # Only the primary creates a controller, QML window or Sendspin helper.
        request = {"id": str(uuid.uuid4()), "command": "focus"}
        reply = await self.bus.call(Message(destination=BUS_NAME, path=OBJECT_PATH,
                                            interface=BUS_NAME, member="Execute", signature="s",
                                            body=[json.dumps(request)]))
        if reply.message_type == MessageType.ERROR or not json.loads(reply.body[0]).get("ok"):
            raise RuntimeError("The existing Couchside UI is not ready")
        return False

    def attach(self, controller):
        self.controller = controller
        self.ready.set()

    def snapshot(self):
        c = self.controller
        client = c.conn.client if c else None
        identity = c._get_client_id() if client and c else None
        local = find_local_player(list(client.players), identity) if client and identity else None
        return {"protocol": 1, "ready": self.ready.is_set(),
                "music_assistant_ready": bool(c and c.conn.state is ConnState.CONNECTED),
                "content_types": list(CONTENT_TYPES),
                "playback_owner": "music_assistant", "ma_player_id": local.player_id if local else None,
                "view": self.view}

    async def execute(self, request):
        try:
            await asyncio.wait_for(self.ready.wait(), 10)
        except TimeoutError as exc:
            raise ControlError("not_ready", "The Couchside UI is not ready") from exc
        kind = request.get("content_type", "focus")
        value = request.get("content_id", "")
        payload = {}
        c = self.controller
        # Resolve content before navigation. These calls never start playback.
        if kind not in ("focus", "now_playing"):
            if c.conn.state is not ConnState.CONNECTED or c.conn.client is None:
                raise ControlError("not_ready", "Music Assistant is not connected")
            if kind == "search":
                c._search_gen += 1
                generation = c._search_gen
                try:
                    outcome = await asyncio.wait_for(library.search(c.conn.client, value), 15)
                except TimeoutError as exc:
                    raise ControlError("search_failed", "Music Assistant search timed out") from exc
                if outcome.error:
                    raise ControlError("search_failed", "Music Assistant search failed")
                if generation != c._search_gen:
                    raise ControlError("superseded", "A newer UI search replaced this request")
                c._set_library(outcome.rows)
            else:
                try:
                    item = await asyncio.wait_for(c.conn.client.music.get_item_by_uri(value), 15)
                except Exception as exc:
                    raise ControlError("content_not_found", "Music Assistant could not resolve this item") from exc
                card = library.to_card(c.conn.client, item)
                if card is None or card.kind != kind:
                    raise ControlError("content_not_found", "Resolved item does not match the requested type")
                from couchside.ui.controller import _card
                payload = _card(card)
        request_id = request["id"]
        future = asyncio.get_running_loop().create_future()
        self.pending[request_id] = future
        try:
            self.navigationRequested.emit(request_id, kind, json.dumps({"value": value, "item": payload}))
            if not await asyncio.wait_for(future, 5):
                raise ControlError("navigation_failed", "QML could not open the requested view")
            if kind != "focus":
                self.view = {"type": kind, "id": value}
            return self.snapshot()
        except TimeoutError as exc:
            raise ControlError("navigation_failed", "QML did not acknowledge navigation") from exc
        finally:
            self.pending.pop(request_id, None)

    @Slot(str, bool)
    def completeNavigation(self, request_id, success):
        future = self.pending.get(request_id)
        if future and not future.done():
            future.set_result(success)

    def close(self):
        if self.bus:
            self.bus.disconnect()
