"""Guest mode: the session (token, guests, who added what) and its rules. Qt-free.

Rules (host settings): skips and boosts per guest, songs a guest may have waiting in the
queue at once, and an optional cooldown between adds. A skip ends whatever is playing,
whoever added it. A boost moves one of the guest's own waiting songs to play next (the
newest boost wins, because each one is moved right after the current song).

Admins (granted by the host: a one-time code or promotion) have no limits; admin status
belongs to the device and lasts until revoked or guest mode ends.
"""

from __future__ import annotations

import asyncio
import re
import secrets
from dataclasses import dataclass, field
from typing import Iterable

_DEVICE_ID = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
MAX_NAME = 24
MAX_GUESTS = 50
CODE_TTL = 600.0   # seconds an admin code stays valid
CODE_TRIES = 20            # wrong tries (all phones together) before the code is cancelled
CODE_TRIES_PER_PHONE = 3   # wrong tries one phone gets per code (so one guest can't burn it)
_WRONG_CODE = "That code isn't right — ask the host for a new one"


class GuestError(Exception):
    """A rule said no; the message is shown to the guest as is."""


class NotAdmin(GuestError):
    """An admin-only action from a guest who isn't (or is no longer) an admin."""


@dataclass
class GuestRules:
    skips: int = 3
    boosts: int = 2
    max_waiting: int = 3
    cooldown: float = 0.0  # seconds between a guest's adds (0 = off)


@dataclass
class Guest:
    device_id: str
    name: str
    skips_used: int = 0
    boosts_used: int = 0
    last_add: float | None = None
    admin: bool = False
    # shown in lists; the device id is the phone's secret and never leaves the server
    public_id: str = field(default_factory=lambda: secrets.token_urlsafe(9))
    # songs this guest's own searches returned: the only URIs they may add
    offered: set[str] = field(default_factory=set)

    def offer(self, uris) -> None:
        self.offered.update(uris)
        if len(self.offered) > 500:  # keep it bounded; the newest search matters
            self.offered = set(list(self.offered)[-500:])


