"""Strict, UI-only control protocol. Playback remains owned by Music Assistant."""
from collections import OrderedDict
import json
import re

BUS_NAME = "io.github.shreyasajj.Couchside.Control"
OBJECT_PATH = "/io/github/shreyasajj/Couchside/Control"
CONTENT_TYPES = ("now_playing", "search", "track", "album", "artist", "playlist")


class ControlError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def validate_content(kind, value):
    if kind not in CONTENT_TYPES:
        raise ControlError("unsupported", "Unsupported Couchside content type")
    if not isinstance(value, str) or len(value) > 2048 or any(ord(c) < 32 for c in value):
        raise ControlError("invalid_request", "Invalid content ID")
    if kind == "now_playing":
        if value not in ("", "now_playing"):
            raise ControlError("invalid_request", "Now Playing does not accept an item ID")
    elif kind == "search":
        if len(value) > 512:
            raise ControlError("invalid_request", "Search is limited to 512 characters")
    elif not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}://" + kind + r"/[^\s?#]{1,1536}", value):
        raise ControlError("invalid_request", "Use a Music Assistant URI matching the content type")
    return kind, value


class Dispatcher:
    def __init__(self, snapshot, execute):
        self.snapshot = snapshot
        self.execute = execute
        self.cache = OrderedDict()

    async def handle(self, payload):
        request_id = None
        request = None
        try:
            if len(payload.encode()) > 16384:
                raise ControlError("invalid_request", "Request too large")
            request = json.loads(payload)
            if not isinstance(request, dict):
                raise ControlError("invalid_request", "Expected an object")
            request_id = request.get("id")
            if not isinstance(request_id, str) or not 1 <= len(request_id) <= 128:
                request_id = None
                raise ControlError("invalid_request", "Request ID required")
            if request_id in self.cache:
                original, response = self.cache[request_id]
                if original != request:
                    raise ControlError("invalid_request", "Request ID reused with different content")
                return response
            command = request.get("command")
            allowed = {"id", "command"}
            if command == "navigate":
                allowed |= {"content_type", "content_id"}
                validate_content(request.get("content_type"), request.get("content_id"))
            elif command not in ("get_state", "focus"):
                raise ControlError("unsupported", "Only UI commands are supported")
            if request.keys() - allowed:
                raise ControlError("invalid_request", "Unknown fields")
            result = self.snapshot() if command == "get_state" else await self.execute(request)
            response = json.dumps({"id": request_id, "ok": True, "result": result})
        except (ValueError, ControlError) as exc:
            response = json.dumps({"id": request_id, "ok": False,
                                   "error": {"code": getattr(exc, "code", "invalid_request"),
                                             "message": str(exc)}})
        if request_id and request_id not in self.cache:
            self.cache[request_id] = (request, response)
            if len(self.cache) > 128:
                self.cache.popitem(last=False)
        return response
