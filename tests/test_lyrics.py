import asyncio

from couchside.core.lyrics import (
    LyricLine, LyricsFetcher, TrackInfo, first_artist, line_index_at, parse_lrc,
)

LRC = "[00:15.14] I will shelter you\n[00:18.36] For days\n"


def test_parse_basic():
    assert parse_lrc(LRC) == [LyricLine(15.14, "I will shelter you"), LyricLine(18.36, "For days")]


def test_parse_multiple_tags_one_line():
    assert parse_lrc("[00:01.00][00:05.50]Chorus") == [LyricLine(1.0, "Chorus"), LyricLine(5.5, "Chorus")]


def test_parse_offset():
    # LRC: a positive offset (ms) shows lyrics earlier
    assert parse_lrc("[offset:+500]\n[00:10.00]x") == [LyricLine(9.5, "x")]
    assert parse_lrc("[offset:-250]\n[00:10.00]x") == [LyricLine(10.25, "x")]


def test_parse_ignores_metadata_and_untimed():
    assert parse_lrc("[ar:Band]\n[ti:Song]\nno tag here\n[00:02]Two") == [LyricLine(2.0, "Two")]


def test_parse_sorts_and_keeps_blank():
    assert parse_lrc("[00:09.00]b\n[00:03.00]\n[00:01.00]a") == [
        LyricLine(1.0, "a"), LyricLine(3.0, ""), LyricLine(9.0, "b")]


def test_parse_hours():
    assert parse_lrc("[1:02:03.50]late") == [LyricLine(3723.5, "late")]


def test_parse_garbage_is_empty():
    assert parse_lrc(None) == [] and parse_lrc("") == [] and parse_lrc("just words\n[xx:yy]") == []


def test_index_before_first_line():
    assert line_index_at(parse_lrc(LRC), 3.0) == -1
    assert line_index_at([], 10.0) == -1


def test_index_between_lines():
    lines = parse_lrc(LRC)
    assert line_index_at(lines, 15.14) == 0
    assert line_index_at(lines, 17.0) == 0
    assert line_index_at(lines, 99.0) == 1


def test_first_artist():
    assert first_artist("Martin Garrix/Saksham/Scott Quinn") == "Martin Garrix"
    assert first_artist("A, B & C") == "A"
    assert first_artist("Koe Wetzel feat. Ella Langley") == "Koe Wetzel"
    assert first_artist("Disclosure x Sam Smith") == "Disclosure"
    assert first_artist("Simon & Garfunkel") == "Simon"
    assert first_artist("") == ""


INFO = TrackInfo(key="k1", title="Ain't Letting You Down", artist="Martin Garrix/Saksham",
                 album="Ain't Letting You Down", duration=261, uri="library://track/22")


class Http:
    def __init__(self, routes):
        self.routes, self.calls = routes, []

    async def __call__(self, url, params):
        self.calls.append((url.rsplit("/", 1)[-1], dict(params)))
        r = self.routes.get(url.rsplit("/", 1)[-1])
        if isinstance(r, Exception):
            raise r
        return r if r is not None else (404, None)


async def test_ma_lyrics_win():
    http = Http({})

    async def ma(uri):
        return "[00:01.00]from MA"
    lines = await LyricsFetcher(http, ma_lookup=ma).get(INFO)
    assert lines == [LyricLine(1.0, "from MA")] and http.calls == []


async def test_lrclib_get_used_with_first_artist():
    http = Http({"get": (200, {"syncedLyrics": LRC, "instrumental": False})})
    lines = await LyricsFetcher(http).get(INFO)
    assert lines[0].text == "I will shelter you"
    name, params = http.calls[0]
    assert name == "get" and params["artist_name"] == "Martin Garrix" and params["duration"] == 261


async def test_falls_back_to_search_by_duration():
    http = Http({"get": (404, None), "search": (200, [
        {"duration": 300.0, "syncedLyrics": "[00:01]wrong length"},
        {"duration": 262.0, "syncedLyrics": "[00:02]right one"},
        {"duration": 261.0, "syncedLyrics": None, "plainLyrics": "plain"},
    ])})
    assert await LyricsFetcher(http).get(INFO) == [LyricLine(2.0, "right one")]


async def test_plain_only_is_none():
    http = Http({"get": (200, {"syncedLyrics": None, "plainLyrics": "words"}), "search": (200, [])})
    assert await LyricsFetcher(http).get(INFO) is None


async def test_instrumental_is_none():
    http = Http({"get": (200, {"instrumental": True, "syncedLyrics": None})})
    assert await LyricsFetcher(http).get(INFO) is None


async def test_errors_and_timeouts_are_none():
    async def slow(url, params):
        await asyncio.sleep(5)

    async def ma_boom(uri):
        raise RuntimeError("down")
    assert await LyricsFetcher(Http({"get": RuntimeError("x"), "search": ValueError("y")}),
                               ma_lookup=ma_boom).get(INFO) is None
    assert await LyricsFetcher(slow, timeout=0.05).get(INFO) is None
    assert await LyricsFetcher(Http({"get": (200, "not json object"), "search": (200, {"oops": 1})})).get(INFO) is None


async def test_results_cached_including_misses():
    http = Http({"get": (404, None), "search": (200, [])})
    f = LyricsFetcher(http)
    assert await f.get(INFO) is None
    assert await f.get(INFO) is None
    assert len(http.calls) == 2  # get + search once, then the cached miss


# --- review fixes ----------------------------------------------------------------

