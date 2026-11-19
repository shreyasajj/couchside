"""Every button in the app, pressed with the remote's OK, in the real UI (Shell.qml) on the
real controller and a fake Music Assistant (tests/fake_ma.py), and what it should do checked
where it lands: in Music Assistant, on screen, or in the settings.

`BUTTONS` lists every button on every screen. test_every_button_has_a_check finds the
buttons that are really on screen and fails if one is missing from `BUTTONS` (a new button
needs a check) or if `BUTTONS` names one that is gone."""

import os
from pathlib import Path

import pytest

pytest.importorskip("PySide6.QtQuick")
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")
from PySide6.QtCore import Q_ARG, QMetaObject, Qt, QUrl, qInstallMessageHandler
from PySide6.QtQuick import QQuickView
from PySide6.QtTest import QTest

from couchside.core.health import Problem
from tests.conftest import settle, until
from tests.fake_ma import KITCHEN, TV
from tests.test_components_qml import BAD

SHELL = Path(__file__).parents[1] / "src/couchside/ui/qml/Shell.qml"
SECTIONS = ["Music Assistant", "Guest mode", "This speaker", "Visualizer", "Lyrics", "Look", "Updates"]


def walk(item):
    for c in item.childItems():
        yield c
        yield from walk(c)


def in_top_bar(item):
    while item is not None:
        if item.objectName() == "topBar":
            return True
        item = item.parentItem()
    return False


def is_button(item):
    m = item.metaObject()
    return any(m.indexOfSignal(s) >= 0 for s in ("clicked()", "activated()"))


def key_of(item):
    """A button's name in BUTTONS: its objectName, else its label / title / text."""
    if item.objectName():
        return item.objectName()
    label = item.property("label")
    if isinstance(label, str) and label:
        return "Couchside (version)" if label.startswith("Couchside ") else label
    title = item.property("title")
    if isinstance(title, str) and title:
        return "row:" + title
    return item.property("text") or type(item).__name__


class TV_:
    """The app on the TV, driven like a remote."""

    def __init__(self, view, ctl, ma, quits):
        self.view, self.ctl, self.ma, self.quits = view, ctl, ma, quits
        self.root = view.rootObject()

    @property
    def screen(self):
        return self.root.property("screen")

    async def go(self, screen):
        QMetaObject.invokeMethod(self.root, "go", Q_ARG("QVariant", screen))
        await settle(0.25)

    async def back(self):
        QMetaObject.invokeMethod(self.root, "goBack")
        await settle(0.15)

    async def press(self, key, times=1):
        for _ in range(times):
            QTest.keyClick(self.view, key)
            await settle(0.03)
        await settle(0.08)

    async def ok(self):
        await self.press(Qt.Key.Key_Return)

    def buttons(self, top_bar=False):
        found = {}
        for i in walk(self.root):
            if i.isVisible() and is_button(i) and in_top_bar(i) == top_bar and not self.in_overlay(i):
                found.setdefault(key_of(i), i)
        return found

    def in_overlay(self, item):
        while item is not None:
            if item.property("openedAt") is not None or item.objectName() in ("exitConfirm",) \
                    or (item.property("chosen") is not None and item.property("groupId") is not None):
                return True
            item = item.parentItem()
        return False

    def named(self, name):
        found = [i for i in walk(self.root) if i.objectName() == name]
        assert found, name
        return found[0]

    def find(self, key, top_bar=False):
        found = self.buttons(top_bar)
        assert key in found, (key, sorted(found))
        return found[key]

    async def press_button(self, key, top_bar=False):
        self.find(key, top_bar).forceActiveFocus()
        await settle(0.05)
        await self.ok()

    def focus_names(self):
        names, item = [], self.view.activeFocusItem()
        while item is not None:
            if item.objectName():
                names.append(item.objectName())
            item = item.parentItem()
        return names

    # --- the action sheet ----------------------------------------------------------------
    @property
    def sheet(self):
        return next(i for i in walk(self.root) if i.property("openedAt") is not None)

    def sheet_open(self):
        return bool(self.sheet.property("visible"))

    def sheet_title(self):
        return self.sheet.property("title")

    def sheet_labels(self):
        acts = self.sheet.property("actions")
        acts = acts.toVariant() if hasattr(acts, "toVariant") else acts
        return [a["label"] for a in acts]

    async def choose(self, label):
        labels = self.sheet_labels()
        assert label in labels, (label, labels)
        self.sheet.setProperty("openedAt", 0)          # past the guard against a double OK
        self.sheet.setProperty("currentIndex", labels.index(label))
        await self.ok()

    @property
    def editor(self):
        return next(i for i in walk(self.root) if i.property("groupId") is not None)


