from types import SimpleNamespace as NS

import pytest
from aiohttp.test_utils import TestClient, TestServer

from couchside.core.guest_server import GuestServer
from couchside.core.guests import GuestRules, GuestSession
from tests.test_admin_actions import Host
from tests.test_guest_actions import FakeMusic, FakePlayers, FakeQueues, item

DEV, OTHER = "device-abcdef12", "device-other123"
ADMIN_ROUTES = [("queue", {"itemId": "next", "action": "remove"}), ("shuffle", {"on": True}),
                ("volume", {"level": 10}), ("speaker", {"playerId": "kitchen", "action": "control"}),
                ("guest", {"guestId": "x", "action": "reset"})]


@pytest.fixture
async def env(tmp_path):
    page = tmp_path / "guest.html"
    page.write_text("<html>guest page</html>")
    session = GuestSession(GuestRules(skips=0))
    queues = FakeQueues([item("cur", "Now"), item("next", "Next"), item("later", "Later")])
    calls = []
    for m in ("move_up", "move_down", "delete_item", "play_index"):
        async def f(qid, iid, _m=m):
            calls.append((_m, iid))
        setattr(queues, m, f)
    client = NS(player_queues=queues, players=FakePlayers(queues), music=FakeMusic(),
                server_info=NS(base_url="http://ma:8095"))
    host = Host()
    events = []
    server = GuestServer(lambda: session, lambda: (client, "tvqueue", "tv"), page_path=page,
                         clock=lambda: 1000.0, get_admin_host=host.host,
                         on_admin_event=lambda kind, name: events.append((kind, name)))
    tc = TestClient(TestServer(server.app))
    await tc.start_server()
    base = f"/g/{session.token}/"
    for dev, name in ((DEV, "Sam"), (OTHER, "Olly")):
        r = await tc.post(base + "api/join", json={"deviceId": dev, "name": name})
        assert r.status == 200
    yield NS(tc=tc, session=session, client=client, host=host, calls=calls, base=base, events=events)
    await tc.close()
    await server.stop()


async def post(env, path, dev=DEV, **body):
    r = await env.tc.post(env.base + "api/" + path, json={"deviceId": dev, **body})
    return r.status, await r.json()


async def state(env, dev=DEV):
    r = await env.tc.get(env.base + "api/state", params={"deviceId": dev})
    return await r.json()


async def test_every_admin_route_refuses_guests(env):
    for route, body in ADMIN_ROUTES:
        status, data = await post(env, "admin/" + route, **body)
        assert status == 403, route
        assert "admin" in data["error"]
    assert env.calls == [] and env.host.calls == []
    st = await state(env)
    assert st["admin"] is False and "adminInfo" not in st


async def test_code_makes_an_admin_once(env):
    code = env.session.new_admin_code(now=1000.0)
    status, data = await post(env, "code", code=code)
    assert status == 200 and data["admin"] is True
    assert env.events == [("admin", "Sam")]
    status, _ = await post(env, "code", dev=OTHER, code=code)
    assert status == 400
    st = await state(env)
    assert st["admin"] is True and [g["name"] for g in st["adminInfo"]["guests"]] == ["Sam", "Olly"]
    assert DEV not in repr(st) and OTHER not in repr(st)


async def test_wrong_codes_cancel_and_tell_the_tv(env):
    code = env.session.new_admin_code(now=1000.0)
    wrong = "000000" if code != "000000" else "111111"
    for dev in (DEV, OTHER, DEV, OTHER, DEV):
        await post(env, "code", dev=dev, code=wrong)
    assert env.session.admin_code is None
    assert ("code_cancelled", "") in env.events


async def test_code_tries_are_rate_limited(env):
    env.session.new_admin_code(now=1000.0)
    codes = [(await post(env, "code", code="12345x"))[0] for _ in range(6)]
    assert 429 in codes


async def test_admin_routes_work_for_admins(env):
    env.session.guests[DEV].admin = True
    other = env.session.guests[OTHER]
    assert (await post(env, "admin/queue", itemId="later", action="up"))[0] == 200
    assert (await post(env, "admin/shuffle", on=True))[0] == 200
    assert (await post(env, "admin/volume", step=5))[0] == 200
    assert (await post(env, "admin/speaker", playerId="kitchen", action="transfer"))[0] == 200
    assert (await post(env, "admin/guest", guestId=other.public_id, action="remove"))[0] == 200
    assert env.calls == [("move_up", "later")]
    assert env.host.calls == [("shuffle", True), ("volume", 45), ("transfer", "kitchen")]
    assert OTHER not in env.session.guests
    status, data = await post(env, "join", dev=OTHER, name="Olly again")
    assert status == 400 and "removed" in data["error"]


async def test_admin_inputs_are_checked(env):
    env.session.guests[DEV].admin = True
    for route, body in [("queue", {"itemId": 5, "action": "up"}), ("queue", {"itemId": "x" * 200, "action": "up"}),
                        ("volume", {"level": "loud"}), ("volume", {}), ("volume", {"level": True}),
                        ("speaker", {"playerId": None, "action": "control"}),
                        ("guest", {"guestId": ["x"], "action": "reset"}), ("shuffle", {"on": "yes"})]:
        status, _ = await post(env, "admin/" + route, **body)
        assert status == 400, (route, body)


async def test_admin_skips_are_unlimited(env):
    env.session.guests[DEV].admin = True
    for _ in range(2):
        cur = env.client.player_queues.current
        status, _ = await post(env, "skip", currentItemId=cur)
        assert status == 200


async def test_revoked_admin_is_refused_at_once(env):
    g = env.session.guests[DEV]
    g.admin = True
    env.session.revoke(g.public_id)
    status, _ = await post(env, "admin/shuffle", on=False)
    assert status == 403
    assert (await state(env))["admin"] is False
