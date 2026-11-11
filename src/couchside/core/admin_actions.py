"""What an admin can do from their phone: any queue change, shuffle, volume, which speaker
plays, and resetting or removing guests. Everything checks the admin flag first. The TV's
own controls (volume, shuffle, the controlled speaker) come in through `AdminHost`, so this
stays Qt-free and testable. Admins never act on other admins: only the host does."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from couchside.core import queue as queue_mod
from couchside.core.guest_actions import _queue, _upcoming
from couchside.core.guests import Guest, GuestError, GuestSession, NotAdmin

QUEUE_ACTIONS = ("play", "next", "up", "down", "remove")
SPEAKER_ACTIONS = ("control", "transfer")


@dataclass
class AdminHost:
    volume: Callable[[], int | None]
    set_volume: Callable[[int], Awaitable[None]]
    shuffle: Callable[[], bool | None]
    set_shuffle: Callable[[bool], Awaitable[None]]
    speakers: Callable[[], list[dict]]      # the TV's speaker rows
    control: Callable[[str], None]          # switch the speaker the TV (and guests) control
    transfer: Callable[[str], Awaitable[bool]]


def require_admin(guest: Guest) -> None:
    if not guest.admin:
        raise NotAdmin("Only an admin can do that")


async def admin_queue(client: Any, queue_id: str, session: GuestSession, guest: Guest,
                      item_id: str, action: str) -> None:
    require_admin(guest)
    if action not in QUEUE_ACTIONS:
        raise GuestError("Bad request")
    async with session.lock:
        current, items = await _queue(client, queue_id)
        if item_id not in [i.queue_item_id for i in _upcoming(current, items)]:
            raise GuestError("That song isn't waiting any more")
        if not await queue_mod.queue_action(client, queue_id, item_id, action):
            raise GuestError("That didn't work — try again")


async def admin_shuffle(host: AdminHost, guest: Guest, on: bool) -> None:
    require_admin(guest)
    await host.set_shuffle(bool(on))


async def admin_volume(host: AdminHost, guest: Guest, level: int | None = None,
                       step: int | None = None) -> None:
    require_admin(guest)
    if level is None:
        now = host.volume()
        if now is None or step is None:
            raise GuestError("Volume isn't available right now")
        level = now + step
    await host.set_volume(max(0, min(100, int(level))))


async def admin_speaker(host: AdminHost, guest: Guest, player_id: str, action: str) -> None:
    require_admin(guest)
    if action not in SPEAKER_ACTIONS:
        raise GuestError("Bad request")
    row = next((r for r in host.speakers() if r.get("playerId") == player_id), None)
    if row is None or not row.get("available"):
        raise GuestError("That speaker isn't available")
    if action == "control":
        host.control(player_id)
    elif not await host.transfer(player_id):
        raise GuestError("Couldn't move the music — try again")


async def admin_guest(session: GuestSession, actor: Guest, public_id: str, action: str) -> None:
    require_admin(actor)
    target = session.by_public_id(public_id)
    if target.admin:
        raise GuestError("Only the host can change another admin")
    if action == "reset":
        session.reset(public_id)
    elif action == "remove":
        session.remove(public_id)
    else:
        raise GuestError("Bad request")


def admin_info(session: GuestSession, host: AdminHost, actor: Guest) -> dict:
    r = session.rules
    return {
        "volume": host.volume(),
        "shuffle": host.shuffle(),
        "speakers": [{"playerId": s.get("playerId", ""), "name": s.get("name", ""),
                      "controlled": bool(s.get("controlled")), "available": bool(s.get("available")),
                      "playing": s.get("playing") or ""} for s in host.speakers()],
        "guests": [{"id": g.public_id, "name": g.name, "admin": g.admin, "you": g is actor,
                    "skipsLeft": max(0, r.skips - g.skips_used), "boostsLeft": max(0, r.boosts - g.boosts_used)}
                   for g in session.guests.values()],
    }
