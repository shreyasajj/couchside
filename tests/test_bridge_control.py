import json
from unittest.mock import AsyncMock

import pytest

from couchside.core.bridge_control import ControlError, Dispatcher, validate_content


@pytest.mark.parametrize("kind,value", [("track", "library://track/123"),
    ("album", "spotify--abc://album/123"), ("artist", "library://artist/1"),
    ("playlist", "library://playlist/abc"), ("search", "Björk"), ("now_playing", "")])
def test_content_types(kind, value):
    assert validate_content(kind, value) == (kind, value)


@pytest.mark.parametrize("kind,value", [("video", "123"), ("track", "https://example.org"),
    ("track", "library://album/123"), ("track", "library://track/1?command=play"),
    ("search", "x" * 513), ("search", "a\n"), ("now_playing", "some-id"), ("track", None)])
def test_invalid_content(kind, value):
    with pytest.raises(ControlError):
        validate_content(kind, value)


async def test_protocol_ui_only_and_idempotency():
    execute = AsyncMock(return_value={"view": "search"})
    dispatcher = Dispatcher(lambda: {"playback_owner": "music_assistant"}, execute)
    request = dict(id="one", command="navigate", content_type="search", content_id="Björk")
    first = await dispatcher.handle(json.dumps(request))
    assert json.loads(first)["ok"]
    assert await dispatcher.handle(json.dumps(request)) == first
    execute.assert_awaited_once()
    bad = json.loads(await dispatcher.handle(json.dumps({**request, "content_id": "other"})))
    assert bad["error"]["code"] == "invalid_request"
    for cmd in ("play", "pause", "seek", "eval"):
        result = json.loads(await dispatcher.handle(json.dumps(dict(id=cmd, command=cmd))))
        assert result["error"]["code"] == "unsupported"
    execute.assert_awaited_once()


@pytest.mark.parametrize("raw", ["{", "[]", '{}', '{"id":[],"command":"focus"}'])
async def test_invalid_envelopes(raw):
    execute = AsyncMock()
    result = json.loads(await Dispatcher(lambda: {}, execute).handle(raw))
    assert not result["ok"]
    execute.assert_not_awaited()
