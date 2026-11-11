"""What a guest can do to the queue: add a track, skip, boost, search; and what their phone
shows. Every action goes through the session's rules first. Qt-free."""

from __future__ import annotations

import logging
from typing import Any

from couchside.core import library
from couchside.core.guests import Guest, GuestError, GuestSession

log = logging.getLogger(__name__)

MAX_URI = 500
MAX_QUERY = 100
UPCOMING_SHOWN = 30
_NOT_TRACKS = ("/album/", "/playlist/", "/artist/", "/radio/", "/podcast/", "/audiobook/", "/genre/")


async def _queue(client: Any, queue_id: str) -> tuple[str | None, list]:
    """(current item id, items in order)."""
    try:
        q = client.player_queues.get(queue_id)
    except Exception:
        q = None
    current = getattr(getattr(q, "current_item", None), "queue_item_id", None)
    items = await client.player_queues.get_queue_items(queue_id, limit=500)
    return current, list(items)


def _upcoming(current: str | None, items: list) -> list:
    ids = [i.queue_item_id for i in items]
    start = ids.index(current) + 1 if current in ids else 0
    return items[start:]


def _info(client: Any, it: Any) -> dict:
    media = getattr(it, "media_item", None)
    return {"title": getattr(media, "name", None) or getattr(it, "name", "") or "",
            "artist": getattr(media, "artist_str", None) or "",
            "imageUrl": library.image_url(client, media if media is not None else it) or ""}


async def add_track(client: Any, queue_id: str, player_id: str, session: GuestSession,
                    guest: Guest, uri: str, now: float) -> None:
    if (not isinstance(uri, str) or not uri or len(uri) > MAX_URI or "://" not in uri
            or any(seg in uri for seg in _NOT_TRACKS)):
        raise GuestError("Only songs can be added")
    current, items = await _queue(client, queue_id)
    session.check_add(guest, [i.queue_item_id for i in _upcoming(current, items)], now)
    before = {i.queue_item_id for i in items}
    if not await library.play(client, queue_id, uri, "add"):
        raise GuestError("Couldn't add that song — try again")
    try:
        _, after = await _queue(client, queue_id)
    except Exception:
        after = []
    new = [i for i in after if i.queue_item_id not in before]
    match = [i for i in new if getattr(getattr(i, "media_item", None), "uri", None) == uri] or new
    session.note_added(guest, match[-1].queue_item_id if match else None, now)


async def skip(client: Any, player_id: str, session: GuestSession, guest: Guest) -> None:
    session.use_skip(guest)
    try:
        await client.players.next_track(player_id)
    except Exception as e:
        guest.skips_used -= 1  # not the guest's fault: give it back
        log.warning("guest skip failed: %s", e)
        raise GuestError("Couldn't skip — try again") from e


async def boost(client: Any, queue_id: str, session: GuestSession, guest: Guest, item_id: str) -> None:
    current, items = await _queue(client, queue_id)
    session.use_boost(guest, item_id, [i.queue_item_id for i in _upcoming(current, items)])
    try:
        await client.player_queues.move_next(queue_id, item_id)
    except Exception as e:
        guest.boosts_used -= 1
        log.warning("guest boost failed: %s", e)
        raise GuestError("Couldn't boost — try again") from e


async def guest_state(client: Any, queue_id: str, session: GuestSession, guest: Guest) -> dict:
    current, items = await _queue(client, queue_id)
    cur = next((i for i in items if i.queue_item_id == current), None)
    upcoming = _upcoming(current, items)
    return {
        "name": guest.name,
        "nowPlaying": ({**_info(client, cur), "addedBy": session.added_by(current) or ""}
                       if cur is not None else None),
        "upcoming": [{"itemId": i.queue_item_id, **_info(client, i),
                      "addedBy": session.added_by(i.queue_item_id) or "",
                      "mine": session.owns(guest, i.queue_item_id)}
                     for i in upcoming[:UPCOMING_SHOWN]],
        "remaining": session.remaining(guest, [i.queue_item_id for i in upcoming]),
    }


async def guest_search(client: Any, query: str) -> list[dict]:
    """Tracks only: albums or playlists would get round the per-guest limit."""
    from music_assistant_models.enums import MediaType

    query = (query or "").strip()[:MAX_QUERY]
    if not query:
        return []
    res = await client.music.search(query, media_types=[MediaType.TRACK], limit=20)
    out = []
    for c in library._cards(client, getattr(res, "tracks", None)):
        out.append({"uri": c.uri, "title": c.title, "subtitle": c.subtitle, "imageUrl": c.image_url or ""})
    return out
