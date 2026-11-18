"""The whole UI (Shell.qml) with the real controller, offscreen: every screen loads
without QML errors, and the remote's rules hold (Up to the bar, Back, tabs that vanish)."""

import asyncio
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
SCREENS = ["now", "search", "queue", "visualizer", "speakers", "guests", "settings", "logs"]
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
    ctl.visualizerEdges = True                 # edge lights over the other pictures
    for mode in ("radial", "bars"):
        ctl.visualizerMode = mode
        pump(0.3)
        if SHOTS:
            view.grabWindow().save(str(Path(SHOTS) / f"visualizer-{mode}-edges.png"))
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


def give_words_and_a_queue(ctl):
    from couchside.core.lyrics import LyricLine
    ctl._raw_lyrics = [LyricLine(float(t), f"Line number {t}") for t in range(0, 200, 4)]
    ctl._rebuild_lyrics()
    ctl._queue_rows = [{"itemId": str(i), "title": f"Song {i}", "subtitle": "Someone", "imageUrl": "",
                        "duration": 200, "current": i == 0, "addedBy": "Priya" if i == 1 else ""}
                       for i in range(5)]
    ctl.queueChanged.emit()
    pump(0.2)


def box(item):
    from PySide6.QtCore import QPointF
    top_left = item.mapToScene(QPointF(0, 0))
    return top_left.x(), top_left.y(), top_left.x() + item.width(), top_left.y() + item.height()


def credit_in(card):
    """The "Added by" line under Up Next's first song ("" if none shows)."""
    def walk(item):
        for child in item.childItems():
            if child.objectName() == "upNextCredit" and child.property("visible"):
                yield child.property("text")
            yield from walk(child)
    return next(walk(card), "")


def apart(a, b):
    """The two items' boxes on screen don't overlap."""
    ax0, ay0, ax1, ay1 = box(a)
    bx0, by0, bx1, by1 = box(b)
    return ax1 <= bx0 or bx1 <= ax0 or ay1 <= by0 or by1 <= ay0


async def test_with_lyrics_the_song_floats_top_left_and_up_next_stays_right(ui):
    view, ctl, messages = ui
    give_words_and_a_queue(ctl)
    ctl.lyricsShown = True
    go(view, "now")
    pump(0.4)
    card, words = named(view, "songCard"), named(view, "words")
    up_next = named(view, "upNext")
    assert card.property("visible") is True and up_next.property("visible") is True
    x0, y0, _x1, _y1 = box(card)
    assert x0 < 200 and y0 < 200                       # the top-left corner
    assert apart(card, words) and apart(words, up_next) and apart(card, up_next)
    assert up_next.property("shown") == 1              # just the next song while the words show
    assert credit_in(up_next) == "Added by Priya"      # and who asked for it
    left, _t, right, _b = box(words)
    assert abs((left + right) / 2 - 960) < 2           # centred on the screen
    assert right - left > 1500                         # the words get the width Up Next gave up
    assert words.height() > 350                        # and the room between the top and the controls
    assert ctl.vizVisible is True
    press(view, Qt.Key.Key_Right, 2)                   # the volume button is still there
    assert "lyricsButton" not in focus_path(view) and view.activeFocusItem() is not None
    if SHOTS:
        for mode in ("edge", "radial"):
            ctl.visualizerMode = mode
            pump(0.3)
            view.grabWindow().save(str(Path(SHOTS) / f"now-lyrics-layout-{mode}.png"))
    ctl.lyricsShown = False
    pump(0.4)
    assert card.property("visible") is False
    assert problems(messages) == []


