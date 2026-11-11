"""Synced lyrics: LRC parsing, line lookup, and fetching (MA metadata, then LRCLIB). Qt-free."""

from __future__ import annotations

import asyncio
import bisect
import logging
import re
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from couchside import __version__

log = logging.getLogger(__name__)

LRCLIB = "https://lrclib.net/api"
USER_AGENT = f"Couchside/{__version__} (https://github.com/shreyasajj/couchside)"
SEARCH_DURATION_SLACK = 3.0  # seconds

# [mm:ss], [mm:ss.xx], [mm:ss:xx] (colon hundredths), [h:mm:ss.xx]
_TIME_TAG = re.compile(r"\[(\d{1,3}):(\d{1,2})(?::(\d{1,2}))?(?:\.(\d{1,3}))?\]")
_WORD_STAMP = re.compile(r"<\d{1,3}:\d{1,2}(?:[.:]\d{1,3})?>")
_OFFSET = re.compile(r"^\s*\[offset:\s*([+-]?\d+)\s*\]", re.IGNORECASE | re.MULTILINE)
_ARTIST_SPLIT = re.compile(r"\s*(?:/|,|&|\bfeat\.?\b|\bft\.?\b|\s+x\s+)\s*", re.IGNORECASE)


@dataclass(frozen=True)
class LyricLine:
    time: float  # seconds
    text: str


@dataclass(frozen=True)
class TrackInfo:
    key: str
    title: str
    artist: str
    album: str
    duration: float | None
    uri: str | None


def _tag_seconds(m: re.Match) -> float:
    a, b, c, frac = m.group(1), m.group(2), m.group(3), m.group(4)
    if c is not None and frac is not None:   # [h:mm:ss.xx]
        return int(a) * 3600 + int(b) * 60 + int(c) + float("0." + frac)
    if c is not None:                        # [mm:ss:xx] colon hundredths
        return int(a) * 60 + int(b) + float("0." + c)
    return int(a) * 60 + int(b) + (float("0." + frac) if frac else 0.0)


def parse_lrc(text: str | None) -> list[LyricLine]:
    """Timed lines from LRC text.

    Tags at the start of a line share the text after them; a tag in the middle of a
    line starts a new line (text before it belongs to the earlier tags). Per-word
    `<mm:ss.xx>` stamps (enhanced LRC) are removed. Tags without a time and lines that
    do not start with a time are ignored.
    """
    if not text:
        return []
    m = _OFFSET.search(text)
    offset = int(m.group(1)) / 1000 if m else 0.0
    lines: list[LyricLine] = []

    def emit(times: list[float], words: str) -> None:
        words = " ".join(_WORD_STAMP.sub("", words).split())
        lines.extend(LyricLine(round(max(0.0, t - offset), 3), words) for t in times)

    for raw in text.splitlines():
        tags = list(_TIME_TAG.finditer(raw))
        if not tags or raw[:tags[0].start()].strip("\ufeff \t"):
            continue
        pending: list[float] = []
        pos = tags[0].start()
        for tag in tags:
            between = raw[pos:tag.start()]
            if between.strip() and pending:
                emit(pending, between)
                pending = []
            pending.append(_tag_seconds(tag))
            pos = tag.end()
        emit(pending, raw[pos:])
    lines.sort(key=lambda line: line.time)
    if not any(line.text for line in lines):
        return []  # only timestamps / blank lines: nothing to sing along to
    return lines


def line_index_at(lines: list[LyricLine], position: float) -> int:
    """Index of the line being sung at `position` (-1 before the first line)."""
    return bisect.bisect_right([line.time for line in lines], position) - 1


def first_artist(artist: str) -> str:
    return _ARTIST_SPLIT.split(artist or "", maxsplit=1)[0].strip()


HttpGet = Callable[[str, dict], Awaitable[tuple[int, Any]]]
MaLookup = Callable[[str], Awaitable[str | None]]


_UNKNOWN = object()  # a step could not answer (network error, 429, 5xx): retry later


