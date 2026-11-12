"""Self-update through the Flatpak portal (org.freedesktop.portal.Flatpak), from inside
the sandbox: an update monitor tells us when the remote has a newer build, Update installs
it, and Spawn with the latest-version flag starts the new build. Qt-free (dbus-next)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable

log = logging.getLogger(__name__)

PORTAL = "org.freedesktop.portal.Flatpak"
PATH = "/org/freedesktop/portal/Flatpak"
PORTAL_IFACE = "org.freedesktop.portal.Flatpak"
MONITOR_IFACE = "org.freedesktop.portal.Flatpak.UpdateMonitor"
SPAWN_LATEST_VERSION = 2
_STATUS = {0: "running", 1: "empty", 2: "done", 3: "failed"}


@dataclass(frozen=True)
class Progress:
    status: str      # running / empty (nothing to do) / done / failed
    percent: int
    error: str


def in_flatpak() -> bool:
    return Path("/.flatpak-info").exists()


async def _session_bus():
    from dbus_next.aio import MessageBus
    return await MessageBus().connect()


def _plain(info: Any) -> dict:
    return {k: getattr(v, "value", v) for k, v in (info or {}).items()}


def _progress(info: dict) -> Progress:
    status = _STATUS.get(info.get("status", 0), "running")
    n_ops, op, pct = info.get("n_ops", 0), info.get("op", 0), info.get("progress", 0)
    percent = int((op * 100 + pct) / n_ops) if n_ops else int(pct)
    if status == "failed":
        percent = 0
    return Progress(status, max(0, min(100, percent)),
                    str(info.get("error_message") or info.get("error") or ""))


class PortalUpdater:
    def __init__(self, bus_factory: Callable[[], Awaitable[Any]] = _session_bus):
        self._bus_factory = bus_factory
        self._bus = None
        self._monitor: str | None = None

    async def _call(self, path: str, iface: str, member: str, signature: str = "", body=(),
                    destination: str = PORTAL):
        from dbus_next import Message, MessageType

        reply = await self._bus.call(Message(destination=destination, path=path, interface=iface,
                                             member=member, signature=signature, body=list(body)))
        if reply is None or reply.message_type == MessageType.ERROR:
            raise RuntimeError(f"{member}: {getattr(reply, 'error_name', 'no reply')} "
                               f"{(reply.body if reply else '')}")
        return reply.body

    async def start(self, on_available: Callable[[dict], None],
                    on_progress: Callable[[Progress], None]) -> bool:
        """Watch for updates. False when there is no portal (not in a Flatpak, no bus)."""
        try:
            self._bus = await self._bus_factory()
            (self._monitor,) = await self._call(PATH, PORTAL_IFACE, "CreateUpdateMonitor", "a{sv}", [{}])
            rule = f"type='signal',interface='{MONITOR_IFACE}',path='{self._monitor}'"
            await self._call("/org/freedesktop/DBus", "org.freedesktop.DBus", "AddMatch", "s", [rule],
                             destination="org.freedesktop.DBus")
        except Exception as e:
            log.info("no Flatpak update portal: %s", e)
            self._monitor = None
            return False

        def handler(msg):
            if msg.interface != MONITOR_IFACE or msg.path != self._monitor:
                return
            info = _plain(msg.body[0] if msg.body else {})
            if msg.member == "UpdateAvailable":
                on_available(info)
            elif msg.member == "Progress":
                on_progress(_progress(info))
        self._bus.add_message_handler(handler)
        return True

    async def update(self) -> bool:
        if self._monitor is None:
            return False
        await self._call(self._monitor, MONITOR_IFACE, "Update", "sa{sv}", ["", {}])
        return True

    async def spawn_latest(self, argv: list[str], env: dict[str, str] | None = None) -> int:
        """Start `argv` in a new sandbox of the newest installed build of this app; it
        outlives us (the portal doesn't tie it to our bus name)."""
        if self._bus is None:
            self._bus = await self._bus_factory()
        (pid,) = await self._call(PATH, PORTAL_IFACE, "Spawn", "ayaaya{uh}a{ss}ua{sv}",
                                  [b"/\0", [a.encode() + b"\0" for a in argv], {}, dict(env or {}),
                                   SPAWN_LATEST_VERSION, {}])
        return pid

    async def close(self) -> None:
        if self._bus is not None:
            try:
                if self._monitor:
                    await self._call(self._monitor, MONITOR_IFACE, "Close")
            except Exception:
                pass
            self._bus.disconnect()
            self._bus = None
