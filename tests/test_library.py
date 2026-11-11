from types import SimpleNamespace as NS

from music_assistant_models.enums import QueueOption

from couchside.core.library import MediaCard, image_url, play, recents, search, to_card


def img(path="https://cdn/x.jpg", proxy_id="pid", remote=True):
    return NS(path=path, proxy_id=proxy_id, remotely_accessible=remote)


def track(name="Song", uri="tidal://track/1", artist="Artist", album="Album", image=None):
    return NS(name=name, uri=uri, media_type=NS(value="track"), artist_str=artist,
              album=NS(name=album) if album else None, image=image)


class FakeMusic:
    def __init__(self, results=None, fail=(), played=(), added=()):
        self.results, self.fail, self.played, self.added = results, set(fail), played, added
        self.calls = []

    def get_media_item_image(self, item, *_):
        return getattr(item, "image", None)

    async def search(self, q, limit=12):
        self.calls.append(("search", q, limit))
        if "search" in self.fail:
            raise RuntimeError("down")
        return self.results

    async def recently_played(self, limit=10):
        if "played" in self.fail:
            raise RuntimeError("down")
        return list(self.played)

    async def get_library_tracks(self, limit=None, order_by=None):
        self.calls.append(("library_tracks", limit, order_by))
        if "added" in self.fail:
            raise RuntimeError("down")
        return list(self.added)


class FakeQueues:
    def __init__(self, fail=False):
        self.calls, self.fail = [], fail

    async def play_media(self, queue_id, media, option=None):
        self.calls.append((queue_id, media, option))
        if self.fail:
            raise RuntimeError("nope")


def client(music=None, queues=None):
    return NS(music=music or FakeMusic(), player_queues=queues or FakeQueues(),
              server_info=NS(base_url="http://ma:8095"))


def test_track_card_subtitle():
    c = to_card(client(), track())
    assert c == MediaCard("tidal://track/1", "track", "Song", "Artist · Album", c.image_url, "tidal://track/1")


def test_card_without_uri_is_none():
    assert to_card(client(), track(uri="")) is None


def test_playlist_and_album_subtitles():
    pl = NS(name="Mix", uri="sp://pl/1", media_type=NS(value="playlist"), owner="Shre", image=None)
    al = NS(name="LP", uri="sp://al/1", media_type=NS(value="album"), artist_str="Band", image=None)
    assert to_card(client(), pl).subtitle == "Shre"
    assert to_card(client(), al).subtitle == "Band"


def test_image_url_prefers_proxy():
    assert image_url(client(), track(image=img())) == "http://ma:8095/imageproxy/pid?size=256"
    assert image_url(client(), track(image=img(proxy_id=None))) == "https://cdn/x.jpg"
    assert image_url(client(), track(image=img(proxy_id=None, remote=False))) is None
    assert image_url(client(), track(image=None)) is None


async def test_search_orders_and_drops_empty_rows():
    res = NS(tracks=[track()], albums=[], artists=[NS(name="A", uri="x://artist/1", media_type=NS(value="artist"), image=None)],
             playlists=[], radio=[])
    out = await search(client(FakeMusic(results=res)), "love")
    assert [title for title, _ in out.rows] == ["Tracks", "Artists"]
    assert out.error == ""


async def test_blank_query_does_not_call_server():
    m = FakeMusic()
    out = await search(client(m), "   ")
    assert out.rows == [] and m.calls == []


async def test_search_failure_returns_error():
    out = await search(client(FakeMusic(fail={"search"})), "love")
    assert out.rows == [] and out.error == "Search failed — check the connection"


async def test_recents_survive_one_failing_call():
    rows = await recents(client(FakeMusic(fail={"played"}, added=[track()])))
    assert [t for t, _ in rows] == ["Recently added"]


async def test_recently_added_uses_library_order():
    m = FakeMusic(played=[track(uri="a://1")], added=[track(uri="b://1")])
    rows = await recents(client(m), limit=15)
    assert ("library_tracks", 15, "timestamp_added_desc") in m.calls
    assert [t for t, _ in rows] == ["Recently played", "Recently added"]


async def test_play_modes_map_to_queue_options():
    q = FakeQueues()
    c = client(queues=q)
    for mode in ("now", "next", "add"):
        assert await play(c, "q1", "x://track/1", mode)
    assert [opt for _, _, opt in q.calls] == [QueueOption.PLAY, QueueOption.NEXT, QueueOption.ADD]


async def test_play_failure_returns_false():
    assert not await play(client(queues=FakeQueues(fail=True)), "q1", "x://t", "now")
    assert not await play(client(), "q1", "x://t", "bogus")
