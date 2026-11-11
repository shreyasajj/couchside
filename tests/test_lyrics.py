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
