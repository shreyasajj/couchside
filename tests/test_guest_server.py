import asyncio
from types import SimpleNamespace as NS

import pytest
from aiohttp.test_utils import TestClient, TestServer

from couchside.core.guest_server import GuestServer
from couchside.core.guests import GuestRules, GuestSession
from tests.test_guest_actions import FakeMusic, FakePlayers, FakeQueues, item

DEV = "device-abcdef12"


@pytest.fixture
async def env(tmp_path):
    page = tmp_path / "guest.html"
    page.write_text("<html>guest page</html>")
    session = GuestSession(GuestRules(skips=1))
    client = NS(player_queues=FakeQueues([item("cur", "Now"), item("next", "Next")]),
                players=FakePlayers(), music=FakeMusic(), server_info=NS(base_url="http://ma:8095"))
    state = {"client": client}
    server = GuestServer(lambda: session,
                         lambda: (state["client"], "tvqueue", "tv") if state["client"] else None,
                         page_path=page, clock=lambda: 1000.0)
    tc = TestClient(TestServer(server.app))
    await tc.start_server()
    yield NS(tc=tc, session=session, client=client, server=server, state=state,
             base=f"/g/{session.token}/")
    await tc.close()


async def join(env, name="Sam"):
    r = await env.tc.post(env.base + "api/join", json={"deviceId": DEV, "name": name})
    return r.status, await r.json()


async def test_page_served_only_with_the_token(env):
    r = await env.tc.get(env.base)
    assert r.status == 200 and "guest page" in await r.text()
    assert (await env.tc.get("/g/wrong-token-1234/")).status == 403
    r = await env.tc.get(f"/g/{env.session.token}", allow_redirects=False)
    assert r.status in (301, 302, 307, 308) and r.headers["Location"].endswith("/")


async def test_api_rejects_wrong_token(env):
    r = await env.tc.post("/g/nope-nope-nope-1/api/join", json={"deviceId": DEV, "name": "Sam"})
    assert r.status == 403


async def test_join_then_state(env):
    status, body = await join(env)
    assert status == 200 and body["name"] == "Sam"
    r = await env.tc.get(env.base + "api/state", params={"deviceId": DEV})
    st = await r.json()
    assert r.status == 200 and st["nowPlaying"]["title"] == "Now" and st["remaining"]["skips"] == 1


async def test_bad_join_is_400_with_message(env):
    r = await env.tc.post(env.base + "api/join", json={"deviceId": DEV, "name": ""})
    assert r.status == 400 and "name" in (await r.json())["error"]
    r = await env.tc.post(env.base + "api/join", data="not json")
    assert r.status == 400


async def test_actions_need_a_joined_guest(env):
    r = await env.tc.post(env.base + "api/skip", json={"deviceId": DEV})
    assert r.status == 400 and "name" in (await r.json())["error"]


async def test_add_skip_boost(env):
    await join(env)
    r = await env.tc.post(env.base + "api/add", json={"deviceId": DEV, "uri": "x://t/9"})
    assert r.status == 200
    new = next(i.queue_item_id for i in env.client.player_queues.items if env.session.added_by(i.queue_item_id))
    assert env.session.added_by(new) == "Sam"
    r = await env.tc.post(env.base + "api/boost", json={"deviceId": DEV, "itemId": new})
    assert r.status == 200
    r = await env.tc.post(env.base + "api/skip", json={"deviceId": DEV})
    assert r.status == 200
    r = await env.tc.post(env.base + "api/skip", json={"deviceId": DEV})
    assert r.status == 400 and "No skips left" in (await r.json())["error"]


async def test_search_and_query_cap(env):
    await join(env)
    r = await env.tc.get(env.base + "api/search", params={"deviceId": DEV, "q": "love"})
    assert r.status == 200 and (await r.json())["results"][0]["uri"] == "x://t/1"


async def test_not_connected_is_503(env):
    await join(env)
    env.state["client"] = None
    r = await env.tc.get(env.base + "api/state", params={"deviceId": DEV})
    assert r.status == 503


async def test_body_size_capped(env):
    r = await env.tc.post(env.base + "api/join", data=b"x" * 100_000,
                          headers={"Content-Type": "application/json"})
    assert r.status in (400, 413)


async def test_image_proxy_only_for_ma_images(env, monkeypatch):
    r = await env.tc.get(env.base + "api/img", params={"u": "http://evil.example/x.jpg"})
    assert r.status == 400


async def test_websocket_gets_change_pings(env):
    await join(env)
    ws = await env.tc.ws_connect(env.base + "api/ws", params={"deviceId": DEV})
    await asyncio.sleep(0.05)
    env.server.notify_changed()
    msg = await asyncio.wait_for(ws.receive_json(), 2)
    assert msg == {"type": "changed"}
    await ws.close()


async def test_new_token_locks_out_old_links(env):
    await join(env)
    old = env.base
    env.session.new_token()
    assert (await env.tc.get(old)).status == 403
