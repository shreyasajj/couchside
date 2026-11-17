from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest

from couchside.core import library
from couchside.core.bridge_control import ControlError
from couchside.core.connection import ConnState
from couchside.core.settings import AppSettings


@pytest.fixture
async def ui(qt_app, tmp_path, monkeypatch):
    from couchside.ui.controller import AppController
    from couchside.ui.bridge_control import UiControl
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    controller = AppController(AppSettings())
    controller.conn.client = NS(players=[], music=NS())
    controller.conn.state = ConnState.CONNECTED
    control = UiControl()
    control.attach(controller)
    # Acknowledge the QML boundary; real QML navigation is tested on the TV.
    control.navigationRequested.connect(lambda request_id, *_: control.completeNavigation(request_id, True))
    yield control, controller
    await controller.close()


async def test_search_uses_controller_domain_rows(ui, monkeypatch):
    control, controller = ui
    card = library.MediaCard("library://track/1", "track", "Song", "Artist", None, "library://track/1")
    monkeypatch.setattr(library, "search", AsyncMock(return_value=library.SearchOutcome([("Tracks", [card])])))
    result = await control.execute(dict(id="search", command="navigate", content_type="search", content_id="Song"))
    assert controller.libraryRows[0]["items"][0]["title"] == "Song"
    assert result["view"] == {"type": "search", "id": "Song"}
    focused = await control.execute(dict(id="focus", command="focus"))
    assert focused["view"] == result["view"]


async def test_item_resolution_is_ui_only(ui):
    control, controller = ui
    controller.conn.client.music.get_item_by_uri = AsyncMock(return_value=NS(
        uri="library://album/1", media_type="album", name="Album", artist_str="Artist", image=None))
    result = await control.execute(dict(id="item", command="navigate", content_type="album",
                                        content_id="library://album/1"))
    assert result["view"] == {"type": "album", "id": "library://album/1"}
    assert not hasattr(controller.conn.client, "player_queues")  # No playback calls required.


async def test_disconnected_search_does_not_navigate(ui):
    control, controller = ui
    controller.conn.state = ConnState.RECONNECTING
    with pytest.raises(ControlError, match="not connected"):
        await control.execute(dict(id="search", command="navigate", content_type="search", content_id="Song"))
    assert control.view == {"type": "now_playing", "id": ""}


async def test_missing_sendspin_identity_never_matches_another_player(ui, monkeypatch):
    control, controller = ui
    monkeypatch.setattr(controller, "_get_client_id", lambda: None)
    controller.conn.client.players = [NS(player_id="another-speaker", output_protocols=[NS()])]
    assert control.snapshot()["ma_player_id"] is None


async def test_state_changes_are_announced_once(ui):
    control, controller = ui
    emitted = []
    control.endpoint = NS(StateChanged=lambda: emitted.append(True))
    controller.conn.client.music.get_item_by_uri = AsyncMock(return_value=NS(
        uri="library://album/1", media_type="album", name="Album", artist_str="Artist", image=None))
    await control.execute(dict(id="item", command="navigate", content_type="album", content_id="library://album/1"))
    assert len(emitted) == 1
    controller.changed.emit()  # unrelated UI churn leaves the published state alone
    await control.execute(dict(id="focus", command="focus"))
    assert len(emitted) == 1
    controller.conn.state = ConnState.RECONNECTING
    controller.changed.emit()
    assert len(emitted) == 2


async def test_browse_lists_library_without_navigating(ui):
    control, controller = ui
    root = await control.execute(dict(id="root", command="browse"))
    assert [row["path"] for row in root["items"]] == ["playlist", "album", "artist", "track"]
    rows = [NS(uri=f"library://album/{n}", media_type="album", name=f"Album {n}", artist_str="Artist", image=None)
            for n in range(3)] + [NS(uri="not a uri", media_type="album", name="Broken", artist_str="", image=None)]
    controller.conn.client.music.get_library_albums = AsyncMock(return_value=rows[:3])
    page = await control.execute(dict(id="page", command="browse", path="album", offset=4, limit=2))
    controller.conn.client.music.get_library_albums.assert_awaited_once_with(limit=3, offset=4)
    assert [row["id"] for row in page["items"]] == ["library://album/0", "library://album/1"]
    assert page["next_offset"] == 6 and page["items"][0]["content_type"] == "album"
    controller.conn.client.music.get_library_albums = AsyncMock(return_value=rows[3:])
    assert (await control.execute(dict(id="bad", command="browse", path="album")))["items"] == []
    assert control.view == {"type": "now_playing", "id": ""}
    controller.conn.state = ConnState.RECONNECTING
    with pytest.raises(ControlError, match="not connected"):
        await control.execute(dict(id="down", command="browse", path="album"))


async def test_browse_requests_are_validated_by_the_dispatcher(ui):
    import json
    control, _ = ui
    for extra in (dict(path="radio"), dict(limit=51), dict(offset=-1), dict(content_id="x")):
        reply = json.loads(await control.dispatcher.handle(json.dumps(dict(id=str(extra), command="browse", **extra))))
        assert reply["error"]["code"] == "invalid_request"
    reply = json.loads(await control.dispatcher.handle(json.dumps(dict(id="ok", command="browse"))))
    assert reply["ok"] and len(reply["result"]["items"]) == 4