async def test_party_puts_the_song_top_left_lyrics_in_the_middle_and_up_next_right(ui):
    view, ctl, messages = ui
    give_words_and_a_queue(ctl)
    ctl.visualizerMode = "party"
    go(view, "visualizer")
    card, words, up_next = named(view, "partyCard"), named(view, "partyWords"), named(view, "partyUpNext")
    assert words.property("visible") is True and up_next.property("visible") is True
    assert card.property("visible") is False           # the controls use that corner while they show
    named(view, "visualizerPage").setProperty("chromeHidden", True)   # the controls fade away
    pump(0.5)
    assert card.property("visible") is True
    assert apart(card, words) and apart(words, up_next) and apart(card, up_next)
    assert box(card)[0] < 200 and box(card)[1] < 200
    left, _t, right, _b = box(words)
    assert abs((left + right) / 2 - 960) < 2           # centred on the screen
    assert right - left > 1500                         # Up Next is one song: the words get the width
    assert words.height() > 500                        # and most of the screen's height
    assert up_next.property("shown") == 1 and credit_in(up_next) == "Added by Priya"
    assert up_next.property("activeFocusOnTab") is False   # only to look at
    assert ctl.queueVisible is True                     # the queue loads for Up Next
    ctl.visualizerMode = "bars"
    pump(0.1)
    assert ctl.queueVisible is False
    if SHOTS:
        view.grabWindow().save(str(Path(SHOTS) / "visualizer-party-layout.png"))
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
    assert "edgesChip" in focus_path(view)
    press(view, Qt.Key.Key_Return)
    assert ctl.visualizerEdges is True         # edge lights over every picture
    press(view, Qt.Key.Key_Return)
    assert ctl.visualizerEdges is False
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


async def test_the_warning_button_opens_the_logs(ui):
    from couchside.core.health import Problem
    view, ctl, messages = ui
    chip = named(view, "problemChip")
    assert chip.property("visible") is False
    ctl._problems = [Problem("speaker-crashing", "This TV's speaker keeps stopping (exit code 1)")]
    ctl.healthChanged.emit()
    pump(0.2)
    assert chip.property("visible") is True
    go(view, "now")
    press(view, Qt.Key.Key_Up)                 # the bar: Left to the warning, first in line
    press(view, Qt.Key.Key_Left, 3)
    assert "problemChip" in focus_path(view)
    press(view, Qt.Key.Key_Return)
    pump(0.3)
    assert screen(view) == "logs" and "restartSpeaker" in focus_path(view)
    press(view, Qt.Key.Key_Down)
    assert "logPanel" in focus_path(view)
    press(view, Qt.Key.Key_Up)
    assert "restartSpeaker" in focus_path(view)
    if SHOTS:
        view.grabWindow().save(str(Path(SHOTS) / "logs.png"))
    back(view)
    assert screen(view) == "now"
    assert problems(messages) == []


async def test_the_tabs_sit_in_the_middle_of_the_screen(ui):
    view, ctl, _messages = ui
    row = named(view, "tabRow")
    from PySide6.QtCore import QPointF
    centre = row.mapToScene(QPointF(row.property("width") / 2, 0)).x()
    assert abs(centre - view.width() / 2) < 2
    ctl.toggleGuestMode()                      # the QR card doesn't push them aside
    pump(0.3)
    centre = row.mapToScene(QPointF(row.property("width") / 2, 0)).x()
    assert abs(centre - view.width() / 2) < 2


async def test_settings_change_music_assistants_crossfade(ui, monkeypatch):
    view, ctl, messages = ui
    from couchside.core.crossfade import Crossfade
    sent = []

    async def fake_load(client, qid):
        return Crossfade(True, "standard_crossfade", "smart_crossfade", 8)

    async def fake_seconds(client, seconds):
        sent.append(seconds)
        return True
    monkeypatch.setattr("couchside.ui.controller.crossfade.load", fake_load)
    monkeypatch.setattr("couchside.ui.controller.crossfade.set_seconds", fake_seconds)
    monkeypatch.setattr(ctl, "_queue_id", lambda: "q")
    async def settle():
        for _ in range(5):
            await asyncio.sleep(0)
        pump(0.1)
    go(view, "settings")
    await settle()
    named(view, "setupPage").setProperty("category", 2)      # This speaker
    pump(0.1)
    row = named(view, "crossfadeLengthRow")
    assert row.property("visible") is True
    assert ctl.crossfadeKnown is True and row.property("value") == "8 s"
    row.forceActiveFocus()
    press(view, Qt.Key.Key_Right)
    await settle()
    assert sent == [9] and row.property("value") == "9 s"
    press(view, Qt.Key.Key_Left)
    await settle()
    press(view, Qt.Key.Key_Left)
    await settle()
    assert sent == [9, 8, 7] and "crossfadeLengthRow" in focus_path(view)   # Left adjusts, stays put
    press(view, Qt.Key.Key_Up, 2)
    assert "crossfadeRow" in focus_path(view)
    assert problems(messages) == []
