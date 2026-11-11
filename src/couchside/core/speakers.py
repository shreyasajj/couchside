"""Speakers and groups as rows, plus switch / sync / group / move-queue actions (Qt-free)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Iterable

log = logging.getLogger(__name__)

GROUP_PROVIDER = "sync_group"  # MA's provider for permanent synced groups


@dataclass(frozen=True)
class SpeakerRow:
    player_id: str
    name: str
    is_group: bool
    available: bool
    controlled: bool
    local: bool
    synced_to: str | None
    members: tuple[str, ...]
    can_sync: bool
    playing: str


def _is_group(player: Any) -> bool:
    t = getattr(player, "type", None)
    return str(getattr(t, "value", t) or "").lower() == "group"


def _playing(player: Any) -> str:
    media = getattr(player, "current_media", None)
    if media is None:
        return ""
    return " — ".join(x for x in (getattr(media, "title", None), getattr(media, "artist", None)) if x)


def speaker_rows(players: Iterable[Any], controlled_id: str | None, local_id: str | None) -> list[SpeakerRow]:
    """Enabled players and groups: controlled first, then this TV, the other available
    ones, then unavailable ones; names sorted within each band."""
    players = [p for p in players if getattr(p, "enabled", True)]
    by_id = {p.player_id: p for p in players}
    controlled = by_id.get(controlled_id)
    groupable = set(getattr(controlled, "can_group_with", None) or [])

    rows = []
    for p in players:
        available = bool(getattr(p, "available", False))
        rows.append(SpeakerRow(
            player_id=p.player_id,
            name=getattr(p, "name", "") or p.player_id,
            is_group=_is_group(p),
            available=available,
            controlled=p.player_id == controlled_id,
            local=p.player_id == local_id,
            synced_to=getattr(p, "synced_to", None),
            members=tuple(getattr(p, "group_members", None) or ()),
            can_sync=available and p.player_id != controlled_id and p.player_id in groupable,
            playing=_playing(p),
        ))

    def band(r: SpeakerRow) -> int:
        return 0 if r.controlled else 1 if r.local else 2 if r.available else 3

    return sorted(rows, key=lambda r: (band(r), r.name.lower()))


async def speaker_action(client: Any, controlled_id: str | None, player_id: str, action: str,
                         members: Iterable[str] = ()) -> bool:
    """sync / unsync / transfer / create_group / edit_group / delete_group."""
    players = client.players
    members = list(members)
    try:
        if action == "sync" and controlled_id:
            await players.set_members(controlled_id, player_ids_to_add=[player_id])
        elif action == "unsync":
            target = players.get(player_id)
            leader = getattr(target, "synced_to", None) or controlled_id
            if not leader:
                return False
            await players.set_members(leader, player_ids_to_remove=[player_id])
        elif action == "transfer":
            source = players.get(controlled_id) if controlled_id else None
            if source is None or players.get(player_id) is None:
                return False
            src_queue = getattr(source, "active_source", None) or source.player_id
            await client.player_queues.transfer_queue(src_queue, player_id, auto_play=True)
        elif action == "create_group" and members:
            names = [getattr(players.get(m), "name", m) for m in members]
            await players.create_group_player(GROUP_PROVIDER, " + ".join(names), members)
        elif action == "edit_group":
            group = players.get(player_id)
            if group is None:
                return False
            old = list(getattr(group, "group_members", None) or [])
            add = [m for m in members if m not in old]
            remove = [m for m in old if m not in members]
            await players.set_members(player_id, player_ids_to_add=add or None,
                                      player_ids_to_remove=remove or None)
        elif action == "delete_group":
            await players.remove_group_player(player_id)
        else:
            return False
        return True
    except Exception as e:
        log.warning("speaker %s on %s failed: %s", action, player_id, e)
        return False
