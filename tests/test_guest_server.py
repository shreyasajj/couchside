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
    await server.stop()  # closes the image proxy's HTTP session


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
    await env.tc.get(env.base + "api/search", params={"deviceId": DEV, "q": "love"})
    r = await env.tc.post(env.base + "api/add", json={"deviceId": DEV, "uri": "x://t/1"})
    assert r.status == 200
    new = next(i.queue_item_id for i in env.client.player_queues.items if env.session.added_by(i.queue_item_id))
    assert env.session.added_by(new) == "Sam"
    r = await env.tc.post(env.base + "api/boost", json={"deviceId": DEV, "itemId": new})
    assert r.status == 200
    cur = env.client.player_queues.current
    r = await env.tc.post(env.base + "api/skip", json={"deviceId": DEV, "currentItemId": cur})
    assert r.status == 200
    cur = env.client.player_queues.current
    r = await env.tc.post(env.base + "api/skip", json={"deviceId": DEV, "currentItemId": cur})
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
    for bad in ("http://evil.example/x.jpg",
                "http://ma:8095/imageproxy/../info",
                "http://ma:8095/imageproxy/%2e%2e/info",
                "http://ma:8095/imageproxy?path=http://192.168.1.1/&provider=builtin",
                "http://ma:8095.evil.com/imageproxy/abc",
                "http://user@ma:8095/imageproxy/abc",
                "http://ma:8095/imageproxy/abc?size=256&path=x",
                "https://ma:8095/imageproxy/abc"):
        r = await env.tc.get(env.base + "api/img", params={"u": bad})
        assert r.status == 400, bad
    r = await env.tc.get(env.base + "api/img", params={"u": "http://ma:8095/imageproxy/abc123?size=256"})
    assert r.status != 400  # allowed (MA isn't reachable in the test, so 502)


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


# --- review fixes: abuse limits and server lifecycle -------------------------------------

async def test_devices_per_address_capped_on_the_lan(env):
    for n in range(3):
        r = await env.tc.post(env.base + "api/join", json={"deviceId": f"device-{n}-abcdef", "name": f"G{n}"})
        assert r.status == 200
    r = await env.tc.post(env.base + "api/join", json={"deviceId": "device-9-abcdef", "name": "Sneaky"})
    assert r.status == 429


async def test_search_is_rate_limited(env):
    await join(env)
    codes = []
    for _ in range(15):
        r = await env.tc.get(env.base + "api/search", params={"deviceId": DEV, "q": "x"})
        codes.append(r.status)
    assert 429 in codes and codes[0] == 200


async def test_websockets_capped(env, monkeypatch):
    import couchside.core.guest_server as gs
    monkeypatch.setattr(gs, "MAX_SOCKETS", 2)
    socks = [await env.tc.ws_connect(env.base + "api/ws") for _ in range(2)]
    r = await env.tc.get(env.base + "api/ws", headers={"Upgrade": "websocket", "Connection": "Upgrade",
                                                       "Sec-WebSocket-Version": "13", "Sec-WebSocket-Key": "dGhlIHNhbXBsZSBub25jZQ=="})
    assert r.status == 503
    r.release()
    for w in socks:
        await w.close()


def _free_port():
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


async def _listening(port):
    try:
        _, w = await asyncio.open_connection("127.0.0.1", port)
        w.close()
        return True
    except OSError:
        return False


async def test_start_after_a_failed_bind(tmp_path, monkeypatch):
    from aiohttp import web
    page = tmp_path / "p.html"
    page.write_text("x")
    port = _free_port()
    real_start = web.TCPSite.start

    async def busy(self):
        raise OSError(98, "Address already in use")
    monkeypatch.setattr(web.TCPSite, "start", busy)
    server = GuestServer(lambda: None, lambda: None, page_path=page, port=port)
    with pytest.raises(OSError):
        await server.start()
    monkeypatch.setattr(web.TCPSite, "start", real_start)
    await server.start()                       # works once the port is free
    assert await _listening(port)
    await server.stop()


async def test_quick_off_then_on_keeps_the_server_running(tmp_path):
    page = tmp_path / "p.html"
    page.write_text("x")
    port = _free_port()
    server = GuestServer(lambda: None, lambda: None, page_path=page, port=port)
    await server.start()
    stop = asyncio.ensure_future(server.stop())
    start = asyncio.ensure_future(server.start())
    await asyncio.gather(stop, start)
    assert await _listening(port)
    await server.stop()
    assert not await _listening(port)


def test_lan_ip_never_loopback_when_a_lan_route_exists(monkeypatch):
    import couchside.core.guest_server as gs

    class FakeSock:
        def __init__(self, *a):
            self.target = None
        def connect(self, addr):
            self.target = addr[0]
        def getsockname(self):
            return ("127.0.0.1" if self.target in ("127.0.0.1", "localhost") else "10.0.0.5", 0)
        def close(self):
            pass
    monkeypatch.setattr(gs.socket, "socket", FakeSock)
    assert gs.lan_ip("127.0.0.1") == "10.0.0.5"   # MA on this same box
    assert gs.lan_ip("192.168.30.3") == "10.0.0.5"
