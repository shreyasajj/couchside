"""`couchside` entry point: Qt + asyncio (qasync) + QML/Kirigami."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

APP_ID = "io.github.shreyasajj.Couchside"


async def _ensure_sendspin(settings) -> None:
    from PySide6.QtCore import QProcess

    from couchside.core.settings import save_settings
    from couchside.sendspin.autostart import request_autostart

    # Single-instance via file lock inside couchside-sendspin, so this is safe to repeat.
    QProcess.startDetached("couchside-sendspin", [])
    if not settings.autostart_requested:
        granted = await request_autostart(True)
        logging.getLogger(__name__).info("Background autostart granted: %s", granted)
        settings.autostart_requested = True
        save_settings(settings)


def main() -> int:
    logging.basicConfig(level=os.environ.get("COUCHSIDE_LOG", "INFO"))
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuickControls2 import QQuickStyle
    import qasync

    from couchside.core.settings import load_settings
    from couchside.core.tasks import keep_running
    from couchside.sendspin.pairing import tail_log
    from couchside.sendspin.runner import log_path
    from couchside.ui.controller import AppController

    app = QGuiApplication(sys.argv)
    app.setApplicationName("Couchside")
    app.setOrganizationDomain("github.io")
    app.setDesktopFileName(APP_ID)
    if not os.environ.get("QT_QUICK_CONTROLS_STYLE"):
        QQuickStyle.setStyle("org.kde.desktop")

    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    settings = load_settings()
    controller = AppController(settings)

    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("app", controller)
    engine.load(str(Path(__file__).parent / "qml" / "Main.qml"))
    if not engine.rootObjects():
        return 1

    closing = asyncio.Event()
    app.aboutToQuit.connect(closing.set)

    async def run() -> None:
        tasks = [
            asyncio.ensure_future(keep_running(controller.conn.run, "MA connection")),
            asyncio.ensure_future(keep_running(
                lambda: tail_log(log_path(), controller.on_pairing_event), "pairing log")),
            asyncio.ensure_future(keep_running(
                lambda: _ensure_sendspin(settings), "Sendspin start", delay=30)),
            asyncio.ensure_future(keep_running(controller.check_versions_forever, "version check", delay=600)),
            asyncio.ensure_future(controller.start_update_monitor()),
        ]
        await closing.wait()
        await controller.conn.stop()
        await controller.close()
        for t in tasks:
            t.cancel()

    with loop:
        loop.run_until_complete(run())
    return 0


if __name__ == "__main__":
    sys.exit(main())