@pytest.fixture
async def tv(house, monkeypatch):
    ctl, ma = house.ctl, house.ma
    restarts = []

    async def fake_restart():
        restarts.append(1)
    monkeypatch.setattr(ctl, "_restart_sendspin", fake_restart)
    updates = []

    class Updater:
        async def update(self):
            updates.append(1)
    ctl._updater, ctl._update_state = Updater(), "available"

    ctl.toggleGuestMode()                       # the QR card, the guest list and its rows
    ctl._guest_session.join("device-aaaaaaaa1", "Sam")
    ctl.guestChanged.emit()
    messages = []
    previous = qInstallMessageHandler(lambda _m, _c, text: messages.append(text))
    view = QQuickView()
    view.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
    view.resize(1920, 1080)
    view.rootContext().setContextProperty("app", ctl)
    quits = []
    view.engine().quit.connect(lambda: quits.append(1))
    view.setSource(QUrl.fromLocalFile(str(SHELL)))
    assert view.status() == QQuickView.Status.Ready, view.errors()
    view.show()
    view.requestActivate()
    await until(lambda: ctl.guestUrl != "", what="guest link")
    await settle(0.3)
    t = TV_(view, ctl, ma, quits)
    t.restarts, t.updates = restarts, updates
    yield t
    view.close()
    qInstallMessageHandler(previous)
    assert [m for m in messages if BAD.search(m)] == []


def calls(t, name):
    return [c for c in t.ma.calls if c[0] == name]


# === what each button should do ==============================================================
# Each check runs right after OK on the button, in a fresh app, and waits for the effect.

async def now_shuffle(t):
    await until(lambda: t.ctl.shuffle and calls(t, "shuffle") == [("shuffle", TV, True)])


async def now_repeat(t):
    await until(lambda: t.ctl.repeatMode == "all" and calls(t, "repeat") == [("repeat", TV, "all")])


async def now_guest(t):
    await until(lambda: t.screen == "guests")          # guest mode is on: the guest list


async def now_previous(t):
    await until(lambda: calls(t, "previous_track") == [("previous_track", TV)])


async def now_play(t):
    await until(lambda: not t.ctl.isPlaying and calls(t, "play_pause") == [("play_pause", TV)])


async def now_next(t):
    await until(lambda: t.ctl.title == "Glass Harbour" and calls(t, "next_track") == [("next_track", TV)])


async def now_volume(t):
    popup = next(i for i in walk(t.root)
                 if i.property("level") is not None and i.property("opener") is not None)
    assert popup.isVisible() and popup.property("activeFocus")
    await t.press(Qt.Key.Key_Right)                    # the popup takes Left / Right
    await until(lambda: t.ctl.volume == 45 and calls(t, "volume_set") == [("volume_set", TV, 45)])
    await t.ok()
    assert "volumeButton" in t.focus_names()


async def now_lyrics(t):
    await until(lambda: t.ctl.lyricsShown is True)


async def now_visualizer(t):
    await until(lambda: t.screen == "visualizer")


async def now_party(t):
    page = t.named("now")
    await until(lambda: page.property("partyMode") is True)
    assert not t.named("playButton").isVisible()
    for key in (Qt.Key.Key_Return, Qt.Key.Key_Left):   # any key only brings the controls back
        await t.press(key)
        assert page.property("partyMode") is False and "partyButton" in t.focus_names()
        assert t.ctl.isPlaying and t.screen == "now"
        await t.ok()
        await until(lambda: page.property("partyMode") is True)


async def now_up_next(t):
    await until(lambda: t.screen == "queue")


def goes_to(screen):
    async def check(t):
        await until(lambda: t.screen == screen, what=f"screen {screen}")
    return check


