"""Loads the new building blocks offscreen: button focus and OK, icons, Up next, edge lights."""

import time
from pathlib import Path

import pytest

pytest.importorskip("PySide6.QtQuick")
from PySide6.QtCore import QCoreApplication, Qt, QUrl  # noqa: E402
from PySide6.QtQuick import QQuickView  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

HARNESS = Path(__file__).parent / "qml/BlocksHarness.qml"


def pump(seconds=0.2):
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


def child(view, name):
    from PySide6.QtQuick import QQuickItem
    item = view.rootObject().findChild(QQuickItem, name)
    assert item is not None, name
    return item


def test_button_ok_clicks_and_the_theme_loads(view):
    root = view.rootObject()
    button = child(view, "button")
    button.forceActiveFocus()
    pump(0.05)
    assert button.property("activeFocus") is True and button.property("lit") is True
    for key in (Qt.Key.Key_Return, Qt.Key.Key_Select):
        QTest.keyClick(view, key)
    pump(0.05)
    assert root.property("clicks") == 2
    assert child(view, "playButton").property("lit") is True   # play is white without focus
    assert button.width() < child(view, "playButton").width() <= 100  # small, play a little bigger


def test_every_icon_the_pages_use_has_a_shape(view):
    icon = child(view, "icon")
    paths = icon.property("paths")
    if hasattr(paths, "toVariant"):
        paths = paths.toVariant()
    used = set()
    import re
    for qml in (Path(__file__).parents[1] / "src/couchside/ui/qml").glob("*.qml"):
        text = qml.read_text()
        for line in text.splitlines():
            if re.search(r"^\s*(iconName|name):", line) and "Kirigami" not in line:
                line = re.sub(r'[=!]==? *"[^"]*"', "", line)   # comparisons are not icon names
                used.update(n for n in re.findall(r'"([a-z-]+)"', line))
    assert used and used <= set(paths), used - set(paths)


def test_up_next_hides_without_a_next_song_and_is_plain_text(view):
    chip = child(view, "upNext")
    assert chip.isVisible() is False
    chip.setProperty("title", "<b>Luna</b>")
    chip.setProperty("artist", "Bolier")
    pump(0.05)
    assert chip.isVisible() is True and chip.width() > 0
    texts = [c for c in chip.findChildren(object) if c.metaObject().className().startswith("QQuickText")]
    from PySide6.QtQml import QQmlEngine, QQmlExpression
    assert texts
    for t in texts:
        expr = QQmlExpression(QQmlEngine.contextForObject(t), t, "textFormat === Text.PlainText")
        assert expr.evaluate()[0] is True


def test_edge_lights_follow_the_pulse_and_change_colour_with_the_hue(view):
    lights = child(view, "lights")
    lights.setProperty("pulse", 0.0)
    quiet = lights.opacity()
    left = lights.property("leftColour").name()
    lights.setProperty("pulse", 1.0)
    lights.setProperty("hue", 0.9)
    assert lights.opacity() > quiet > 0
    assert lights.property("leftColour").name() != left
    assert lights.property("leftColour").name() != lights.property("rightColour").name()


def test_rows_cards_and_text_buttons_focus_and_activate(view):
    root = view.rootObject()
    row, card, pill = child(view, "row"), child(view, "card"), child(view, "pill")
    row.forceActiveFocus()
    pump(0.05)
    assert row.property("activeFocus") is True
    assert row.property("ink").name() != "#ffffff"       # focused: dark text on a white row
    QTest.keyClick(view, Qt.Key.Key_Return)
    pump(0.05)
    assert root.property("rowHits") == 1
    pill.forceActiveFocus()
    QTest.keyClick(view, Qt.Key.Key_Select)
    pump(0.05)
    assert root.property("clicks") == 10
    card.forceActiveFocus()
    pump(0.3)
    assert card.property("activeFocus") is True
    from PySide6.QtQml import QQmlEngine, QQmlExpression
    for item in (row, card, pill):
        texts = [c for c in item.findChildren(object) if c.metaObject().className().startswith("QQuickText")]
        assert texts
        for t in texts:
            expr = QQmlExpression(QQmlEngine.contextForObject(t), t,
                                  "textFormat === Text.PlainText && font.pixelSize >= 28")
            assert expr.evaluate()[0] is True, t.property("text")
