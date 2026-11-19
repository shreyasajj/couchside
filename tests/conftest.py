import asyncio
import os
import socket
import time
from types import SimpleNamespace as NS

import pytest


def pytest_sessionfinish(session, exitstatus):
    """With COUCHSIDE_NO_SKIPS set (CI), a skipped test fails the run: the QML tests skip
    themselves when QtQuick is missing, and CI must not pass without them."""
    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    skipped = reporter.stats.get("skipped", []) if reporter else []
    if os.environ.get("COUCHSIDE_NO_SKIPS") and skipped and session.exitstatus == 0:
        reporter.write_line(f"{len(skipped)} test(s) skipped; COUCHSIDE_NO_SKIPS makes that a failure",
                            red=True)
        session.exitstatus = 1


@pytest.fixture(scope="session")
def qt_app():
    """One QGuiApplication for every Qt test (offscreen, so it runs headless in CI)."""
    QtGui = pytest.importorskip("PySide6.QtGui")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QtGui.QGuiApplication.instance() or QtGui.QGuiApplication([])


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def until(cond, timeout: float = 3.0, what: str = "") -> None:
    """Run Qt and asyncio together until `cond()` is true (fails after `timeout`)."""
    from PySide6.QtCore import QCoreApplication

    end = time.monotonic() + timeout
    while True:
        QCoreApplication.processEvents()
        if cond():
            return
        if time.monotonic() > end:
            raise AssertionError(f"timed out waiting for {what or cond}")
        await asyncio.sleep(0.01)


async def settle(seconds: float = 0.1) -> None:
    """Let spawned tasks and Qt events run for a moment."""
    from PySide6.QtCore import QCoreApplication

    end = time.monotonic() + seconds
    while time.monotonic() < end:
        QCoreApplication.processEvents()
        await asyncio.sleep(0.01)


class NoLyrics:
    """No network in tests: the lyrics lookup finds nothing (or what it is given)."""

    def __init__(self, lines=None):
        self.lines, self.asked = lines, []

    async def get(self, info):
        self.asked.append(info.title)
        return self.lines


@pytest.fixture
async def house(qt_app, tmp_path, monkeypatch):
    """The real controller and connection on a fake Music Assistant (tests/fake_ma.py):
    connected, with this TV's player found. Settings live in tmp_path."""
    from tests.fake_ma import TV, FakeMA

    for var in ("XDG_CONFIG_HOME", "XDG_STATE_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME"):
        monkeypatch.setenv(var, str(tmp_path / var.lower()))
    from couchside.core.connection import ConnState
    from couchside.core.settings import AppSettings, save_token
    from couchside.ui.controller import AppController

    save_token("token")
    settings = AppSettings(server_url="http://ma.test:8095", guest_port=free_port())
    ma = FakeMA.house()
    ctl = AppController(settings)
    ctl._client_id = TV
    ctl._lyrics_fetcher = NoLyrics()

    async def no_devices(*_a):
        return []

    async def no_pactl(_kind):
        return ""
    monkeypatch.setattr(ctl, "_list_audio_devices", no_devices)
    monkeypatch.setattr(ctl, "_pactl", no_pactl)

    async def quick_sleep(_s):
        await asyncio.sleep(0.02)
    ctl.conn._factory = lambda url, token: ma
    ctl.conn._sleep = quick_sleep
    runner = asyncio.ensure_future(ctl.conn.run())
    await until(lambda: ctl.conn.state is ConnState.CONNECTED and ctl.playback.active_player_id == TV,
                what="connected to the fake Music Assistant")
    yield NS(ctl=ctl, ma=ma, settings=settings, tmp=tmp_path)
    await ctl.conn.stop()
    try:
        await asyncio.wait_for(runner, 2)
    except (TimeoutError, asyncio.CancelledError):
        runner.cancel()
    await ctl.close()
