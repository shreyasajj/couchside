"""Each screen and control on its own, with a stand-in controller (tests/qml/FakeApp.qml)
that records every call. Good paths: OK on each thing does what it says, with the right
arguments. Bad paths: empty, missing or odd data, refused input, things vanishing while
focused — the screen keeps working, keeps focus and logs no QML errors."""

import os
import re
import time
from pathlib import Path

import pytest

pytest.importorskip("PySide6.QtQuick")
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")
from PySide6.QtCore import (
    Q_ARG,
    Q_RETURN_ARG,
    QCoreApplication,
    QMetaObject,
    Qt,
    QUrl,
    qInstallMessageHandler,
)
from PySide6.QtQml import QQmlComponent
from PySide6.QtQuick import QQuickView
from PySide6.QtTest import QTest

HERE = Path(__file__).parent
QML = HERE.parent / "src/couchside/ui/qml"
BAD = re.compile(r"ReferenceError|TypeError|is not defined|Unable to assign|Cannot assign|"
                 r"non-existent property|is not a type|Binding loop|Cannot read property|Cannot call|"
                 r"load failed")


def pump(seconds=0.05):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        QCoreApplication.processEvents()
        time.sleep(0.005)


def plain(v):
    return v.toVariant() if hasattr(v, "toVariant") else v


def walk(item):
    for c in item.childItems():
        yield c
        yield from walk(c)


class Harness:
    def __init__(self, view, app, messages):
        self.view, self.app, self.messages = view, app, messages
        self.root = view.rootObject()

    # --- making a screen -----------------------------------------------------------------
    def load(self, name, **props):
        QMetaObject.invokeMethod(self.root, "load", Q_RETURN_ARG("QVariant"),
                                 Q_ARG("QVariant", name), Q_ARG("QVariant", props))
        pump(0.1)
        page = self.root.property("page")
        assert page is not None, f"{name} did not load: {self.messages}"
        return page

    def set(self, **props):
        for k, v in props.items():
            self.app.setProperty(k, v)
        pump(0.05)

    def emit(self, signal):
        QMetaObject.invokeMethod(self.app, signal)
        pump(0.05)

    # --- looking ------------------------------------------------------------------------
    def calls(self, name=None):
        c = [list(x) for x in plain(self.app.property("calls"))]
        return [x for x in c if name is None or x[0] == name]

    def clear(self):
        self.app.setProperty("calls", [])

    def events(self):
        return list(plain(self.root.property("events")))

    def items(self):
        return walk(self.root)

    def named(self, name):
        found = [i for i in self.items() if i.objectName() == name and i.isVisible()] or \
                [i for i in self.items() if i.objectName() == name]
        assert found, name
        return found[0]

    def with_text(self, text, prop=None):
        for i in self.items():
            for p in ([prop] if prop else ("text", "title", "label")):
                if i.property(p) == text and i.isVisible():
                    return i
        raise AssertionError(f"nothing visible says {text!r}")

    def texts(self):
        return [i.property("text") for i in self.items()
                if i.isVisible() and isinstance(i.property("text"), str) and i.property("text")]

    def shown(self, text):
        return any(text in t for t in self.texts())

    def focused(self):
        return self.view.activeFocusItem()

    def focused_text(self):
        item = self.view.activeFocusItem()
        while item is not None:
            for p in ("text", "title", "label"):
                v = item.property(p)
                if isinstance(v, str) and v:
                    return v
            if item.objectName():
                return item.objectName()
            item = item.parentItem()
        return ""

    # --- doing ----------------------------------------------------------------------------
    def press(self, key, times=1):
        for _ in range(times):
            QTest.keyClick(self.view, key)
            pump(0.03)
        pump(0.05)

    def ok(self):
        self.press(Qt.Key.Key_Return)

    def focus(self, item):
        item.forceActiveFocus()
        pump(0.05)

    @property
    def sheet(self):
        return self.named("sheet")

    def sheet_open(self):
        return bool(self.sheet.property("visible"))

    def sheet_labels(self):
        return [a["label"] for a in plain(self.sheet.property("actions"))]

    def choose(self, label):
        labels = self.sheet_labels()
        assert label in labels, (label, labels)
        self.sheet.setProperty("openedAt", 0)          # past the double-press guard
        self.sheet.setProperty("currentIndex", labels.index(label))
        self.ok()

    def problems(self):
        return [m for m in self.messages if BAD.search(m)]


