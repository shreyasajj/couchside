"""Search, recently played/added and play actions, as plain rows for the TV (Qt-free)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)

IMAGE_SIZE = 256  # MA 2.10's image proxy accepts 256, 512 or 1024
SEARCH_ERROR = "Search failed — check the connection"
_ROWS = [("tracks", "Tracks"), ("albums", "Albums"), ("artists", "Artists"),
         ("playlists", "Playlists"), ("radio", "Radio")]


@dataclass(frozen=True)
class MediaCard:
    key: str
    kind: str  # track album artist playlist radio (or another MA media type)
    title: str
    subtitle: str
    image_url: str | None
    uri: str


@dataclass(frozen=True)
class SearchOutcome:
    rows: list[tuple[str, list[MediaCard]]] = field(default_factory=list)
    error: str = ""


def image_url(client: Any, item: Any) -> str | None:
    """MA image-proxy URL when the image has a proxy id, else a public http(s) path."""
    try:
        img = client.music.get_media_item_image(item)
    except Exception:
        img = getattr(item, "image", None)
    if img is None:
        return None
    proxy_id = getattr(img, "proxy_id", None)
    base = getattr(getattr(client, "server_info", None), "base_url", None)
    if proxy_id and base:
        return f"{base}/imageproxy/{proxy_id}?size={IMAGE_SIZE}"
    path = getattr(img, "path", None) or ""
    if getattr(img, "remotely_accessible", False) and path.startswith(("http://", "https://")):
        return path
    return None


def _kind(item: Any) -> str:
    mt = getattr(item, "media_type", None)
    return str(getattr(mt, "value", mt) or "").lower()


def _subtitle(item: Any, kind: str) -> str:
    if kind == "track":
        album = getattr(getattr(item, "album", None), "name", None)
        return " · ".join(p for p in (getattr(item, "artist_str", None), album) if p)
    if kind == "album":
        return getattr(item, "artist_str", None) or ""
    if kind == "playlist":
        return getattr(item, "owner", None) or ""
    return ""


def to_card(client: Any, item: Any) -> MediaCard | None:
    uri = getattr(item, "uri", None)
    if not uri:
        return None
    kind = _kind(item)
    return MediaCard(key=uri, kind=kind, title=getattr(item, "name", "") or "",
                     subtitle=_subtitle(item, kind), image_url=image_url(client, item), uri=uri)


def _cards(client: Any, items: Any) -> list[MediaCard]:
    return [c for c in (to_card(client, i) for i in (items or [])) if c is not None]


async def search(client: Any, query: str, limit: int = 12) -> SearchOutcome:
    query = (query or "").strip()
    if not query:
        return SearchOutcome()
    try:
        res = await client.music.search(query, limit=limit)
    except Exception as e:
        log.warning("search %r failed: %s", query, e)
        return SearchOutcome(error=SEARCH_ERROR)
    rows = [(title, _cards(client, getattr(res, attr, None))) for attr, title in _ROWS]
    return SearchOutcome(rows=[(t, cards) for t, cards in rows if cards])


async def recents(client: Any, limit: int = 15) -> list[tuple[str, list[MediaCard]]]:
    """Recently played and recently added; each one can fail on its own.

    MA 2.10 (schema 65) has no `recently_added_tracks` (needs schema 101), so the
    library sorted by date added stands in for it.
    """
    rows: list[tuple[str, list[MediaCard]]] = []
    try:
        rows.append(("Recently played", _cards(client, await client.music.recently_played(limit=limit))))
    except Exception as e:
        log.warning("recently played failed: %s", e)
    try:
        added = await client.music.get_library_tracks(limit=limit, order_by="timestamp_added_desc")
        rows.append(("Recently added", _cards(client, added)))
    except Exception as e:
        log.warning("recently added failed: %s", e)
    return [(t, cards) for t, cards in rows if cards]


async def play(client: Any, queue_id: str, uri: str, mode: str) -> bool:
    """mode: now (play), next (after the current track), add (end of the queue)."""
    from music_assistant_models.enums import QueueOption

    option = {"now": QueueOption.PLAY, "next": QueueOption.NEXT, "add": QueueOption.ADD}.get(mode)
    if option is None:
        return False
    try:
        await client.player_queues.play_media(queue_id, uri, option=option)
        return True
    except Exception as e:
        log.warning("play %s (%s) on %s failed: %s", uri, mode, queue_id, e)
        return False