class LyricsFetcher:
    """MA's own LRC first, then LRCLIB get, then LRCLIB search.

    One overall time budget for the chain (`timeout`), a short one for the MA step.
    Only definite answers are cached (found, 404, no synced lyrics, instrumental, no
    match); a blip means "try again next time this song plays". Songs without a length
    (radio, live streams) are not looked up: nothing to match on and no usable position.
    """

    def __init__(self, http_get: HttpGet, ma_lookup: MaLookup | None = None,
                 timeout: float = 10.0, ma_timeout: float = 2.0, max_entries: int = 300):
        self._http = http_get
        self._ma = ma_lookup
        self._timeout = timeout
        self._ma_timeout = ma_timeout
        self._max = max_entries
        self._cache: OrderedDict[str, list[LyricLine] | None] = OrderedDict()  # LRU
        self._inflight: dict[str, asyncio.Future] = {}

    async def get(self, info: TrackInfo) -> list[LyricLine] | None:
        if not info.duration:
            return None
        if info.key in self._cache:
            self._cache.move_to_end(info.key)
            return self._cache[info.key]
        # The same song asked for again while a lookup runs (A -> B -> A): share it.
        fut = self._inflight.get(info.key)
        if fut is None:
            fut = asyncio.ensure_future(self._lookup(info))
            self._inflight[info.key] = fut
            fut.add_done_callback(lambda _f: self._inflight.pop(info.key, None))
        return await asyncio.shield(fut)

    async def _lookup(self, info: TrackInfo) -> list[LyricLine] | None:
        try:
            lines, definite = await asyncio.wait_for(self._chain(info), self._timeout)
        except Exception as e:
            log.info("lyrics for %r gave up: %s", info.title, e or type(e).__name__)
            lines, definite = None, False
        if lines or definite:
            self._cache[info.key] = lines or None
            while len(self._cache) > self._max:
                self._cache.popitem(last=False)
        return lines or None

    async def _chain(self, info: TrackInfo) -> tuple[list[LyricLine] | None, bool]:
        definite = True
        steps = ((self._from_ma, self._ma_timeout), (self._from_lrclib_get, None),
                 (self._from_lrclib_search, None))
        for step, limit in steps:
            try:
                result = await (asyncio.wait_for(step(info), limit) if limit else step(info))
            except asyncio.CancelledError:
                raise
            except Exception as e:  # timeouts, network, bad data
                log.info("lyrics %s for %r: %s", step.__name__, info.title, e or type(e).__name__)
                result = _UNKNOWN
            if result is _UNKNOWN:
                definite = False
            elif result:
                return result, True
        return None, definite

    async def _from_ma(self, info: TrackInfo):
        if self._ma is None or not info.uri:
            return None
        return parse_lrc(await self._ma(info.uri)) or None

    async def _from_lrclib_get(self, info: TrackInfo):
        params = {"track_name": info.title, "artist_name": first_artist(info.artist),
                  "duration": round(info.duration or 0)}
        if info.album:
            params["album_name"] = info.album
        status, data = await self._http(f"{LRCLIB}/get", params)
        if status == 404:
            return None
        if status != 200 or not isinstance(data, dict):
            return _UNKNOWN
        if data.get("instrumental"):
            return None
        return parse_lrc(data.get("syncedLyrics")) or None

    async def _from_lrclib_search(self, info: TrackInfo):
        # Title only: the first-artist guess fails for duos ("Simon & Garfunkel"); the
        # length check keeps covers, remixes and same-name songs out.
        status, data = await self._http(f"{LRCLIB}/search", {"track_name": info.title})
        if status != 200 or not isinstance(data, list):
            return _UNKNOWN
        for hit in data:
            if not isinstance(hit, dict) or not hit.get("syncedLyrics"):
                continue
            d = hit.get("duration")
            if not isinstance(d, (int, float)) or abs(d - (info.duration or 0)) > SEARCH_DURATION_SLACK:
                continue
            lines = parse_lrc(hit["syncedLyrics"])
            if lines:
                return lines
        return None


class HttpClient:
    """GET -> (status, JSON or None) over one shared aiohttp session (created on first
    use, so it binds to the running loop), with Couchside's User-Agent."""

    def __init__(self, timeout: float = 8.0):
        self._timeout = timeout
        self._session = None

    async def get(self, url: str, params: dict) -> tuple[int, Any]:
        import aiohttp

        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self._timeout),
                headers={"User-Agent": USER_AGENT})
        async with self._session.get(url, params=params) as r:
            if r.status != 200:
                return r.status, None
            try:
                return r.status, await r.json(content_type=None)
            except Exception:
                return r.status, None

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None
