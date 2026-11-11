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

    current_index = None

    def get(self, qid):
        cur = next((i for i in self.items if i.queue_item_id == self.current), None)
        idx = self.current_index
        if idx is None and cur is not None:
            idx = self.items.index(cur)
        return NS(queue_id=qid, current_item=cur, current_index=idx)

    async def get_queue_items(self, qid, limit=500, offset=0):
        return list(self.items[offset:offset + limit])

    async def play_media(self, qid, media, option=None):
        opt = str(getattr(option, "value", option))
        self.calls.append(("play_media", media, opt))
        if "add" in self.fail:
            raise RuntimeError("nope")
        new = item(f"new{len(self.items)}", "Added", uri=media)
        if opt == "next":
            ids = [i.queue_item_id for i in self.items]
            self.items.insert(ids.index(self.current) + 1 if self.current in ids else 0, new)
        else:
            self.items.append(new)

    async def move_item(self, qid, iid, pos_shift=1):
        self.calls.append(("move_item", iid, pos_shift))
        ids = [i.queue_item_id for i in self.items]
        i = ids.index(iid)
        it = self.items.pop(i)
        self.items.insert(i + pos_shift, it)

    async def move_next(self, qid, iid):
        self.calls.append(("move_next", iid))
        if "move" in self.fail:
            raise RuntimeError("nope")


class FakePlayers:
    def __init__(self, queues=None):
        self.calls, self.fail, self.queues = [], False, queues

    async def next_track(self, pid):
        self.calls.append(("next", pid))
        if self.fail:
            raise RuntimeError("nope")
        q = self.queues
        if q is not None:  # MA moves on to the next song
            ids = [i.queue_item_id for i in q.items]
            if q.current in ids and ids.index(q.current) + 1 < len(ids):
                q.current = ids[ids.index(q.current) + 1]


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
    client = NS(player_queues=queues, players=FakePlayers(queues), music=FakeMusic(),
                server_info=NS(base_url="http://ma:8095"))
    s = GuestSession(GuestRules(**rules))
    g = s.join("device-abcdef12", "Sam")
    return client, s, g


async def test_add_track_credits_the_new_item():
    client, s, g = setup()
    g.offered.add("x://t/9")
    await add_track(client, Q, "tv", s, g, "x://t/9", now=1)
    new = [i.queue_item_id for i in client.player_queues.items if s.added_by(i.queue_item_id)]
    assert len(new) == 1
    assert client.player_queues.calls == [("play_media", "x://t/9", "next")]


async def test_add_respects_waiting_limit():
    client, s, g = setup(max_waiting=1)
    g.offered.update({"x://t/1", "x://t/2"})
    await add_track(client, Q, "tv", s, g, "x://t/1", now=1)
    with pytest.raises(GuestError, match="1 songs waiting"):
        await add_track(client, Q, "tv", s, g, "x://t/2", now=2)


async def test_add_failure_is_a_guest_error():
    client, s, g = setup()
    g.offered.add("x://t/1")
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
    await skip(client, Q, "tv", s, g, "cur")
    assert client.players.calls == [("next", "tv")] and g.skips_used == 1
    client.players.fail = True
    with pytest.raises(GuestError):
        await skip(client, Q, "tv", s, g, "cur")
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
    results = await guest_search(client, "love", guest=g)
    assert client.music.calls == [("love", ["track"], 20)]
    assert results == [{"uri": "x://t/1", "title": "Song", "subtitle": "Band", "imageUrl": ""}]
    assert await guest_search(client, "  ", guest=g) == []
    assert "x://t/1" in g.offered


async def test_guest_songs_play_first_come_first_served_before_the_rest():
    # autoplay / other queued songs stay behind the guests' songs
    client, s, g = setup([item("cur", "Now"), item("auto1", "Auto 1"), item("auto2", "Auto 2")])
    ana = s.join("device-ana-12345", "Ana")
    g.offered.update({"x://t/1", "x://t/3"})
    ana.offered.add("x://t/2")
    await add_track(client, Q, "tv", s, g, "x://t/1", now=1)    # Sam first
    await add_track(client, Q, "tv", s, ana, "x://t/2", now=2)  # then Ana
    await add_track(client, Q, "tv", s, g, "x://t/3", now=3)    # then Sam again
    order = [(s.added_by(i.queue_item_id) or i.media_item.name) for i in client.player_queues.items]
    assert order == ["Now", "Sam", "Ana", "Sam", "Auto 1", "Auto 2"]
    uris = [i.media_item.uri for i in client.player_queues.items[1:4]]
    assert uris == ["x://t/1", "x://t/2", "x://t/3"]


# --- review fixes -------------------------------------------------------------------

import asyncio  # noqa: E402


async def searched(client, s, g, *uris):
    """Pretend the guest's own search returned these uris (only those can be added)."""
    for u in uris:
        g.offered.add(u)


async def test_parallel_adds_cannot_beat_the_limits():
    client, s, g = setup(max_waiting=3, cooldown=60)
    slow = client.player_queues.play_media

    async def slowed(*a, **k):
        await asyncio.sleep(0.01)
        return await slow(*a, **k)
    client.player_queues.play_media = slowed
    uris = [f"x://t/{n}" for n in range(10)]
    await searched(client, s, g, *uris)
    results = await asyncio.gather(*(add_track(client, Q, "tv", s, g, u, now=1) for u in uris),
                                   return_exceptions=True)
    assert sum(1 for r in results if r is None) == 1          # cooldown: only the first gets in
    assert all(isinstance(r, GuestError) for r in results if r is not None)


async def test_only_songs_from_the_guests_own_search_can_be_added():
    client, s, g = setup()
    for bad in ("http://192.168.1.1/stream.mp3", "https://music.youtube.com/playlist?list=1", "x://t/never-searched"):
        with pytest.raises(GuestError):
            await add_track(client, Q, "tv", s, g, bad, now=1)
    assert client.player_queues.calls == []


async def test_search_results_become_addable():
    client, s, g = setup()
    await guest_search(client, "love", guest=g)
    await add_track(client, Q, "tv", s, g, "x://t/1", now=1)


async def test_queue_read_from_the_current_song_in_long_queues():
    many = [item(f"old{n}", f"Old {n}") for n in range(600)] + [item("cur", "Now"), item("next", "Next")]
    client, s, g = setup(many)
    client.player_queues.current_index = 600
    st = await guest_state(client, Q, s, g)
    assert st["nowPlaying"]["title"] == "Now" and [u["itemId"] for u in st["upcoming"]] == ["next"]


async def test_skip_names_the_song_and_two_at_once_skip_one():
    client, s, g = setup([item("cur", "Now"), item("next", "Next")])
    ana = s.join("device-ana-12345", "Ana")
    r = await asyncio.gather(skip(client, Q, "tv", s, g, "cur"), skip(client, Q, "tv", s, ana, "cur"),
                             return_exceptions=True)
    client.player_queues.current = "next"   # (MA moved on after the first skip)
    assert client.players.calls == [("next", "tv")]
    assert sum(1 for x in r if isinstance(x, GuestError)) == 1
    assert g.skips_used + ana.skips_used == 1


async def test_skip_when_the_song_already_changed_is_refused_and_free():
    client, s, g = setup()
    with pytest.raises(GuestError, match="already changed"):
        await skip(client, Q, "tv", s, g, "something-else")
    assert g.skips_used == 0 and client.players.calls == []