async def test_transient_failure_not_cached():
    # A blip (error / 429 / 5xx) must not stick: the next try may find lyrics.
    flaky = Http({"get": RuntimeError("wifi"), "search": (429, None)})
    f = LyricsFetcher(flaky)
    assert await f.get(INFO) is None
    flaky.routes = {"get": (200, {"syncedLyrics": LRC})}
    assert (await f.get(INFO))[0].text == "I will shelter you"


async def test_server_error_not_cached():
    http = Http({"get": (503, None), "search": (500, None)})
    f = LyricsFetcher(http)
    assert await f.get(INFO) is None
    http.routes = {"get": (200, {"syncedLyrics": LRC})}
    assert await f.get(INFO) is not None


async def test_no_duration_means_no_lookup():
    # Radio / live streams: no length to match and no meaningful position.
    http = Http({"get": (200, {"syncedLyrics": LRC}), "search": (200, [{"syncedLyrics": LRC}])})
    from dataclasses import replace
    assert await LyricsFetcher(http).get(replace(INFO, duration=None)) is None
    assert await LyricsFetcher(http).get(replace(INFO, duration=0)) is None
    assert http.calls == []


async def test_slow_ma_step_does_not_block_lrclib():
    async def ma_hangs(uri):
        await asyncio.sleep(5)
    http = Http({"get": (200, {"syncedLyrics": LRC})})
    f = LyricsFetcher(http, ma_lookup=ma_hangs, ma_timeout=0.05, timeout=1.0)
    assert (await f.get(INFO))[0].text == "I will shelter you"


async def test_total_wait_is_bounded():
    async def slow(url, params):
        await asyncio.sleep(0.3)
        return 404, None
    import time
    start = time.monotonic()
    assert await LyricsFetcher(slow, timeout=0.4).get(INFO) is None  # get + search would be 0.6 s
    assert time.monotonic() - start < 0.55


def test_parse_lrc_with_no_words_is_empty():
    assert parse_lrc("[00:00.00]\n[00:05.00]  ") == []


# --- unusual LRC files -------------------------------------------------------------

def test_parse_colon_centiseconds():
    # some files write [mm:ss:cc] instead of [mm:ss.cc]
    assert parse_lrc("[00:01:50]a\n[01:02:05]b") == [LyricLine(1.5, "a"), LyricLine(62.05, "b")]


def test_parse_text_between_mid_line_tags():
    assert parse_lrc("[00:01.00]hello [00:02.00]world") == [LyricLine(1.0, "hello"), LyricLine(2.0, "world")]


def test_parse_strips_word_timestamps():
    # enhanced LRC: per-word <mm:ss.xx> stamps
    assert parse_lrc("[00:01.00]<00:01.00>I <00:01.40>will <00:01.90>shelter") == [
        LyricLine(1.0, "I will shelter")]


def test_parse_leading_tags_share_text():
    assert parse_lrc("[00:01.00][00:09.00] chorus line") == [
        LyricLine(1.0, "chorus line"), LyricLine(9.0, "chorus line")]


# --- lookup efficiency -------------------------------------------------------------

async def test_concurrent_lookups_share_one_request():
    gate = asyncio.Event()

    async def http(url, params):
        calls.append(url)
        await gate.wait()
        return 200, {"syncedLyrics": LRC}
    calls = []
    f = LyricsFetcher(http)
    a = asyncio.ensure_future(f.get(INFO))
    b = asyncio.ensure_future(f.get(INFO))   # A -> B -> A quickly: same song again
    await asyncio.sleep(0.01)
    gate.set()
    ra, rb = await a, await b
    assert ra == rb and ra[0].text == "I will shelter you"
    assert len(calls) == 1


async def test_cache_is_bounded():
    from dataclasses import replace
    http = Http({"get": (404, None), "search": (200, [])})
    f = LyricsFetcher(http, max_entries=2)
    for k in ("a", "b", "c"):
        await f.get(replace(INFO, key=k))
    before = len(http.calls)
    await f.get(replace(INFO, key="a"))      # evicted: asked again
    await f.get(replace(INFO, key="c"))      # still cached
    assert len(http.calls) == before + 2


async def test_http_client_reuses_one_session(monkeypatch):
    import couchside.core.lyrics as lyr
    made = []

    class FakeResp:
        status = 200
        async def json(self, content_type=None):
            return {"ok": True}
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            return False

    class FakeSession:
        def __init__(self, **kw):
            made.append(kw)
            self.closed = False
        def get(self, url, params=None):
            return FakeResp()
        async def close(self):
            self.closed = True

    monkeypatch.setattr("aiohttp.ClientSession", FakeSession)
    client = lyr.HttpClient()
    assert await client.get("u", {}) == (200, {"ok": True})
    assert await client.get("u", {}) == (200, {"ok": True})
    assert len(made) == 1 and made[0]["headers"]["User-Agent"].startswith("Couchside/")
    await client.close()


async def test_http_client_post_json(monkeypatch):
    import couchside.core.lyrics as lyr
    sent = []

    class FakeResp:
        status = 200
        async def json(self, content_type=None):
            return {"ok": 1}
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            return False

    class FakeSession:
        def __init__(self, **kw):
            self.closed = False
        def post(self, url, json=None, headers=None):
            sent.append((url, json, headers))
            return FakeResp()
        async def close(self):
            self.closed = True

    monkeypatch.setattr("aiohttp.ClientSession", FakeSession)
    c = lyr.HttpClient()
    assert await c.post_json("u", {"a": 1}, headers={"H": "v"}) == (200, {"ok": 1})
    assert sent == [("u", {"a": 1}, {"H": "v"})]
