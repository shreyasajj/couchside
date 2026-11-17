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
SCREENS = ["now", "search", "queue", "visualizer", "speakers", "guests", "settings"]
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
    for mode in ("flow", "bars", "edge", "party", "radial"):
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
    for name in ("now", "visualizer", "queue"):
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


def named(view, name):
    return view.rootObject().findChild(object, name)


async def test_the_lyrics_button_swaps_the_cover_for_the_words_over_the_visualizer(ui):
    view, ctl, messages = ui
    go(view, "now")
    words = named(view, "words")
    assert words.property("visible") is False and ctl.vizVisible is False
    press(view, Qt.Key.Key_Right, 3)           # play, next, volume, lyrics
    assert "lyricsButton" in focus_path(view)
    press(view, Qt.Key.Key_Return)
    pump(0.4)
    assert ctl.lyricsShown is True and words.property("visible") is True
    assert ctl.vizVisible is True              # the visualizer listens behind the words
    assert "lyricsButton" in focus_path(view)  # focus stays on the button
    if SHOTS:
        for mode in ("edge", "bars", "radial"):
            ctl.visualizerMode = mode
            pump(0.3)
            view.grabWindow().save(str(Path(SHOTS) / f"now-lyrics-{mode}.png"))
    ctl.lyricsVisualizer = False
    pump(0.2)
    assert ctl.vizVisible is False and words.property("visible") is True
    ctl.lyricsVisualizer = True
    go(view, "queue")
    assert ctl.vizVisible is False             # only while Now Playing is in front
    go(view, "now")
    press(view, Qt.Key.Key_Right, 3)
    press(view, Qt.Key.Key_Return)
    pump(0.2)
    assert ctl.lyricsShown is False and words.property("visible") is False
    assert problems(messages) == []


async def test_switching_lyrics_off_hides_the_button_and_the_words(ui):
    view, ctl, messages = ui
    ctl.lyricsShown = True
    go(view, "now")
    press(view, Qt.Key.Key_Right, 3)
    assert "lyricsButton" in focus_path(view)
    ctl.lyricsEnabled = False
    pump(0.3)
    assert named(view, "words").property("visible") is False
    assert view.activeFocusItem() is not None and "lyricsButton" not in focus_path(view)
    go(view, "lyrics")                         # no such screen any more: stays put
    assert screen(view) == "now"
    assert problems(messages) == []


async def test_search_shows_rows_of_cards(ui):
    view, ctl, messages = ui
    from couchside.core.library import MediaCard
    cards = [MediaCard(key=f"x://t/{i}", kind="track", title=f"Song {i}", subtitle="Someone",
                       image_url=None, uri=f"x://t/{i}") for i in range(4)]
    go(view, "search")
    ctl._set_library([("Tracks", cards), ("Albums", cards[:2])])
    pump(0.3)
    results = named(view, "results")
    assert results.property("count") == 2      # one row per kind
    press(view, Qt.Key.Key_Down)               # from the box to the first card
    first = view.activeFocusItem()
    assert "results" in focus_path(view)
    press(view, Qt.Key.Key_Right)
    assert view.activeFocusItem() is not first and "results" in focus_path(view)
    press(view, Qt.Key.Key_Down)
    assert results.property("currentIndex") == 1
    press(view, Qt.Key.Key_Up, 2)
    assert "searchBox" in focus_path(view)
    if SHOTS:
        view.grabWindow().save(str(Path(SHOTS) / "search-cards.png"))
    assert problems(messages) == []


async def test_visualizer_modes_follow_left_and_right(ui):
    view, ctl, _messages = ui
    ctl.visualizerMode = "radial"
    go(view, "visualizer")
    assert "mode-radial" in focus_path(view)
    press(view, Qt.Key.Key_Right)
    assert ctl.visualizerMode == "flow"
    press(view, Qt.Key.Key_Right, 2)
    assert ctl.visualizerMode == "edge"
    press(view, Qt.Key.Key_Right, 5)
    assert ctl.visualizerMode == "party"       # stops at the last mode
    press(view, Qt.Key.Key_Up)
    assert "coloursChip" in focus_path(view)
    press(view, Qt.Key.Key_Up)
    assert "beatChip" in focus_path(view)
    before = ctl.visualizerIntensity
    press(view, Qt.Key.Key_Right, 2)
    assert ctl.visualizerIntensity == pytest.approx(before + 0.1)
    press(view, Qt.Key.Key_Up)
    assert "sourceChip" in focus_path(view)
    press(view, Qt.Key.Key_Up)
    assert "tab-now" in focus_path(view)       # no tab of its own: the bar opens on the first
    back(view)
    back(view)
    assert screen(view) == "now"               # Back returns to where it was opened


async def test_the_visualizer_button_opens_the_visualizer(ui):
    view, ctl, _messages = ui
    ctl.visualizerMode = "bars"
    go(view, "now")
    press(view, Qt.Key.Key_Right, 4)           # play, next, volume, lyrics, visualizer
    assert "visualizerButton" in focus_path(view)
    press(view, Qt.Key.Key_Return)
    assert screen(view) == "visualizer" and ctl.visualizerMode == "bars"


async def test_typing_on_now_playing_opens_search_with_the_letters(ui):
    view, _ctl, _messages = ui
    go(view, "now")
    QTest.keyClick(view, Qt.Key.Key_A)
    pump(0.2)
    assert screen(view) == "search" and problems(_messages) == []