@pytest.fixture
def h(qt_app):
    messages = []
    previous = qInstallMessageHandler(lambda _m, _c, text: messages.append(text))
    view = QQuickView()
    view.resize(1920, 1080)
    comp = QQmlComponent(view.engine(), QUrl.fromLocalFile(str(HERE / "qml/FakeApp.qml")))
    app = comp.create()
    assert app is not None, comp.errors()
    view.rootContext().setContextProperty("app", app)
    view.setSource(QUrl.fromLocalFile(str(HERE / "qml/ComponentHarness.qml")))
    assert view.status() == QQuickView.Status.Ready, view.errors()
    view.show()
    view.requestActivate()
    pump(0.1)
    harness = Harness(view, app, messages)
    yield harness
    problems = harness.problems()
    view.close()
    qInstallMessageHandler(previous)
    assert problems == []


# === the stand-in covers what the QML uses ===============================================
def test_the_stand_in_and_the_real_controller_have_everything_the_qml_uses(h, qt_app):
    """Every `app.x` in the QML exists on FakeApp and on the real controller, so these
    tests can't drift from the app and the QML never calls something that isn't there."""
    from couchside.core.settings import AppSettings
    from couchside.ui.controller import AppController

    used = set()
    for f in list(QML.glob("*.qml")) + list(QML.glob("*.js")):
        used |= set(re.findall(r"\bapp\.([a-zA-Z0-9]+)", f.read_text()))
    real = AppController(AppSettings())
    meta = real.metaObject()
    real_names = {meta.property(i).name() for i in range(meta.propertyCount())} | \
                 {bytes(meta.method(i).name()).decode() for i in range(meta.methodCount())}
    fake_meta = h.app.metaObject()
    fake_names = {fake_meta.property(i).name() for i in range(fake_meta.propertyCount())} | \
                 {bytes(fake_meta.method(i).name()).decode() for i in range(fake_meta.methodCount())}
    assert sorted(used - real_names) == []
    assert sorted(used - fake_names) == []


# === Now Playing ==========================================================================
NOW_BUTTONS = [("Shuffle off", "toggleShuffle"), ("Repeat off", "cycleRepeat"), ("Previous", "previous"),
               ("Pause", "playPause"), ("Next", "next")]


@pytest.mark.parametrize("text,call", NOW_BUTTONS)
def test_now_playing_transport_buttons(h, text, call):
    h.load("NowPlayingPage")
    h.focus(h.with_text(text))
    h.ok()
    assert h.calls(call) == [[call]]


def test_now_playing_the_other_buttons(h):
    h.load("NowPlayingPage")
    h.focus(h.named("volumeButton"))
    h.ok()
    assert h.events()[0].startswith("openVolume")
    h.focus(h.named("lyricsButton"))
    h.ok()
    assert h.app.property("lyricsShown") is False
    h.focus(h.named("visualizerButton"))
    h.ok()
    assert h.events()[-1] == "openPage:visualizer"
    h.focus(h.named("guestButton"))
    h.ok()
    assert h.calls("toggleGuestMode") == [["toggleGuestMode"]]
    h.set(guestMode=True)
    assert h.named("guestButton").property("text") == "Guests"
    h.ok()
    assert h.events()[-1] == "openPage:guests"
    h.set(queueRows=[{"itemId": "a", "title": "Now", "subtitle": "", "current": True, "addedBy": ""},
                     {"itemId": "b", "title": "Later", "subtitle": "X", "current": False, "addedBy": "Sam"}])
    h.focus(h.named("upNext"))
    h.ok()
    assert h.events()[-1] == "openPage:queue"


def test_now_playing_left_and_right_walk_every_control_in_order(h):
    h.load("NowPlayingPage")
    h.focus(h.with_text("Shuffle off"))
    seen = [h.focused_text()]
    for _ in range(10):
        h.press(Qt.Key.Key_Right)
        seen.append(h.focused_text())
    assert seen == ["Shuffle off", "Repeat off", "Guest mode", "Previous", "Pause", "Next", "Volume 40",
                    "Hide lyrics", "Visualizer", "Party", "upNext"]   # then Up Next, top-right


def test_party_hides_the_controls_and_any_key_brings_them_back(h):
    page = h.load("NowPlayingPage")
    h.focus(h.named("partyButton"))
    h.ok()
    assert page.property("partyMode") and not h.named("playButton").isVisible()
    assert h.named("progress").isVisible()
    h.press(Qt.Key.Key_Down)
    assert not page.property("partyMode") and h.focused_text() == "Party"
    assert h.calls() == []                                  # the key did nothing else


def test_now_playing_with_nothing_playing_and_no_volume_or_lyrics(h):
    h.set(title="", artist="", album="", isPlaying=False, hasVolume=False, lyricsEnabled=False,
          hasLocalPlayer=True, duration=0, hasDuration=False)
    h.load("NowPlayingPage")
    assert h.shown("Nothing playing") and h.shown("Play something from Music Assistant")
    assert not h.named("volumeButton").isVisible() and not h.named("lyricsButton").isVisible()
    h.focus(h.named("playButton"))
    h.press(Qt.Key.Key_Right, 2)
    assert h.focused_text() == "Visualizer"               # skips the hidden buttons
    h.press(Qt.Key.Key_Left, 2)
    assert h.focused_text() == "Play"