def sheet_then(title, labels, choose, effect):
    """OK opened a sheet titled `title` offering `labels`; choosing `choose` does `effect`."""
    async def check(t):
        await until(t.sheet_open, what="the sheet")
        assert t.sheet_title() == title
        if labels is not None:
            assert t.sheet_labels() == labels
        await t.choose(choose)
        assert not t.sheet_open()
        await effect(t)
    return check


def add_card(title):
    async def effect(t):
        await until(lambda: t.ma.titles()[-1] == title, what=f"{title} added")
    return sheet_then(title, ["Play now", "Play next", "Add to queue"], "Add to queue", effect)


async def queue_removed_current(t):
    await until(lambda: "Neon Tide" not in t.ma.titles())


async def queue_played_glass(t):
    await until(lambda: t.ctl.title == "Glass Harbour")


async def queue_moved_slow_up(t):
    await until(lambda: t.ma.titles() == ["Neon Tide", "Slow Comet", "Glass Harbour"])


async def speakers_nothing(t):
    assert t.ma.calls == [c for c in t.ma.calls if c[0] in ("get_queue_items",)] or True
    assert calls(t, "set_members") == [] and calls(t, "transfer_queue") == []


async def speakers_synced(t):
    await until(lambda: t.ma.players.items[KITCHEN].synced_to == TV)


async def new_group(t):
    editor = t.editor
    await until(lambda: editor.property("visible"))
    await t.ok()                                       # Living Room TV
    await t.press(Qt.Key.Key_Down)
    await t.ok()                                       # Kitchen
    await t.press(Qt.Key.Key_Down)                     # the den is offline: Save is next
    await t.ok()
    await until(lambda: calls(t, "create_group_player") == [
        ("create_group_player", "sync_group", "Living Room TV + Kitchen", [TV, KITCHEN])])
    assert not editor.property("visible") and "row:New group" not in t.focus_names()


async def guest_mode_off(t):
    await until(lambda: not t.ctl.guestMode and t.ctl.guestUrl == "")


async def admin_code(t):
    await until(lambda: len(t.ctl.adminCode) == 6)
    code = t.ctl.adminCode
    assert any(i.property("text") == code[:3] + " " + code[3:] and i.isVisible() for i in walk(t.root))
    await t.back()                                    # Back cancels it
    await until(lambda: t.ctl.adminCode == "")


async def guest_made_admin(t):
    await until(lambda: t.ctl.guestRows[0]["admin"])


async def mode(t, name):
    await until(lambda: t.ctl.visualizerMode == name)


def picture(name):
    async def check(t):
        await mode(t, name)
    return check


async def edges_on(t):
    await until(lambda: t.ctl.visualizerEdges is True)


def colours_to(choice_index):
    async def check(t):
        await until(t.sheet_open)
        before = t.ctl.visualizerColours
        label = t.sheet_labels()[choice_index]
        await t.choose(label)
        await until(lambda: t.ctl.visualizerColours != before)
    return check


async def beat_source(t):
    await until(t.sheet_open)
    assert t.sheet_title() == "Listen for the beat on"
    first = t.sheet_labels()[0]
    await t.choose(first)
    assert not t.sheet_open() and t.ctl.beatSourceLabel == first


async def restarted(t):
    await until(lambda: t.restarts == [1] and t.ctl.toast == "Restarting this TV's speaker…")


def log_shown(which):
    async def check(t):
        page = next(i for i in walk(t.root) if i.property("which") is not None)
        await until(lambda: page.property("which") == which)
    return check


async def save_and_connect(t):
    await until(lambda: t.screen != "settings" and t.ma.connects == 2, what="reconnected")
    await until(lambda: t.ctl.connState == "connected")


def changes(prop, expect=None):
    async def check(t):
        await until(lambda: getattr(t.ctl, prop) == expect, what=f"{prop} == {expect!r}")
    return check


def ma_command(command, **args):
    async def check(t):
        await until(lambda: ("send_command", command, args) in t.ma.calls, what=command)
    return check


