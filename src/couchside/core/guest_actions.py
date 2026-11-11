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


QUEUE_WINDOW = 200


async def _queue(client: Any, queue_id: str) -> tuple[str | None, list]:
    """(current item id, items from the current one on). Long queues (hours of autoplay)
    are read from the current song, not from the start."""
    try:
        q = client.player_queues.get(queue_id)
    except Exception:
        q = None
    current = getattr(getattr(q, "current_item", None), "queue_item_id", None)
    index = getattr(q, "current_index", None)
    offset = index if isinstance(index, int) and index > 0 else 0
    items = list(await client.player_queues.get_queue_items(queue_id, limit=QUEUE_WINDOW, offset=offset))
    if offset and current not in [i.queue_item_id for i in items]:
        items = list(await client.player_queues.get_queue_items(queue_id, limit=QUEUE_WINDOW))
    return current, items


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
    # Allow-list: only songs this guest's own search returned (never an arbitrary URL).
    if (not isinstance(uri, str) or not uri or len(uri) > MAX_URI or uri not in guest.offered
            or any(seg in uri for seg in _NOT_TRACKS)):
        raise GuestError("Only songs from your search can be added")
    async with session.lock:
        await _add_locked(client, queue_id, session, guest, uri, now)


async def _add_locked(client, queue_id, session, guest, uri, now) -> None:
    current, items = await _queue(client, queue_id)
    upcoming_ids = [i.queue_item_id for i in _upcoming(current, items)]
    session.check_add(guest, upcoming_ids, now)
    # Guests' songs form a first-come, first-served block right after the current song,
    # ahead of everything else (MA's autoplay can fill the queue with dozens of songs, and
    # it doesn't mark them): insert as "next", then move below the guest songs waiting.
    ahead = sum(1 for i in upcoming_ids if session.added_by(i) is not None)
    before = {i.queue_item_id for i in items}
    if not await library.play(client, queue_id, uri, "next"):
        raise GuestError("Couldn't add that song — try again")
    try:
        _, after = await _queue(client, queue_id)
    except Exception:
        after = []
    new = [i for i in after if i.queue_item_id not in before]
    match = [i for i in new if getattr(getattr(i, "media_item", None), "uri", None) == uri] or new
    new_id = match[-1].queue_item_id if match else None
    session.note_added(guest, new_id, now)
    if new_id and ahead:
        try:
            await client.player_queues.move_item(queue_id, new_id, pos_shift=ahead)
        except Exception as e:  # the song is in; only its place is off
            log.warning("placing guest song failed: %s", e)


async def skip(client: Any, queue_id: str, player_id: str, session: GuestSession, guest: Guest,
               item_id: str) -> None:
    """Skip the song the guest saw playing (`item_id`): if it already changed (another
    guest skipped it a moment ago), nothing happens and no skip is used."""
    async with session.lock:
        current, _ = await _queue(client, queue_id)
        if not current or item_id != current:
            raise GuestError("That song already changed — have a look again")
        session.use_skip(guest)
        try:
            await client.players.next_track(player_id)
        except Exception as e:
            if not guest.admin:
                guest.skips_used -= 1  # not the guest's fault: give it back
            log.warning("guest skip failed: %s", e)
            raise GuestError("Couldn't skip — try again") from e


async def boost(client: Any, queue_id: str, session: GuestSession, guest: Guest, item_id: str) -> None:
    async with session.lock:
        await _boost_locked(client, queue_id, session, guest, item_id)


async def _boost_locked(client, queue_id, session, guest, item_id) -> None:
    current, items = await _queue(client, queue_id)
    session.use_boost(guest, item_id, [i.queue_item_id for i in _upcoming(current, items)])
    try:
        await client.player_queues.move_next(queue_id, item_id)
    except Exception as e:
        if not guest.admin:
            guest.boosts_used -= 1
        log.warning("guest boost failed: %s", e)
        raise GuestError("Couldn't boost — try again") from e


async def guest_state(client: Any, queue_id: str, session: GuestSession, guest: Guest) -> dict:
    current, items = await _queue(client, queue_id)
    cur = next((i for i in items if i.queue_item_id == current), None)
    upcoming = _upcoming(current, items)
    return {
        "name": guest.name,
        "nowPlaying": ({**_info(client, cur), "itemId": current, "addedBy": session.added_by(current) or ""}
                       if cur is not None else None),
        "upcoming": [{"itemId": i.queue_item_id, **_info(client, i),
                      "addedBy": session.added_by(i.queue_item_id) or "",
                      "mine": session.owns(guest, i.queue_item_id)}
                     for i in upcoming[:UPCOMING_SHOWN]],
        "remaining": session.remaining(guest, [i.queue_item_id for i in upcoming]),
    }


async def guest_search(client: Any, query: str, guest: Guest | None = None) -> list[dict]:
    """Tracks only: albums or playlists would get round the per-guest limit. The results
    become the songs this guest may add."""
    from music_assistant_models.enums import MediaType

    query = (query or "").strip()[:MAX_QUERY]
    if not query:
        return []
    res = await client.music.search(query, media_types=[MediaType.TRACK], limit=20)
    out = []
    for c in library._cards(client, getattr(res, "tracks", None)):
        out.append({"uri": c.uri, "title": c.title, "subtitle": c.subtitle, "imageUrl": c.image_url or ""})
    if guest is not None:
        guest.offer(r["uri"] for r in out)
    return out
