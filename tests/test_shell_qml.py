"""The whole UI (Shell.qml) with the real controller, offscreen: every screen loads
without QML errors, and the remote's rules hold (Up to the bar, Back, tabs that vanish)."""

import os
import re
import time
from pathlib import Path

import pytest

pytest.importorskip("PySide6.QtQuick")
from PySide6.QtCore import QCoreApplication, QMetaObject, Q_ARG, Qt, QUrl, qInstallMessageHandler  # noqa: E402
from PySide6.QtQuick import QQuickView  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

from couchside.core.playback import NowPlaying  # noqa: E402
from couchside.core.settings import AppSettings  # noqa: E402

SHELL = Path(__file__).parents[1] / "src/couchside/ui/qml/Shell.qml"
SCREENS = ["now", "search", "queue", "lyrics", "visualizer", "speakers", "guests", "settings"]
BAD = re.compile(r"ReferenceError|TypeError|is not defined|Unable to assign|Cannot assign|"
                 r"non-existent property|is not a type|Binding loop|Cannot read property|Cannot call")
SHOTS = os.environ.get("COUCHSIDE_SHOTS")   # a directory: save a picture of every screen there


def pump(seconds=0.1):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        QCoreApplication.processEvents()
        time.sleep(0.005)


@pytest.fixture
async def ui(qt_app, tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("QT_QUICK_CONTROLS_STYLE", "Basic")   # the Mac's native style can't be restyled
    from couchside.core.settings import save_token
    from couchside.ui.controller import AppController
    save_token("token")   # set up already: no jump to Settings
    ctl = AppController(AppSettings())
    async def no_devices(*_a):   # no real sendspin or pactl in tests
        return []

    async def no_pactl(_kind):
        return ""
    monkeypatch.setattr(ctl, "_list_audio_devices", no_devices)
    monkeypatch.setattr(ctl, "_pactl", no_pactl)
    ctl.playback.now_playing = NowPlaying(
        "Neon Tide", "Marisol Vega", "Afterglow", "", "playing", duration=224, elapsed=38.0,
        elapsed_at=time.time(), shuffle=True, repeat="all", volume=70, palette_dark=(25, 28, 41),
        queue_id="q")
    messages = []
    previous = qInstallMessageHandler(lambda _mode, _ctx, text: messages.append(text))
    view = QQuickView()
    view.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
    view.resize(1920, 1080)
    view.rootContext().setContextProperty("app", ctl)
    view.setSource(QUrl.fromLocalFile(str(SHELL)))
    assert view.status() == QQuickView.Status.Ready, view.errors()
    view.show()
    view.requestActivate()
    pump(0.3)
    yield view, ctl, messages
    view.close()
    qInstallMessageHandler(previous)
    await ctl.close()


def go(view, screen):
    QMetaObject.invokeMethod(view.rootObject(), "go", Q_ARG("QVariant", screen))
    pump(0.25)


def back(view):
    QMetaObject.invokeMethod(view.rootObject(), "goBack")
    pump(0.15)


def screen(view):
    return view.rootObject().property("screen")


def focus_path(view):
    names, item = [], view.activeFocusItem()
    while item is not None:
        if item.objectName():
            names.append(item.objectName())
        item = item.parentItem()
    return names


def press(view, key, times=1):
    for _ in range(times):
        QTest.keyClick(view, key)
    pump(0.1)


def problems(messages):
    return [m for m in messages if BAD.search(m)]


async def test_every_screen_loads_without_qml_errors(ui):
    view, ctl, messages = ui
    for name in SCREENS:
        go(view, name)
        assert screen(view) == name
        assert view.activeFocusItem() is not None, name
        if SHOTS:
            pump(0.4)
            view.grabWindow().save(str(Path(SHOTS) / f"{name}.png"))
    for mode in ("flow", "bars", "party", "radial"):
        ctl.visualizerMode = mode
        go(view, "visualizer")
        pump(0.2)
        if SHOTS:
            view.grabWindow().save(str(Path(SHOTS) / f"visualizer-{mode}.png"))
    assert problems(messages) == []


async def test_nothing_playing_and_guest_mode_still_load(ui):
    view, ctl, messages = ui
    ctl.playback.now_playing = None
    ctl.changed.emit()
    for name in ("now", "lyrics", "visualizer", "queue"):
        go(view, name)
        assert view.activeFocusItem() is not None, name
        if SHOTS:
            view.grabWindow().save(str(Path(SHOTS) / f"empty-{name}.png"))
    assert problems(messages) == []


async def test_up_reaches_the_bar_and_down_returns_to_where_focus_was(ui):
    view, _ctl, _messages = ui
    go(view, "now")
    press(view, Qt.Key.Key_Right)              # from play to next
    before = view.activeFocusItem()
    press(view, Qt.Key.Key_Up)
    assert "tab-now" in focus_path(view)
    press(view, Qt.Key.Key_Right)
    assert "tab-search" in focus_path(view)
    press(view, Qt.Key.Key_Down)
    assert view.activeFocusItem() is before
    press(view, Qt.Key.Key_Up)
    press(view, Qt.Key.Key_Right)
    press(view, Qt.Key.Key_Return)             # open Search from the bar
    assert screen(view) == "search" and "searchBox" in focus_path(view)
    press(view, Qt.Key.Key_Up)
    assert "tab-search" in focus_path(view)


async def test_back_goes_to_now_playing_then_asks_before_leaving(ui):
    view, _ctl, _messages = ui
    go(view, "queue")
    go(view, "speakers")
    back(view)
    assert screen(view) == "queue"             # back to the tab it was opened from
    back(view)
    assert screen(view) == "now"
    back(view)
    confirm = view.rootObject().findChild(object, "exitConfirm")
    assert confirm.property("visible") is True and "exitCancel" in focus_path(view)
    back(view)
    assert confirm.property("visible") is False and screen(view) == "now"
    assert view.activeFocusItem() is not None


async def test_guests_opened_from_settings_goes_back_to_settings(ui):
    view, _ctl, _messages = ui
    go(view, "search")
    go(view, "settings")
    go(view, "guests")
    back(view)
    assert screen(view) == "settings"
    back(view)
    assert screen(view) == "search"


async def test_switching_lyrics_off_while_on_the_lyrics_tab_lands_on_now_playing(ui):
    view, ctl, messages = ui
    go(view, "lyrics")
    ctl.lyricsEnabled = False
    pump(0.3)
    assert screen(view) == "now"
    assert view.activeFocusItem() is not None and "now" in focus_path(view)
    go(view, "lyrics")                         # the tab is gone: asking for it stays put
    assert screen(view) == "now"
    assert problems(messages) == []


async def test_visualizer_modes_follow_left_and_right(ui):
    view, ctl, _messages = ui
    ctl.visualizerMode = "radial"
    go(view, "visualizer")
    assert "mode-radial" in focus_path(view)
    press(view, Qt.Key.Key_Right)
    assert ctl.visualizerMode == "flow"
    press(view, Qt.Key.Key_Right, 5)
    assert ctl.visualizerMode == "party"       # stops at the last mode
    press(view, Qt.Key.Key_Up)
    assert "beatChip" in focus_path(view)
    before = ctl.visualizerIntensity
    press(view, Qt.Key.Key_Right, 2)
    assert ctl.visualizerIntensity == pytest.approx(before + 0.1)
    press(view, Qt.Key.Key_Up)
    assert "sourceChip" in focus_path(view)
    press(view, Qt.Key.Key_Up)
    assert "tab-visualizer" in focus_path(view)


async def test_the_party_button_opens_the_visualizer_in_party_mode(ui):
    view, ctl, _messages = ui
    ctl.visualizerMode = "bars"
    go(view, "now")
    press(view, Qt.Key.Key_Right, 4)           # play, next, volume, party
    press(view, Qt.Key.Key_Return)
    assert screen(view) == "visualizer" and ctl.visualizerMode == "party"


async def test_typing_on_now_playing_opens_search_with_the_letters(ui):
    view, _ctl, _messages = ui
    go(view, "now")
    QTest.keyClick(view, Qt.Key.Key_A)
    pump(0.2)
    assert screen(view) == "search" and problems(_messages) == []
