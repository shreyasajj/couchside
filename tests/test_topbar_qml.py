"""The top bar with a remote: where focus lands, how it moves, what OK opens."""

import time
from pathlib import Path

import pytest

pytest.importorskip("PySide6.QtQuick")
from PySide6.QtCore import QCoreApplication, QMetaObject, Qt, QUrl  # noqa: E402
from PySide6.QtQuick import QQuickItem, QQuickView  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

HARNESS = Path(__file__).parent / "qml/TopBarHarness.qml"


def pump(seconds=0.05):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        QCoreApplication.processEvents()
        time.sleep(0.005)


@pytest.fixture
def view(qt_app):
    v = QQuickView()
    v.setSource(QUrl.fromLocalFile(str(HARNESS)))
    assert v.status() == QQuickView.Status.Ready, v.errors()
    v.show()
    v.requestActivate()
    pump(0.1)
    yield v
    v.close()


def items(item):
    for c in item.childItems():
        yield c
        yield from items(c)


def named(view, name):
    found = [i for i in items(view.rootObject()) if i.objectName() == name]
    assert found, name
    return found[0]


def focused(view):
    item = view.activeFocusItem()
    while item is not None and not item.objectName():
        item = item.parentItem()
    return item.objectName() if item is not None else ""


def press(view, key, times=1):
    for _ in range(times):
        QTest.keyClick(view, key)
    pump()


def went(view):
    w = view.rootObject().property("went")
    return list(w.toVariant() if hasattr(w, "toVariant") else w)


def test_focus_lands_on_the_current_tab_and_moves_without_wrapping(view):
    bar = named(view, "bar")
    QMetaObject.invokeMethod(bar, "focusCurrent")
    pump()
    assert focused(view) == "tab-queue"
    press(view, Qt.Key.Key_Left, 5)
    assert focused(view) == "tab-now"                 # stops at the first tab
    press(view, Qt.Key.Key_Right, 3)
    assert focused(view) == "speakerChip"             # straight after the three tabs
    press(view, Qt.Key.Key_Return)
    assert went(view) == ["speakers"]
    press(view, Qt.Key.Key_Right, 5)
    assert focused(view) == "settingsChip"            # stops at the last one


def test_ok_on_a_tab_opens_it_and_down_leaves_the_bar(view):
    root = view.rootObject()
    bar = named(view, "bar")
    QMetaObject.invokeMethod(bar, "focusCurrent")
    press(view, Qt.Key.Key_Left)
    assert focused(view) == "tab-search"
    press(view, Qt.Key.Key_Select)
    assert went(view) == ["search"]
    press(view, Qt.Key.Key_Up)
    assert focused(view) == "tab-search"              # nothing above the bar
    press(view, Qt.Key.Key_Down)
    assert root.property("downs") == 1


def test_tabs_can_be_fewer(view):
    bar = named(view, "bar")
    bar.setProperty("tabs", ["now", "queue"])
    pump()
    QMetaObject.invokeMethod(bar, "focusCurrent")
    press(view, Qt.Key.Key_Right)
    assert focused(view) == "speakerChip"


def test_guest_mode_has_no_button_up_here_but_its_qr_card_opens_the_guest_list(view):
    """The Guest button lives on Now Playing's control row; the bar only shows the QR card."""
    bar = named(view, "bar")
    assert not [i for i in items(view.rootObject()) if i.objectName() == "guestChip"]
    bar.setProperty("guestMode", True)
    bar.setProperty("qrRows", ["101", "010", "101"])
    pump()
    named(view, "speakerChip").forceActiveFocus()
    press(view, Qt.Key.Key_Right)
    assert focused(view) == "settingsChip"
    press(view, Qt.Key.Key_Right)
    assert focused(view) == "qrCard"
    press(view, Qt.Key.Key_Return)
    assert went(view) == ["guests"]
    assert bar.property("qrWidth") > 0


@pytest.mark.parametrize("guest", [False, True])
def test_a_very_long_speaker_name_does_not_push_the_bar_off_screen(view, guest):
    bar = named(view, "bar")
    bar.setProperty("speakerName", "The Downstairs Living Room And Kitchen Speaker Group Number Two")
    bar.setProperty("guestMode", guest)
    pump()
    tabs, right = named(view, "tabRow"), named(view, "rightRow")
    tabs_right = tabs.mapToItem(bar, tabs.width(), 0).x()
    right_left = right.mapToItem(bar, 0, 0).x()
    right_right = right.mapToItem(bar, right.width(), 0).x()
    assert tabs_right <= right_left
    limit = 1920 - (named(view, "qrCard").width() + 48 if guest else 0)
    assert right_right <= limit


def test_tabs_move_left_rather_than_under_a_long_speaker_name(view):
    bar = named(view, "bar")
    view.rootObject().setProperty("width", 1650)   # less room than a TV: centring would collide
    bar.setProperty("speakerName", "The Downstairs Living Room And Kitchen Speaker Group Number Two")
    bar.setProperty("guestMode", True)
    bar.setProperty("qrRows", ["101", "010", "101"])
    pump()
    tabs, right = named(view, "tabRow"), named(view, "rightRow")
    assert tabs.mapToItem(bar, tabs.width(), 0).x() <= right.mapToItem(bar, 0, 0).x()
    assert tabs.mapToItem(bar, 0, 0).x() >= 0