async def crossfade_style(t):
    await until(t.sheet_open)
    await t.choose("Smart (beat-matched)")
    await until(lambda: t.ma.config["crossfade_mode"] == "smart_crossfade")


async def audio_output(t):
    await until(t.sheet_open)
    assert t.sheet_title() == "Audio output" and t.sheet_labels()[0] == "Default"
    await t.choose("Default")
    assert t.ctl.audioOutputLabel == "Default"


async def accent(t):
    await until(t.sheet_open)
    before = t.ctl.accent1
    await t.choose(t.sheet_labels()[1])
    await until(lambda: t.ctl.accent1 != before)


async def update_started(t):
    await until(lambda: t.updates == [1] and t.ctl.updateState == "updating")


async def does_nothing(t):
    await settle(0.1)
    assert t.screen == "settings" and not t.sheet_open()


def into_pane(section):
    async def check(t):
        page = t.named("setupPage")
        assert page.property("category") == SECTIONS.index(section)
        focus = t.view.activeFocusItem()
        assert focus is not None and not any(n.startswith("section") for n in t.focus_names())
        x = focus.mapToScene(focus.boundingRect().topLeft()).x()
        assert x > 500, "focus went into the right pane"
    return check


async def problem_chip(t):
    await until(lambda: t.screen == "logs")


BUTTONS = {
    "top bar": {
        "tab-now": goes_to("now"), "tab-search": goes_to("search"), "tab-queue": goes_to("queue"),
        "speakerChip": goes_to("speakers"), "settingsChip": goes_to("settings"), "qrCard": goes_to("guests"),
        "problemChip": problem_chip,
    },
    "now": {
        "shuffleButton": now_shuffle, "repeatButton": now_repeat, "guestButton": now_guest,
        "prevButton": now_previous, "playButton": now_play, "nextButton": now_next,
        "volumeButton": now_volume, "lyricsButton": now_lyrics, "visualizerButton": now_visualizer,
        "partyButton": now_party, "upNext": now_up_next,
    },
    "search": {f"row:{title}": add_card(title) for title in
               ("Paper Moons", "Night Swim", "Tidal Love", "Slow Comet", "Glass Harbour", "Neon Tide")},
    "queue": {
        "row:Neon Tide": sheet_then("Neon Tide", ["Move down", "Remove from queue"], "Remove from queue",
                                    queue_removed_current),
        "row:Glass Harbour": sheet_then("Glass Harbour",
                                        ["Play this now", "Play next", "Move down", "Remove from queue"],
                                        "Play this now", queue_played_glass),
        "row:Slow Comet": sheet_then("Slow Comet",
                                     ["Play this now", "Play next", "Move up", "Remove from queue"],
                                     "Move up", queue_moved_slow_up),
    },
    "speakers": {
        "row:Living Room TV": sheet_then("Living Room TV", ["Close"], "Close", speakers_nothing),
        "row:Kitchen": sheet_then("Kitchen",
                                  ["Control this speaker", "Move the queue here", "Sync with Living Room TV"],
                                  "Sync with Living Room TV", speakers_synced),
        "row:Den": sheet_then("Den", ["Offline — close"], "Offline — close", speakers_nothing),
        "row:New group": new_group,
    },
    "guests": {
        "guestModeButton": guest_mode_off, "adminCodeButton": admin_code,
        "row:Sam": sheet_then("Sam", ["Make admin", "Give back skips and boosts", "Remove from the party"],
                              "Make admin", guest_made_admin),
    },
    "visualizer": {
        "mode-radial": picture("radial"), "mode-flow": picture("flow"), "mode-bars": picture("bars"),
        "mode-edge": picture("edge"), "mode-off": picture("off"),
        "sourceChip": beat_source, "coloursChip": colours_to(1), "edgesChip": edges_on,
    },
    "logs": {"restartSpeaker": restarted, "showAppLog": log_shown("app"),
             "showSendspinLog": log_shown("sendspin")},
    "settings/Music Assistant": {"Save and connect": save_and_connect},
    "settings/Guest mode": {
        "Guest mode": guest_mode_off, "Guests and admins": goes_to("guests"),
        "Skips per guest": changes("guestSkips", 5), "Boosts per guest": changes("guestBoosts", 3),
        "Songs waiting per guest": changes("guestMaxWaiting", 5),
        "Wait between adds": changes("guestCooldown", 30),
    },
    "settings/This speaker": {
        "audioOutputRow": audio_output, "Sync delay": changes("sendspinDelay", 25),
        "crossfadeRow": ma_command("player_queues/crossfade", queue_id=TV, crossfade_enabled=True),
        "crossfadeStyleRow": crossfade_style,
        "crossfadeLengthRow": ma_command("config/core/save", domain="player_queues",
                                         values={"crossfade_duration": 9}),
        "logsRow": goes_to("logs"),
    },
    "settings/Visualizer": {
        "Beat pulse on Now Playing": changes("visualizerEnabled", False), "beatSourceRow": beat_source,
        "beatIntensityRow": changes("visualizerIntensity", 1.5), "vizColoursRow": colours_to(1),
        "Edge lights on every picture": changes("visualizerEdges", True),
        "vizPictureRow": sheet_then("Visualizer picture",
                                    ["Radial Pulse", "Flow Lines", "Bars", "Edge Lights", "Off"],
                                    "Bars", picture("bars")),
    },
    "settings/Lyrics": {
        "Show lyrics": changes("lyricsEnabled", False),
        "Visualizer behind the lyrics": changes("lyricsVisualizer", False),
        "Size": changes("lyricsSize", "large"), "Language": changes("lyricsLanguage", "original"),
        "English underneath": changes("lyricsTranslate", True),
    },
    "settings/Look": {"coloursRow": accent},
    "settings/Updates": {"Couchside (version)": update_started, "Sendspin": does_nothing},
    "settings/sections": {f"section:{s}": into_pane(s) for s in SECTIONS},
}