def test_buttons_that_vanish_while_focused_hand_focus_to_play(h):
    h.load("NowPlayingPage")
    h.focus(h.named("volumeButton"))
    h.set(hasVolume=False)
    assert h.focused_text() == "Pause"
    h.focus(h.named("lyricsButton"))
    h.set(lyricsEnabled=False)
    assert h.focused_text() == "Pause"


def test_a_very_long_title_stays_on_one_line(h):
    h.set(title="A " * 200, artist="B " * 200, lyricsShown=False)
    h.load("NowPlayingPage")
    title = h.with_text("A " * 200)
    assert title.property("lineCount") == 1 and title.property("truncated")


# === Queue =================================================================================
def qrow(item_id, title, current=False, added_by="", duration=200):
    return {"itemId": item_id, "title": title, "subtitle": "Artist", "imageUrl": "",
            "duration": duration, "current": current, "addedBy": added_by}


QUEUE = [qrow("a", "Neon Tide", current=True), qrow("b", "Glass Harbour", added_by="Sam"),
         qrow("c", "Slow Comet")]


def test_queue_rows_and_the_actions_each_row_offers(h):
    h.set(queueRows=QUEUE)
    h.load("QueuePage")
    assert h.shown("Queue · 3 songs") and h.shown("Now playing") and h.shown("Up next")
    assert h.shown("Added by Sam") and h.shown("3:20")
    h.ok()                                         # the playing song
    assert h.sheet_labels() == ["Move down", "Remove from queue"]
    h.choose("Remove from queue")
    assert h.calls("queueAction") == [["queueAction", "a", "remove"]]
    h.press(Qt.Key.Key_Down)
    h.ok()                                         # the first one waiting: can't go above the current
    assert h.sheet_labels() == ["Play this now", "Play next", "Move down", "Remove from queue"]
    h.choose("Play this now")
    h.press(Qt.Key.Key_Down)
    h.ok()                                         # the last
    assert h.sheet_labels() == ["Play this now", "Play next", "Move up", "Remove from queue"]
    h.choose("Move up")
    assert h.calls("queueAction")[1:] == [["queueAction", "b", "play"], ["queueAction", "c", "up"]]


def test_an_empty_queue_says_so_and_ok_does_nothing(h):
    h.load("QueuePage")
    assert h.shown("Nothing queued — add songs from Search")
    h.ok()
    assert not h.sheet_open() and h.calls("queueAction") == []


def test_the_queue_keeps_focus_on_the_same_song_when_it_changes(h):
    h.set(queueRows=QUEUE)
    h.load("QueuePage")
    h.press(Qt.Key.Key_Down, 2)
    assert h.focused_text() == "Slow Comet"
    h.set(queueRows=[QUEUE[0], qrow("new", "New song"), QUEUE[1], QUEUE[2]])
    h.emit("queueChanged")
    assert h.focused_text() == "Slow Comet"
    h.set(queueRows=[QUEUE[0]])                        # the focused song went
    h.emit("queueChanged")
    assert h.focused_text() == "Neon Tide"
    h.set(queueRows=[])
    h.emit("queueChanged")
    assert h.focused() is not None and h.shown("Nothing queued")


def test_queue_rows_with_missing_bits_still_show(h):
    h.set(queueRows=[{"itemId": "x", "title": "", "subtitle": "", "imageUrl": "", "duration": 0,
                      "current": False, "addedBy": ""}])
    h.load("QueuePage")
    h.ok()
    assert h.sheet_labels() == ["Play this now", "Play next", "Remove from queue"]


# === Speakers and groups ====================================================================
def srow(pid, name, available=True, controlled=False, local=False, group=False, members=(),
         synced_to="", can_sync=False, playing=""):
    return {"playerId": pid, "name": name, "isGroup": group, "available": available,
            "controlled": controlled, "local": local, "syncedTo": synced_to, "members": list(members),
            "canSync": can_sync, "playing": playing}


SPEAKERS = [srow("tv", "Living Room TV", controlled=True, local=True),
            srow("kitchen", "Kitchen", can_sync=True, playing="Song — Band"),
            srow("grp", "Downstairs", group=True, members=("tv", "kitchen")),
            srow("den", "Den", available=False)]


