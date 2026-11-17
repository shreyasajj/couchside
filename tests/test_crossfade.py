"""Crossfade settings kept by Music Assistant: on/off and style per queue, the standard
crossfade's length for the whole server (Qt-free)."""

import pytest

from couchside.core import crossfade
from couchside.core.crossfade import Crossfade


class FakeClient:
    def __init__(self, enabled=True, mode="global", server_mode="smart_crossfade", seconds=8, fail=False):
        self.values = {"enabled": enabled, "mode": mode, "server_mode": server_mode, "seconds": seconds}
        self.sent = []
        self.fail = fail
        self.player_queues = self
        self._queues = {"q": type("Q", (), {"crossfade_enabled": enabled})()}

    def get(self, queue_id):
        return self._queues.get(queue_id)

    async def send_command(self, command, **args):
        if self.fail:
            raise RuntimeError("no")
        self.sent.append((command, args))
        if command == "config/player_queues/get_value":
            return self.values["mode"]
        if command == "config/core/get_value":
            return {"crossfade_duration": self.values["seconds"],
                    "crossfade_mode": self.values["server_mode"]}[args["key"]]
        return None


async def test_load_reads_the_queue_and_the_server():
    got = await crossfade.load(FakeClient(enabled=True, mode="global", seconds=6), "q")
    assert got == Crossfade(enabled=True, mode="global", server_mode="smart_crossfade", seconds=6)
    assert got.effective_mode == "smart_crossfade"          # "global" follows the server
    assert got.length_applies is False                      # smart crossfade picks its own length


async def test_standard_mode_uses_the_length():
    got = await crossfade.load(FakeClient(mode="standard_crossfade", seconds=4), "q")
    assert got.effective_mode == "standard_crossfade" and got.length_applies is True


async def test_load_without_a_queue_or_server_gives_none():
    assert await crossfade.load(None, "q") is None
    assert await crossfade.load(FakeClient(), None) is None
    assert await crossfade.load(FakeClient(fail=True), "q") is None


async def test_switching_on_and_off_is_per_queue():
    client = FakeClient()
    assert await crossfade.set_enabled(client, "q", False) is True
    assert client.sent == [("player_queues/crossfade", {"queue_id": "q", "crossfade_enabled": False})]


async def test_style_is_saved_on_the_queue():
    client = FakeClient()
    assert await crossfade.set_mode(client, "q", "standard_crossfade") is True
    assert client.sent == [("config/player_queues/save",
                            {"queue_id": "q", "values": {"crossfade_mode": "standard_crossfade"}})]
    assert await crossfade.set_mode(client, "q", "bogus") is False   # only the known styles


@pytest.mark.parametrize("asked, saved", [(5, 5), (0, 1), (99, 15), (15, 15)])
async def test_length_is_kept_between_1_and_15_seconds(asked, saved):
    client = FakeClient()
    assert await crossfade.set_seconds(client, asked) is True
    assert client.sent == [("config/core/save",
                            {"domain": "player_queues", "values": {"crossfade_duration": saved}})]


async def test_failures_report_false():
    client = FakeClient(fail=True)
    assert await crossfade.set_enabled(client, "q", True) is False
    assert await crossfade.set_mode(client, "q", "smart_crossfade") is False
    assert await crossfade.set_seconds(client, 5) is False
    assert await crossfade.set_enabled(None, "q", True) is False