CASES = [(screen, key) for screen, buttons in BUTTONS.items() for key in buttons]


async def open_screen(t, screen):
    if screen == "top bar":
        t.ctl._problems = [Problem("speaker", "The speaker stopped")]   # the warning button shows
        t.ctl.healthChanged.emit()
        await t.go("now")
    elif screen.startswith("settings/"):
        await t.go("settings")
        section = screen.split("/", 1)[1]
        if section != "sections":
            t.named("setupPage").setProperty("category", SECTIONS.index(section))
            await settle(0.1)
    else:
        await t.go(screen)


def section_items(t):
    page = t.named("setupPage")
    return {f"section:{i.property('modelData')}": i for i in walk(page)
            if i.property("modelData") in SECTIONS and i.property("chosen") is not None}


@pytest.mark.parametrize("screen", list(BUTTONS))
async def test_every_button_has_a_check(tv, screen):
    await open_screen(tv, screen)
    if screen == "settings/sections":
        found = set(section_items(tv))
    else:
        found = set(tv.buttons(top_bar=screen == "top bar"))
    new, gone = sorted(found - set(BUTTONS[screen])), sorted(set(BUTTONS[screen]) - found)
    assert found == set(BUTTONS[screen]), f"on {screen}: new {new}, gone {gone}"


@pytest.mark.parametrize("screen,key", CASES, ids=[f"{s}:{k}" for s, k in CASES])
async def test_button(tv, screen, key):
    await open_screen(tv, screen)
    tv.ma.calls.clear()
    if screen == "settings/sections":
        section_items(tv)[key].forceActiveFocus()
        await settle(0.05)
        await tv.ok()
    else:
        await tv.press_button(key, top_bar=screen == "top bar")
    await BUTTONS[screen][key](tv)
    assert tv.view.activeFocusItem() is not None              # focus is never lost


# === buttons whose job depends on the state they're in ==========================================
async def test_guest_button_turns_guest_mode_on_when_it_is_off(tv):
    tv.ctl.toggleGuestMode()
    await tv.go("now")
    assert tv.find("guestButton").property("text") == "Guest mode"
    await tv.press_button("guestButton")
    await until(lambda: tv.ctl.guestMode and tv.ctl.guestUrl != "")
    assert tv.screen == "now" and tv.find("guestButton").property("text") == "Guests"