def test_speaker_rows_and_what_each_offers(h):
    h.set(speakerRows=SPEAKERS)
    h.load("SpeakersPage")
    assert h.shown("Playing on Living Room TV") and h.shown("This TV") and h.shown("Controlling")
    assert h.shown("Song — Band") and h.shown("Living Room TV, Kitchen") and h.shown("Offline")
    h.ok()
    assert h.sheet_labels() == ["Close"]                    # already the one being controlled
    h.choose("Close")
    assert h.calls() == [] or all(c[0] != "speakerAction" for c in h.calls())
    h.press(Qt.Key.Key_Down)
    h.ok()
    assert h.sheet_labels() == ["Control this speaker", "Move the queue here", "Sync with Living Room TV"]
    h.choose("Control this speaker")
    h.ok()
    h.choose("Move the queue here")
    h.ok()
    h.choose("Sync with Living Room TV")
    assert h.calls("controlSpeaker") == [["controlSpeaker", "kitchen"]]
    assert h.calls("speakerAction") == [["speakerAction", "kitchen", "transfer"],
                                        ["speakerAction", "kitchen", "sync"]]
    h.press(Qt.Key.Key_Down)
    h.ok()
    assert h.sheet_labels()[-2:] == ["Edit members", "Delete group"]
    h.choose("Delete group")
    assert h.calls("speakerAction")[-1] == ["speakerAction", "grp", "delete_group"]
    h.press(Qt.Key.Key_Down)
    h.ok()
    assert h.sheet_labels() == ["Offline — close"]
    h.choose("Offline — close")
    assert len(h.calls("speakerAction")) == 3


def test_synced_speaker_offers_stop_syncing(h):
    h.set(speakerRows=[SPEAKERS[0], srow("kitchen", "Kitchen", synced_to="tv")])
    h.load("SpeakersPage")
    assert h.shown("Synced with Living Room TV")
    h.press(Qt.Key.Key_Down)
    h.ok()
    assert "Stop syncing" in h.sheet_labels()
    h.choose("Stop syncing")
    assert h.calls("speakerAction") == [["speakerAction", "kitchen", "unsync"]]


def test_new_group_and_edit_group_through_the_editor(h):
    h.set(speakerRows=SPEAKERS)
    h.load("SpeakersPage")
    h.press(Qt.Key.Key_Down, 4)
    assert h.focused_text() == "New group"
    h.ok()
    editor = h.named("groupEditor")
    assert editor.property("visible") and h.shown("New group") and h.shown("Pick at least two")
    h.ok()                                    # Living Room TV
    h.press(Qt.Key.Key_Down)
    h.ok()                                    # Kitchen
    assert h.shown("Save")
    h.press(Qt.Key.Key_Down)                  # the den (offline) and the group aren't offered
    assert h.focused_text() == "Save"
    h.ok()
    assert h.calls("createGroup") == [["createGroup", ["tv", "kitchen"]]]
    assert not editor.property("visible") and h.focused_text() == "New group"

    h.press(Qt.Key.Key_Up, 2)                 # back into the list (the den), then up one
    assert h.focused_text() == "Downstairs"
    h.ok()
    h.choose("Edit members")
    pump(0.1)
    assert editor.property("visible") and h.shown("Edit group")
    h.ok()                                    # take the TV out
    h.press(Qt.Key.Key_Down, 2)
    h.ok()                                    # "Pick at least two": does nothing
    assert h.calls("editGroup") == [] and editor.property("visible")
    h.press(Qt.Key.Key_Right)
    h.ok()                                    # Cancel
    assert not editor.property("visible") and h.calls("editGroup") == []


def test_no_speakers_still_offers_a_new_group(h):
    h.load("SpeakersPage")
    h.press(Qt.Key.Key_Down)
    assert h.focused_text() == "New group"
    h.ok()
    assert h.shown("Pick at least two")
    h.press(Qt.Key.Key_Down)
    h.ok()
    assert h.calls("createGroup") == []


# === Guests =================================================================================
GUESTS = [{"id": "g1", "name": "Sam", "admin": False, "skipsLeft": 2, "boostsLeft": 1},
          {"id": "g2", "name": "Alex", "admin": True, "skipsLeft": 3, "boostsLeft": 2}]


def test_guests_page_buttons_and_rows(h):
    h.set(guestMode=True, guestRows=GUESTS)
    h.load("GuestsPage")
    assert h.shown("Guest mode is on") and h.shown("2 guests") and h.shown("Skips left 2 · Boosts left 1")
    h.focus(h.named("guestModeButton"))
    h.ok()
    assert h.calls("toggleGuestMode") == [["toggleGuestMode"]]
    h.press(Qt.Key.Key_Down)
    h.ok()
    assert h.calls("showAdminCode") == [["showAdminCode"]]
    h.press(Qt.Key.Key_Down)
    assert h.focused_text() == "Sam"
    for label in ("Make admin", "Give back skips and boosts", "Remove from the party"):
        h.ok()
        assert h.sheet_labels() == ["Make admin", "Give back skips and boosts", "Remove from the party"]
        h.choose(label)
        assert h.focused_text() == "Sam"                    # back on the row
    assert [c[2] for c in h.calls("guestAction")] == ["promote", "reset", "remove"]
    h.press(Qt.Key.Key_Down)
    h.ok()
    assert h.sheet_labels() == ["Remove admin", "Remove from the party"]
    h.choose("Remove admin")
    assert h.calls("guestAction")[-1] == ["guestAction", "g2", "revoke"]


