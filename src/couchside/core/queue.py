"""The controlled speaker's queue as rows, and the actions on a row (Qt-free)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from couchside.core.library import image_url

log = logging.getLogger(__name__)

_ACTIONS = {"play": "play_index", "next": "move_next", "up": "move_up",
            "down": "move_down", "remove": "delete_item"}


@dataclass(frozen=True)
class QueueRow:
    item_id: str
    title: str
    subtitle: str
    image_url: str | None
    duration: float | None
    current: bool


def _row(client: Any, item: Any, current_id: str | None) -> QueueRow:
    media = getattr(item, "media_item", None)
    title = getattr(media, "name", None) or getattr(item, "name", "") or ""
    subtitle = getattr(media, "artist_str", None) or ""
    art = image_url(client, media) if media is not None else image_url(client, item)
    duration = getattr(item, "duration", None)
    return QueueRow(item.queue_item_id, title, subtitle, art,
                    duration if isinstance(duration, (int, float)) else None,
                    item.queue_item_id == current_id)


async def load_queue(client: Any, queue_id: str | None, current_item_id: str | None) -> list[QueueRow]:
    """Items from the current one onwards (what is still to play). Earlier items are
    history and stay hidden; an unknown current item shows the whole queue."""
    if not queue_id:
        return []
    try:
        items = await client.player_queues.get_queue_items(queue_id, limit=500)
    except Exception as e:
        log.warning("loading queue %s failed: %s", queue_id, e)
        return []
    ids = [i.queue_item_id for i in items]
    start = ids.index(current_item_id) if current_item_id in ids else 0
    return [_row(client, i, current_item_id) for i in items[start:]]


async def queue_action(client: Any, queue_id: str | None, item_id: str, action: str) -> bool:
    method = _ACTIONS.get(action)
    if method is None or not queue_id:
        return False
    try:
        await getattr(client.player_queues, method)(queue_id, item_id)
        return True
    except Exception as e:
        log.warning("queue %s %s on %s failed: %s", action, item_id, queue_id, e)
        return False