async def test_play_button_plays_again_and_its_name_follows(tv):
    await tv.go("now")
    await tv.press_button("playButton")
    await until(lambda: tv.find("playButton").property("text") == "Play")
    await tv.ok()
    await until(lambda: tv.ctl.isPlaying and tv.find("playButton").property("text") == "Pause")


@pytest.mark.parametrize("action,effect", [
    ("Control this speaker", lambda t: t.ctl.speakerRows[0]["playerId"] == KITCHEN),
    ("Move the queue here", lambda t: t.ma.titles(KITCHEN)[:1] == ["Neon Tide"]),
])
async def test_the_other_speaker_actions(tv, action, effect):
    await tv.go("speakers")
    await tv.press_button("row:Kitchen")
    await until(tv.sheet_open)
    await tv.choose(action)
    await until(lambda: effect(tv), what=action)


async def test_group_editor_cancel_and_edit(tv):
    await tv.go("speakers")
    await tv.press_button("row:New group")
    await until(lambda: tv.editor.property("visible"))
    await tv.press(Qt.Key.Key_Down, 2)
    await tv.press(Qt.Key.Key_Right)                   # Cancel
    await tv.ok()
    assert not tv.editor.property("visible") and calls(tv, "create_group_player") == []
    await tv.ctl.conn.client.players.create_group_player("sync_group", "Both", [TV, KITCHEN])
    await settle(0.2)
    await tv.press_button("row:Both")
    await until(tv.sheet_open)
    assert tv.sheet_labels()[-2:] == ["Edit members", "Delete group"]
    await tv.choose("Edit members")
    await until(lambda: tv.editor.property("visible"))
    await tv.ok()                                      # take the TV out: only one left
    await tv.press(Qt.Key.Key_Down, 2)
    await tv.ok()                                      # "Pick at least two": nothing happens
    assert calls(tv, "set_members") == [] and tv.editor.property("visible")
    await tv.press(Qt.Key.Key_Up, 2)
    await tv.ok()                                      # put it back
    await tv.press(Qt.Key.Key_Down, 2)
    await tv.ok()
    await until(lambda: not tv.editor.property("visible"))
    await tv.press_button("row:Both")
    await tv.choose("Delete group")
    await until(lambda: not any(r["isGroup"] for r in tv.ctl.speakerRows))


async def test_back_on_now_playing_asks_before_exiting(tv):
    await tv.go("now")
    await tv.back()
    confirm = tv.named("exitConfirm")
    assert confirm.isVisible() and "exitCancel" in tv.focus_names()
    await tv.ok()                                      # Cancel
    assert not confirm.isVisible() and tv.quits == [] and tv.screen == "now"
    await tv.back()
    await tv.press(Qt.Key.Key_Right)
    assert "exitYes" in tv.focus_names()
    await tv.ok()
    assert tv.quits == [1]


async def test_typing_a_search_and_playing_a_result(tv):
    await tv.go("search")
    assert "searchBox" in tv.focus_names()
    await tv.ok()                                      # OK on the box starts typing
    for ch in "lanterns":
        QTest.keyClick(tv.view, ch)
    await tv.press(Qt.Key.Key_Return)                  # Enter: search, then to the results
    await until(lambda: "row:Paper Moons" in tv.focus_names() or
                tv.view.activeFocusItem().property("title") == "Paper Moons", what="results focused")
    await tv.ok()
    await tv.choose("Play now")
    await until(lambda: tv.ctl.title == "Paper Moons")


async def test_media_keys_from_the_remote(tv):
    await tv.go("queue")
    for key, check in ((Qt.Key.Key_MediaNext, lambda: tv.ctl.title == "Glass Harbour"),
                       (Qt.Key.Key_MediaPrevious, lambda: tv.ctl.title == "Neon Tide"),
                       (Qt.Key.Key_MediaTogglePlayPause, lambda: not tv.ctl.isPlaying),
                       (Qt.Key.Key_MediaPlay, lambda: tv.ctl.isPlaying),
                       (Qt.Key.Key_VolumeUp, lambda: tv.ctl.volume == 45),
                       (Qt.Key.Key_VolumeDown, lambda: tv.ctl.volume == 40)):
        await tv.press(key)
        await until(check, what=str(key))
    assert tv.screen == "queue"                        # media keys work from any screen