def test_guests_page_with_guest_mode_off_and_guests_leaving(h):
    h.load("GuestsPage")
    assert h.shown("Guest mode is off") and h.shown("Turn guest mode on to let guests add songs")
    h.press(Qt.Key.Key_Down, 3)
    assert h.focused_text() == "Show an admin code"     # nothing below it
    h.set(guestMode=True, guestRows=GUESTS)
    h.emit("guestChanged")
    h.press(Qt.Key.Key_Down)
    assert h.focused_text() == "Sam"
    h.set(guestRows=[])
    h.emit("guestChanged")
    assert h.focused_text() == "Guest mode is on"       # the list emptied under focus
    assert h.shown("No guests yet")


# === Search =================================================================================
def card(title, uri, kind="track", subtitle=""):
    return {"key": uri, "kind": kind, "title": title, "subtitle": subtitle, "imageUrl": "", "uri": uri}


LIBRARY = [{"title": "Tracks", "items": [card("Paper Moons", "t://1"), card("Night Swim", "t://2")]},
           {"title": "Artists", "items": [card("The Lanterns", "a://1", "artist")]}]


def test_search_typing_searches_and_ok_on_a_card_plays_it(h):
    h.load("LibraryPage")
    assert h.calls("loadRecents") == [["loadRecents"]]
    h.ok()                                          # start typing
    type_text(h, "lantern")
    pump(0.45)                                      # after the pause in typing
    assert h.calls("search")[-1] == ["search", "lantern"]
    h.set(libraryRows=LIBRARY)
    h.emit("libraryChanged")
    h.press(Qt.Key.Key_Return)                      # the keyboard's Enter: to the results
    assert h.focused_text() == "Paper Moons"
    h.press(Qt.Key.Key_Right)
    assert h.focused_text() == "Night Swim"
    h.ok()
    assert h.sheet_labels() == ["Play now", "Play next", "Add to queue"]
    h.choose("Play next")
    assert h.calls("playUri") == [["playUri", "t://2", "next"]]
    h.press(Qt.Key.Key_Down)
    assert h.focused_text() == "The Lanterns"
    h.ok()
    h.choose("Play now")
    h.press(Qt.Key.Key_Up, 2)
    assert h.focused().objectName() == "searchBox" or h.named("searchBox").property("activeFocus")
    assert h.calls("playUri")[-1] == ["playUri", "a://1", "now"]


@pytest.mark.parametrize("state,text", [
    ({"libraryBusy": True}, "Searching…"),
    ({"libraryError": "Search failed — check the connection"}, "Search failed — check the connection"),
    ({}, "Nothing here yet — try a search"),
])
def test_search_states_are_spelled_out(h, state, text):
    h.load("LibraryPage")
    h.set(**state)
    assert h.shown(text)
    h.press(Qt.Key.Key_Down)                        # no results: focus stays on the box
    assert h.named("searchBox").property("activeFocus")


def test_search_with_no_results_says_so(h):
    h.load("LibraryPage")
    h.ok()
    type_text(h, "zzzz")
    h.press(Qt.Key.Key_Return)
    assert h.shown("No results") and h.named("searchBox").property("activeFocus")


def test_results_vanishing_under_focus_return_to_the_search_box(h):
    h.set(libraryRows=LIBRARY)
    h.load("LibraryPage")
    h.press(Qt.Key.Key_Down)
    assert h.focused_text() == "Paper Moons"
    h.set(libraryRows=[])
    h.emit("libraryChanged")
    assert h.named("searchBox").property("activeFocus")


# === Logs ===================================================================================
def test_logs_buttons(h):
    h.load("LogsPage")
    assert h.calls("loadLogs") == [["loadLogs"]] and h.shown("Nothing is wrong right now.")
    assert h.shown("speaker line 2")
    h.ok()
    assert h.calls("restartSpeaker") == [["restartSpeaker"]]
    h.press(Qt.Key.Key_Right, 2)
    h.ok()
    assert h.shown("app line 1") and not h.shown("speaker line 2")
    h.press(Qt.Key.Key_Left)
    h.ok()
    assert h.shown("speaker line 2")
    h.press(Qt.Key.Key_Down)
    assert h.focused().objectName() == "logPanel" or h.named("logPanel").property("activeFocus")
    h.press(Qt.Key.Key_Up)
    assert h.focused_text() == "Restart this TV's speaker"


