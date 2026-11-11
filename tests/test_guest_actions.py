from types import SimpleNamespace as NS

import pytest

from couchside.core.guest_actions import add_track, boost, guest_search, guest_state, skip
from couchside.core.guests import GuestError, GuestRules, GuestSession

Q = "tvqueue"


def item(iid, title, uri=None):
    return NS(queue_item_id=iid, name=f"Artist - {title}", duration=200, image=None,
              media_item=NS(name=title, artist_str="Artist", uri=uri or f"x://{iid}", image=None))


class FakeQueues:
    def __init__(self, items, current="cur"):
        self.items, self.current, self.calls = list(items), current, []
        self.fail = set()

    def get(self, qid):
        cur = next((i for i in self.items if i.queue_item_id == self.current), None)
        return NS(queue_id=qid, current_item=cur)

    async def get_queue_items(self, qid, limit=500, offset=0):
        return list(self.items)

    async def play_media(self, qid, media, option=None):
        self.calls.append(("play_media", media, str(getattr(option, "value", option))))
        if "add" in self.fail:
            raise RuntimeError("nope")
        self.items.append(item(f"new{len(self.items)}", "Added", uri=media))

    async def move_next(self, qid, iid):
        self.calls.append(("move_next", iid))
        if "move" in self.fail:
            raise RuntimeError("nope")


class FakePlayers:
    def __init__(self):
        self.calls, self.fail = [], False

    async def next_track(self, pid):
        self.calls.append(("next", pid))
        if self.fail:
            raise RuntimeError("nope")


class FakeMusic:
    def __init__(self):
        self.calls = []

    def get_media_item_image(self, item, *_):
        return None

    async def search(self, q, media_types=None, limit=20):
        self.calls.append((q, [str(getattr(m, "value", m)) for m in media_types], limit))
        return NS(tracks=[NS(name="Song", uri="x://t/1", media_type=NS(value="track"),
                             artist_str="Band", album=None, image=None)])


def setup(items=None, **rules):
    queues = FakeQueues(items if items is not None else [item("cur", "Now")])
    client = NS(player_queues=queues, players=FakePlayers(), music=FakeMusic(),
                server_info=NS(base_url="http://ma:8095"))
    s = GuestSession(GuestRules(**rules))
    g = s.join("device-abcdef12", "Sam")
    return client, s, g


async def test_add_track_credits_the_new_item():
    client, s, g = setup()
    await add_track(client, Q, "tv", s, g, "x://t/9", now=1)
    new = client.player_queues.items[-1].queue_item_id
    assert s.added_by(new) == "Sam"
    assert client.player_queues.calls == [("play_media", "x://t/9", "add")]


async def test_add_respects_waiting_limit():
    client, s, g = setup(max_waiting=1)
    await add_track(client, Q, "tv", s, g, "x://t/1", now=1)
    with pytest.raises(GuestError, match="1 songs waiting"):
        await add_track(client, Q, "tv", s, g, "x://t/2", now=2)


async def test_add_failure_is_a_guest_error():
    client, s, g = setup()
    client.player_queues.fail.add("add")
    with pytest.raises(GuestError, match="Couldn't add"):
        await add_track(client, Q, "tv", s, g, "x://t/1", now=1)
    assert g.last_add is None  # no cooldown for a failed add


async def test_only_track_uris_accepted():
    client, s, g = setup()
    for bad in ("x://album/1", "x://playlist/2", "", "x" * 600):
        with pytest.raises(GuestError):
            await add_track(client, Q, "tv", s, g, bad, now=1)


async def test_skip_uses_a_skip_and_refunds_on_failure():
    client, s, g = setup(skips=2)
    await skip(client, "tv", s, g)
    assert client.players.calls == [("next", "tv")] and g.skips_used == 1
    client.players.fail = True
    with pytest.raises(GuestError):
        await skip(client, "tv", s, g)
    assert g.skips_used == 1


async def test_boost_moves_own_song_next():
    client, s, g = setup([item("cur", "Now"), item("a", "A"), item("mine", "Mine")])
    s.note_added(g, "mine", now=0)
    await boost(client, Q, s, g, "mine")
    assert client.player_queues.calls == [("move_next", "mine")] and g.boosts_used == 1


async def test_boost_refunded_on_failure():
    client, s, g = setup([item("cur", "Now"), item("mine", "Mine")])
    s.note_added(g, "mine", now=0)
    client.player_queues.fail.add("move")
    with pytest.raises(GuestError):
        await boost(client, Q, s, g, "mine")
    assert g.boosts_used == 0


async def test_guest_state():
    client, s, g = setup([item("old", "Old"), item("cur", "Now"), item("mine", "Mine"), item("x", "Other")])
    s.note_added(g, "mine", now=0)
    st = await guest_state(client, Q, s, g)
    assert st["name"] == "Sam"
    assert st["nowPlaying"]["title"] == "Now"
    assert [(u["itemId"], u["mine"], u["addedBy"]) for u in st["upcoming"]] == [
        ("mine", True, "Sam"), ("x", False, "")]
    assert st["remaining"] == {"skips": 3, "boosts": 2, "waiting": 1, "maxWaiting": 3}


async def test_guest_search_is_tracks_only():
    client, s, g = setup()
    results = await guest_search(client, "love")
    assert client.music.calls == [("love", ["track"], 20)]
    assert results == [{"uri": "x://t/1", "title": "Song", "subtitle": "Band", "imageUrl": ""}]
    assert await guest_search(client, "  ") == []
