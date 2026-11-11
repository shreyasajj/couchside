import asyncio

import pytest

QtCore = pytest.importorskip("PySide6.QtCore")

from couchside.core.playback import NowPlaying  # noqa: E402
from couchside.core.settings import AppSettings  # noqa: E402

PROXY = "http://ma:8095/imageproxy/abc?size=512&fmt=jpg"


@pytest.fixture
def ctl(tmp_path, monkeypatch, qt_app):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from couchside.ui.controller import AppController
    c = AppController(AppSettings())
    c.playback.now_playing = NowPlaying(
        "T", "A", "B", PROXY, "playing", duration=261, elapsed=12.5, elapsed_at=1000.0,
        shuffle=True, repeat="all", volume=40, palette_dark=(25, 28, 41), queue_id="q")
    return c


def test_progress_and_modes(ctl):
    assert ctl.hasDuration and ctl.duration == 261
    assert (ctl.positionBase, ctl.positionAt) == (12.5, 1000.0)
    assert ctl.shuffle and ctl.repeatMode == "all"
    assert ctl.volume == 40 and ctl.hasVolume
    assert ctl.backgroundColour == "#191c29"


def test_artwork_sizes(ctl):
    assert "size=1024" in ctl.artUrlLarge
    assert "size=1024" in ctl.artUrl  # 600 requested, proxy only serves 256/512/1024


def test_no_volume_control(ctl):
    from dataclasses import replace
    ctl.playback.now_playing = replace(ctl.playback.now_playing, volume=None, duration=None)
    assert ctl.volume == -1 and not ctl.hasVolume
    assert not ctl.hasDuration and ctl.duration == 0


def test_nothing_playing_defaults(ctl):
    ctl.playback.now_playing = None
    assert ctl.artUrl == "" and ctl.artUrlLarge == ""
    assert ctl.repeatMode == "off" and not ctl.shuffle and not ctl.hasVolume
    assert ctl.backgroundColour == "#0d0b1a"


def test_format_time_slot(ctl):
    assert ctl.formatTime(261) == "4:21"


async def test_slots_schedule_playback_commands(ctl, monkeypatch):
    calls = []

    def stub(name):
        async def f(*args):
            calls.append((name, *args))
        return f

    for name in ("cycle_repeat", "toggle_shuffle", "set_volume", "step_volume"):
        monkeypatch.setattr(ctl.playback, name, stub(name))
    ctl.cycleRepeat()
    ctl.toggleShuffle()
    ctl.setVolume(55)
    ctl.volumeUp()
    ctl.volumeDown()
    await asyncio.sleep(0)
    assert calls == [("cycle_repeat",), ("toggle_shuffle",), ("set_volume", 55),
                     ("step_volume", 5), ("step_volume", -5)]