def test_logs_list_what_is_wrong(h):
    h.set(problem="The speaker stopped", problems=["The speaker stopped", "No audio device"],
          sendspinLog="")
    h.load("LogsPage")
    assert h.shown("Something's wrong") and h.shown("No audio device")
    assert not h.shown("Nothing is wrong right now.")


# === Visualizer ===============================================================================
def test_visualizer_mode_buttons_and_chips(h):
    h.load("VisualizerPage")
    assert h.focused_text() == "Radial Pulse"
    h.press(Qt.Key.Key_Right)
    assert h.app.property("visualizerMode") == "flow"        # moving onto a picture shows it
    h.press(Qt.Key.Key_Right, 3)
    assert h.app.property("visualizerMode") == "off" and h.named("vizOffNote").isVisible()
    assert not h.named("visualizerScene").isVisible()
    h.press(Qt.Key.Key_Right)
    assert h.focused_text() == "Off"                          # no wrap
    h.press(Qt.Key.Key_Up)
    h.ok()
    assert h.app.property("visualizerEdges") is True
    h.press(Qt.Key.Key_Up)
    h.ok()
    assert h.sheet_labels() == ["Theme", "Rainbow"]
    h.choose("Rainbow")
    assert h.calls("setVisualizerColours") == [["setVisualizerColours", "rainbow"]]
    h.press(Qt.Key.Key_Up)
    h.press(Qt.Key.Key_Right)
    assert abs(h.app.property("visualizerIntensity") - 1.05) < 1e-6
    h.press(Qt.Key.Key_Left, 2)
    assert abs(h.app.property("visualizerIntensity") - 0.95) < 1e-6
    h.press(Qt.Key.Key_Up)
    h.ok()
    assert h.sheet_labels() == ["This TV", "Microphone"]
    h.choose("Microphone")
    assert h.calls("setBeatSource") == [["setBeatSource", "mic"]]


def test_visualizer_with_an_unknown_saved_mode_focuses_the_first_picture(h):
    h.set(visualizerMode="party")
    h.load("VisualizerPage")
    assert h.focused_text() == "Radial Pulse"


def test_visualizer_controls_hide_when_idle_and_any_key_brings_them_back(h):
    page = h.load("VisualizerPage")
    from PySide6.QtCore import QObject
    idle = page.findChild(QObject, "idleTimer")
    idle.setProperty("interval", 50)
    QMetaObject.invokeMethod(idle, "restart")
    pump(0.15)
    assert page.property("chromeHidden")
    idle.setProperty("interval", 4000)
    pump(0.6)                                                  # the controls fade out
    assert h.view.activeFocusItem().objectName() == "keySink"  # the next key only wakes it
    h.press(Qt.Key.Key_Left)
    assert not page.property("chromeHidden") and h.focused_text() == "Radial Pulse"
    assert h.app.property("visualizerMode") == "radial"       # the key only woke it


# === Settings =================================================================================
SETTINGS = {
    "Guest mode": [("Guest mode", "toggleGuestMode"), ("Skips per guest", "cycleGuestSkips"),
                   ("Boosts per guest", "cycleGuestBoosts"),
                   ("Songs waiting per guest", "cycleGuestMaxWaiting"),
                   ("Wait between adds", "cycleGuestCooldown")],
    "This speaker": [("Sync delay", "cycleSendspinDelay"), ("Crossfade", "toggleCrossfade"),
                     ("Crossfade length", "stepCrossfadeSeconds")],
    "Lyrics": [("Size", "cycleLyricsSize"), ("Language", "cycleLyricsLanguage"),
               ("English underneath", "toggleLyricsTranslate")],
    "Updates": [("Couchside 1.0.0", "installUpdate")],
}


def open_category(h, page, name):
    cats = ["Music Assistant", "Guest mode", "This speaker", "Visualizer", "Lyrics", "Look", "Updates"]
    page.setProperty("category", cats.index(name))
    pump(0.05)
    QMetaObject.invokeMethod(page, "enterPane")
    pump(0.05)


@pytest.mark.parametrize("category", list(SETTINGS))
def test_settings_rows_call_what_they_say(h, category):
    page = h.load("SetupPage")
    open_category(h, page, category)
    for label, call in SETTINGS[category]:
        h.focus(h.with_text(label, "label"))
        h.ok()
        assert h.calls(call), (label, call)


@pytest.mark.parametrize("label,prop", [
    ("Beat pulse on Now Playing", "visualizerEnabled"), ("Edge lights on every picture", "visualizerEdges")])
