"""Ask the Background portal to start `couchside-sendspin` at login.

Flathub-friendly: no host access needed. Exercised live (needs a session bus
and xdg-desktop-portal), not in unit tests.
"""

from __future__ import annotations

import asyncio
import logging
import secrets

log = logging.getLogger(__name__)

PORTAL_SERVICE = "org.freedesktop.portal.Desktop"
PORTAL_PATH = "/org/freedesktop/portal/desktop"
REASON = "Keep this TV available as a Music Assistant speaker"


async def request_autostart(enable: bool = True, timeout: float = 120.0) -> bool:
    from PySide6.QtCore import SLOT, QObject, Slot
    from PySide6.QtDBus import QDBusConnection, QDBusInterface, QDBusMessage

    bus = QDBusConnection.sessionBus()
    if not bus.isConnected():
        log.warning("No session bus; cannot request autostart")
        return False

    token = "couchside_" + secrets.token_hex(6)
    sender = bus.baseService().lstrip(":").replace(".", "_")
    request_path = f"{PORTAL_PATH}/request/{sender}/{token}"
    loop = asyncio.get_running_loop()
    result: asyncio.Future[bool] = loop.create_future()

    class Receiver(QObject):
        @Slot(QDBusMessage)
        def on_response(self, msg: QDBusMessage) -> None:
            args = msg.arguments()
            # Response code 0 = granted. The results map arrives as an opaque
            # QDBusArgument in PySide6, so the code is the reliable signal.
            code = int(args[0]) if args else 2
            granted = code == 0
            if not result.done():
                result.set_result(granted)

    receiver = Receiver()
    bus.connect(PORTAL_SERVICE, request_path, "org.freedesktop.portal.Request", "Response",
                receiver, SLOT("on_response(QDBusMessage)"))

    iface = QDBusInterface(PORTAL_SERVICE, PORTAL_PATH, "org.freedesktop.portal.Background", bus)
    options = {
        "handle_token": token,
        "reason": REASON,
        "autostart": enable,
        "commandline": ["couchside-sendspin"],
        "dbus-activatable": False,
    }
    reply = iface.call("RequestBackground", "", options)
    if reply.type() == QDBusMessage.MessageType.ErrorMessage:
        log.warning("RequestBackground failed: %s", reply.errorMessage())
        return False
    try:
        return await asyncio.wait_for(result, timeout)
    except asyncio.TimeoutError:
        log.warning("Background portal did not answer")
        return False
    finally:
        bus.disconnect(PORTAL_SERVICE, request_path, "org.freedesktop.portal.Request",
                       "Response", receiver, SLOT("on_response(QDBusMessage)"))