@dataclass
class GuestSession:
    rules: GuestRules = field(default_factory=GuestRules)
    token: str = ""
    guests: dict[str, Guest] = field(default_factory=dict)
    _credits: dict[str, str] = field(default_factory=dict)  # queue item id -> device id
    _lock: asyncio.Lock | None = None
    admin_code: str | None = None
    code_expires: float = 0.0
    code_cancelled: bool = False   # the last code was cancelled by wrong tries
    _code_misses: int = 0
    _phone_misses: dict[str, int] = field(default_factory=dict)
    _banned: set[str] = field(default_factory=set)
    _former: dict[str, str] = field(default_factory=dict)  # removed guests' names (credits)

    def __post_init__(self) -> None:
        if not self.token:
            self.new_token()

    @property
    def lock(self) -> asyncio.Lock:
        """Serialises guest actions: a rule check and the change it allows happen together,
        so parallel requests can't slip past the limits."""
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    def new_token(self) -> None:
        """New QR link; old links, guests and credits are forgotten."""
        self.token = secrets.token_urlsafe(12)[:16]
        self.guests.clear()
        self._credits.clear()
        self._banned.clear()
        self._former.clear()
        self.cancel_admin_code()

    # --- guests ---------------------------------------------------------------------
    def join(self, device_id: str, name: str) -> Guest:
        if not isinstance(device_id, str) or not _DEVICE_ID.match(device_id):
            raise GuestError("This phone couldn't be recognised — reload the page")
        if device_id in self._banned:
            raise GuestError("The host removed you from this party")
        name = (name or "").strip() if isinstance(name, str) else ""
        if not name or len(name) > MAX_NAME or any(not c.isprintable() for c in name):
            raise GuestError(f"Enter a name (up to {MAX_NAME} characters)")
        guest = self.guests.get(device_id)
        if guest is None:
            if len(self.guests) >= MAX_GUESTS:
                raise GuestError("This party is full — ask the host")
            guest = self.guests[device_id] = Guest(device_id, name)
        else:
            guest.name = name
        return guest

    def guest(self, device_id: str) -> Guest:
        guest = self.guests.get(device_id) if isinstance(device_id, str) else None
        if guest is None:
            raise GuestError("Enter your name first")
        return guest

    def by_public_id(self, public_id: str) -> Guest:
        for g in self.guests.values():
            if isinstance(public_id, str) and g.public_id == public_id:
                return g
        raise GuestError("That guest has left")

    # --- admins -----------------------------------------------------------------------
    def new_admin_code(self, now: float) -> str:
        self.admin_code = f"{secrets.randbelow(1_000_000):06d}"
        self.code_expires = now + CODE_TTL
        self.code_cancelled = False
        self._code_misses = 0
        self._phone_misses = {}
        return self.admin_code

    def cancel_admin_code(self) -> None:
        self.admin_code = None
        self._code_misses = 0
        self._phone_misses = {}

    def is_banned(self, device_id: str) -> bool:
        return device_id in self._banned

    def redeem_code(self, guest: Guest, code, now: float) -> None:
        """One error text whether or not a code is showing, so guests can't tell."""
        if self.admin_code is not None and now > self.code_expires:
            self.cancel_admin_code()
        if self.admin_code is None or self._phone_misses.get(guest.device_id, 0) >= CODE_TRIES_PER_PHONE:
            raise GuestError(_WRONG_CODE)
        if not isinstance(code, str) or not secrets.compare_digest(code.strip().encode(),
                                                                   self.admin_code.encode()):
            self._phone_misses[guest.device_id] = self._phone_misses.get(guest.device_id, 0) + 1
            self._code_misses += 1
            if self._code_misses >= CODE_TRIES:
                self.cancel_admin_code()
                self.code_cancelled = True
            raise GuestError(_WRONG_CODE)
        guest.admin = True
        self.cancel_admin_code()

    def promote(self, public_id: str) -> Guest:
        g = self.by_public_id(public_id)
        g.admin = True
        return g

    def revoke(self, public_id: str) -> Guest:
        g = self.by_public_id(public_id)
        g.admin = False
        return g

    def reset(self, public_id: str) -> Guest:
        g = self.by_public_id(public_id)
        g.skips_used = g.boosts_used = 0
        g.last_add = None
        return g

    def remove(self, public_id: str) -> Guest:
        """Forget the guest and keep them out until guest mode restarts; their songs stay
        in the queue with their name."""
        g = self.by_public_id(public_id)
        del self.guests[g.device_id]
        self._banned.add(g.device_id)
        self._former[g.device_id] = g.name
        return g

    # --- rules ----------------------------------------------------------------------
    def waiting_count(self, guest: Guest, upcoming_ids: Iterable[str]) -> int:
        return sum(1 for i in upcoming_ids if self._credits.get(i) == guest.device_id)

    def check_add(self, guest: Guest, upcoming_ids: Iterable[str], now: float) -> None:
        r = self.rules
        if guest.admin:
            return
        if self.waiting_count(guest, upcoming_ids) >= r.max_waiting:
            raise GuestError(f"You already have {r.max_waiting} songs waiting — "
                             "add more once one has played")
        if r.cooldown and guest.last_add is not None and now - guest.last_add < r.cooldown:
            wait = int(r.cooldown - (now - guest.last_add) + 0.999)
            raise GuestError(f"Wait {wait} s before adding another song")

    def note_added(self, guest: Guest, item_id: str | None, now: float) -> None:
        guest.last_add = now
        if item_id:
            self._credits[item_id] = guest.device_id

    def use_skip(self, guest: Guest) -> None:
        if guest.admin:
            return
        if guest.skips_used >= self.rules.skips:
            raise GuestError("No skips left")
        guest.skips_used += 1

    def use_boost(self, guest: Guest, item_id: str, upcoming_ids: Iterable[str]) -> None:
        if self._credits.get(item_id) != guest.device_id:
            raise GuestError("You can only boost your own songs")
        if item_id not in list(upcoming_ids):
            raise GuestError("That song is already playing or not waiting any more")
        if guest.admin:
            return
        if guest.boosts_used >= self.rules.boosts:
            raise GuestError("No boosts left")
        guest.boosts_used += 1

    # --- credits --------------------------------------------------------------------
    def added_by(self, item_id: str | None) -> str | None:
        device = self._credits.get(item_id or "")
        guest = self.guests.get(device) if device else None
        return guest.name if guest else self._former.get(device) if device else None

    def owns(self, guest: Guest, item_id: str) -> bool:
        return self._credits.get(item_id) == guest.device_id

    def remaining(self, guest: Guest, upcoming_ids: Iterable[str]) -> dict:
        return {"skips": max(0, self.rules.skips - guest.skips_used),
                "boosts": max(0, self.rules.boosts - guest.boosts_used),
                "waiting": self.waiting_count(guest, upcoming_ids),
                "maxWaiting": self.rules.max_waiting}
