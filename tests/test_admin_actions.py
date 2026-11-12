import pytest

from couchside.core import admin_actions as aa
from couchside.core.guest_actions import boost, skip
from couchside.core.guests import GuestError
from tests.test_guest_actions import Q, item, setup


class Host:
    def __init__(self):
        self.calls = []
        self.vol, self.shuf = 40, False
        self.rows = [{"playerId": "tv", "name": "TV", "controlled": True, "available": True, "playing": "Song",
                      "isGroup": False, "members": []},
                     {"playerId": "kitchen", "name": "Kitchen", "controlled": False, "available": True,
                      "playing": "", "isGroup": False, "members": []},
                     {"playerId": "off", "name": "Off", "controlled": False, "available": False,
                      "playing": "", "isGroup": False, "members": []}]

    def host(self):
        async def set_volume(v): self.calls.append(("volume", v))
        async def set_shuffle(on): self.calls.append(("shuffle", on))
        async def transfer(pid): self.calls.append(("transfer", pid)); return True
        return aa.AdminHost(volume=lambda: self.vol, set_volume=set_volume, shuffle=lambda: self.shuf,
                            set_shuffle=set_shuffle, speakers=lambda: self.rows,
                            control=lambda pid: self.calls.append(("control", pid)), transfer=transfer)


def admin_setup(items=None):
    client, s, g = setup(items or [item("cur", "Now"), item("a", "A"), item("b", "B")], skips=0)
    calls = []
    q = client.player_queues
    for m in ("move_up", "move_down", "delete_item", "play_index"):
        async def f(qid, iid, _m=m):
            calls.append((_m, iid))
        setattr(q, m, f)
    other = s.join("device-otherone", "Olly")
    return client, s, g, other, calls


async def test_non_admins_are_refused_everything():
    client, s, g, other, calls = admin_setup()
    h = Host().host()
    with pytest.raises(GuestError, match="admin"):
        await aa.admin_queue(client, Q, s, g, "a", "remove")
    with pytest.raises(GuestError, match="admin"):
        await aa.admin_shuffle(h, g, True)
    with pytest.raises(GuestError, match="admin"):
        await aa.admin_volume(h, g, level=10)
    with pytest.raises(GuestError, match="admin"):
        await aa.admin_speaker(h, g, "kitchen", "control")
    with pytest.raises(GuestError, match="admin"):
        await aa.admin_guest(s, g, other.public_id, "remove")
    assert calls == [] and other.device_id in s.guests


async def test_admin_queue_actions_on_any_song():
    client, s, g, _, calls = admin_setup()
    g.admin = True
    for action in ("up", "down", "remove", "next", "play"):
        await aa.admin_queue(client, Q, s, g, "b", action)
    assert [c[0] for c in calls] == ["move_up", "move_down", "delete_item", "play_index"]
    assert ("move_next", "b") in client.player_queues.calls


async def test_admin_queue_refuses_unknown_items_and_actions():
    client, s, g, _, calls = admin_setup()
    g.admin = True
    with pytest.raises(GuestError):
        await aa.admin_queue(client, Q, s, g, "gone", "remove")
    with pytest.raises(GuestError):
        await aa.admin_queue(client, Q, s, g, "a", "explode")
    assert calls == []


async def test_admin_volume_shuffle_speakers():
    host = Host()
    h = host.host()
    _, s, g, _, _ = admin_setup()
    g.admin = True
    await aa.admin_volume(h, g, level=150)
    await aa.admin_volume(h, g, step=-5)
    await aa.admin_shuffle(h, g, True)
    await aa.admin_speaker(h, g, "kitchen", "control")
    await aa.admin_speaker(h, g, "kitchen", "transfer")
    assert host.calls == [("volume", 100), ("volume", 35), ("shuffle", True),
                          ("control", "kitchen"), ("transfer", "kitchen")]
    for pid, action in (("off", "control"), ("nope", "control"), ("kitchen", "delete")):
        with pytest.raises(GuestError):
            await aa.admin_speaker(h, g, pid, action)


async def test_admin_resets_and_removes_guests_but_not_admins():
    _, s, g, other, _ = admin_setup()
    g.admin = True
    other.skips_used = 2
    await aa.admin_guest(s, g, other.public_id, "reset")
    assert other.skips_used == 0
    other.admin = True
    with pytest.raises(GuestError, match="host"):
        await aa.admin_guest(s, g, other.public_id, "remove")
    with pytest.raises(GuestError, match="host"):
        await aa.admin_guest(s, g, g.public_id, "remove")
    other.admin = False
    await aa.admin_guest(s, g, other.public_id, "remove")
    assert other.device_id not in s.guests


async def test_admin_info_lists_guests_without_device_ids():
    host = Host()
    _, s, g, other, _ = admin_setup()
    g.admin = True
    info = aa.admin_info(s, host.host(), g)
    assert info["volume"] == 40 and info["shuffle"] is False
    assert [(x["name"], x["admin"], x["you"]) for x in info["guests"]] == [("Sam", True, True), ("Olly", False, False)]
    assert all(set(x) == {"id", "name", "admin", "you", "skipsLeft", "boostsLeft"} for x in info["guests"])
    assert "device" not in repr(info)
    assert [(x["playerId"], x["available"]) for x in info["speakers"]] == [("tv", True), ("kitchen", True), ("off", False)]


async def test_admin_skips_are_unlimited_and_failures_dont_go_negative():
    client, s, g, _, _ = admin_setup()
    g.admin = True
    await skip(client, Q, "tv", s, g, "cur")
    client.players.fail = True
    with pytest.raises(GuestError):
        await skip(client, Q, "tv", s, g, client.player_queues.current)
    assert g.skips_used == 0
    s.note_added(g, "b", now=0)
    client.player_queues.fail.add("move")
    with pytest.raises(GuestError):
        await boost(client, Q, s, g, "b")
    assert g.boosts_used == 0