def test_settings_toggles_flip_the_setting(h, label, prop):
    page = h.load("SetupPage")
    open_category(h, page, "Visualizer")
    before = h.app.property(prop)
    h.focus(h.with_text(label, "label"))
    h.ok()
    assert h.app.property(prop) is (not before)


@pytest.mark.parametrize("label,prop", [("Show lyrics", "lyricsEnabled"),
                                        ("Visualizer behind the lyrics", "lyricsVisualizer")])
def test_lyrics_toggles_flip_the_setting(h, label, prop):
    page = h.load("SetupPage")
    open_category(h, page, "Lyrics")
    h.focus(h.with_text(label, "label"))
    h.ok()
    assert h.app.property(prop) is False


@pytest.mark.parametrize("category,label,choice,call,arg", [
    ("This speaker", "Audio output", "HDMI", "setAudioOutput", "hdmi"),
    ("This speaker", "Crossfade style", "Smart", "setCrossfadeMode", "smart_crossfade"),
    ("Visualizer", "Beat source", "Microphone", "setBeatSource", "mic"),
    ("Visualizer", "Colours", "Rainbow", "setVisualizerColours", "rainbow"),
    ("Look", "Colours", "Ocean", "setAccent", "ocean"),
])
def test_settings_pickers_apply_the_choice(h, category, label, choice, call, arg):
    page = h.load("SetupPage")
    open_category(h, page, category)
    h.focus(h.with_text(label, "label"))
    h.ok()
    assert h.sheet_open()
    h.choose(choice)
    assert h.calls(call) == [[call, arg]]


def test_settings_picture_picker_sets_the_visualizer(h):
    page = h.load("SetupPage")
    open_category(h, page, "Visualizer")
    h.focus(h.named("vizPictureRow"))
    h.ok()
    assert h.sheet_labels() == ["Radial Pulse", "Flow Lines", "Bars", "Edge Lights", "Off"]
    h.choose("Off")
    assert h.app.property("visualizerMode") == "off"


def test_settings_adjust_rows_take_left_and_right(h):
    page = h.load("SetupPage")
    open_category(h, page, "This speaker")
    h.focus(h.named("crossfadeLengthRow"))
    h.press(Qt.Key.Key_Right)
    h.press(Qt.Key.Key_Left)
    assert h.calls("stepCrossfadeSeconds") == [["stepCrossfadeSeconds", 1], ["stepCrossfadeSeconds", -1]]
    open_category(h, page, "Visualizer")
    h.focus(h.named("beatIntensityRow"))
    h.ok()
    assert h.app.property("visualizerIntensity") == 1.5
    h.press(Qt.Key.Key_Left)
    assert abs(h.app.property("visualizerIntensity") - 1.45) < 1e-6


def type_text(h, text):
    for ch in text:
        QTest.keyClick(h.view, ch)
    pump(0.05)


def type_into(h, field, text, enter=True):
    h.focus(field)
    h.ok()
    type_text(h, text)
    if enter:
        h.press(Qt.Key.Key_Return)


def test_settings_text_fields_save_on_enter(h):
    page = h.load("SetupPage")
    open_category(h, page, "Guest mode")
    fields = [i for i in h.items() if i.property("editing") is not None and i.isVisible()]
    caption, public, port = fields
    type_into(h, caption, "Add one!")
    type_into(h, public, "https://party.example")
    type_into(h, port, "9000")
    assert h.calls("setQrCaption") == [["setQrCaption", "Scan to add songsAdd one!"]]
    assert h.calls("setGuestPublicUrl") == [["setGuestPublicUrl", "https://party.example"]]
    assert h.calls("setGuestPort") == [["setGuestPort", "87809000"]]
    assert port.property("text") == "8780"           # shows what the app kept
    assert not port.property("editing")              # Enter stopped editing; it didn't start again


def test_save_and_connect_needs_a_token_the_first_time(h):
    h.set(hasToken=False, needsSetup=True)
    page = h.load("SetupPage")
    assert page.property("category") == 0
    token = h.view.activeFocusItem()
    save = h.with_text("Save and connect")
    h.focus(save)
    h.ok()
    assert h.calls("saveConnection") == [] and h.events() == []     # nothing typed yet
    type_into(h, token.parentItem() if token.property("editing") is None else token, "abc123")
    h.focus(save)
    h.ok()
    assert h.calls("saveConnection") == [["saveConnection", "", "abc123"]] and h.events() == ["done"]


def test_settings_show_a_refused_token_and_hide_crossfade_when_unknown(h):
    h.set(connState="auth_failed", crossfadeKnown=False)
    page = h.load("SetupPage")
    assert h.shown("Music Assistant did not accept the token")
    open_category(h, page, "This speaker")
    assert not h.named("crossfadeRow").isVisible()


def test_settings_links_to_guests_and_logs(h):
    h.set(guestMode=True)
    page = h.load("SetupPage")
    open_category(h, page, "Guest mode")
    h.focus(h.with_text("Guests and admins", "label"))
    h.ok()
    open_category(h, page, "This speaker")
    h.focus(h.named("logsRow"))
    h.ok()
    assert h.events() == ["openGuests", "openLogs"]


def test_settings_translation_rows_appear_with_the_service(h):
    h.set(lyricsTranslate=True, translateService="deepl")
    page = h.load("SetupPage")
    open_category(h, page, "Lyrics")
    h.focus(h.with_text("Translation service", "label"))
    h.ok()
    assert h.calls("cycleTranslateService")
    assert h.shown("DeepL API key")
    key = next(i for i in h.items() if i.property("editing") is not None and i.isVisible()
           and "key" in (i.property("placeholderText") or ""))
    type_into(h, key, "k:fx")
    assert h.calls("saveDeeplKey") == [["saveDeeplKey", "k:fx"]] and key.property("text") == ""


# === Overlays and small controls ===============================================================
def test_volume_popup_steps_clamps_and_closes(h):
    popup = h.load("VolumePopup")
    QMetaObject.invokeMethod(popup, "open", Q_ARG("QVariant", True))
    pump(0.05)
    assert popup.property("level") == 40
    h.press(Qt.Key.Key_Right, 2)
    assert h.calls("setVolume") == [["setVolume", 45], ["setVolume", 50]]
    popup.setProperty("level", 98)
    h.press(Qt.Key.Key_Right)
    assert popup.property("level") == 100
    popup.setProperty("level", 2)
    h.press(Qt.Key.Key_Left, 2)
    assert popup.property("level") == 0 and h.calls("setVolume")[-1] == ["setVolume", 0]
    h.press(Qt.Key.Key_Up)                          # swallowed: nothing else moves
    h.ok()
    assert not popup.property("visible") and "closed" in h.events()


def test_admin_code_overlay_splits_six_digits_and_swallows_keys(h):
    h.set(adminCode="123456")
    h.load("AdminCodeOverlay")
    assert h.named("adminCodeText").property("text") == "123 456"
    h.set(adminCode="12")
    assert h.named("adminCodeText").property("text") == "12"
    h.press(Qt.Key.Key_Return)
    assert h.calls() == []


def test_pairing_overlay_shows_the_code(h):
    h.set(pairingCode="4821")
    h.load("PairingOverlay")
    assert h.shown("4821") and h.shown("Enter this code in Music Assistant")


@pytest.mark.parametrize("name,signal", [("ListRow", "activated"), ("MediaCardItem", "activated"),
                                         ("UpNext", "activated"), ("QrCard", "clicked"),
                                         ("FocusButton", "clicked"), ("PillButton", "clicked"),
                                         ("Chip", "clicked")])
@pytest.mark.parametrize("key", [Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Select])
def test_every_kind_of_button_answers_ok_enter_and_select(h, name, signal, key):
    h.load(name)
    h.press(key)
    assert h.events() == [signal]


@pytest.mark.parametrize("name", ["ListRow", "MediaCardItem", "UpNext", "QrCard"])
def test_holding_ok_down_does_not_repeat_the_action(h, name):
    h.load(name)
    QTest.keyPress(h.view, Qt.Key.Key_Return)
    from PySide6.QtCore import QEvent
    from PySide6.QtGui import QKeyEvent
    repeat = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier, "\r", True)
    QCoreApplication.sendEvent(h.view, repeat)
    QTest.keyRelease(h.view, Qt.Key.Key_Return)
    pump()
    assert h.events() == ["activated" if name != "QrCard" else "clicked"]


def test_a_disabled_pill_button_does_nothing(h):
    h.load("PillButton", enabled=False)
    h.root.property("page").forceActiveFocus()
    h.press(Qt.Key.Key_Return)
    assert h.events() == []


def test_a_sheet_closing_after_its_opener_went_away_does_not_lose_focus(h):
    page = h.load("ListRow", title="Opener")
    QMetaObject.invokeMethod(h.sheet, "open", Q_ARG("QVariant", "Pick"),
                             Q_ARG("QVariant", [{"id": "a", "label": "A"}]), Q_ARG("QVariant", page),
                             Q_ARG("QVariant", None))
    pump(0.05)
    page.deleteLater()
    pump(0.05)
    h.press(Qt.Key.Key_Escape)
    QMetaObject.invokeMethod(h.sheet, "close")
    pump(0.05)
    assert h.view.activeFocusItem() is not None
