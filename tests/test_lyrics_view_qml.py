"""Loads the real LyricsView.qml offscreen: the current line never wraps past two rows."""

import time
from pathlib import Path

import pytest

pytest.importorskip("PySide6.QtQuick")
from PySide6.QtCore import QCoreApplication, QUrl  # noqa: E402
from PySide6.QtQuick import QQuickView  # noqa: E402

QML = Path(__file__).parents[1] / "src/couchside/ui/qml/LyricsView.qml"
LONG = ("ਨੀ ਬੋਤਲੇ Azul ਦੀਏ ਨਖਰਾ ਆ ਜਿਵੇਂ Don Julio forty two and the night keeps going on and on "
        "until the morning light comes back around again")


def pump(seconds=0.2):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        QCoreApplication.processEvents()
        time.sleep(0.005)


@pytest.fixture
def view(qt_app):
    v = QQuickView()
    v.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
    v.resize(1920, 600)
    v.setSource(QUrl.fromLocalFile(str(QML)))
    assert v.status() == QQuickView.Status.Ready, v.errors()
    v.show()
    yield v
    v.close()


def first_line(root):
    from PySide6.QtCore import QMetaObject, Q_ARG, Q_RETURN_ARG
    from PySide6.QtQuick import QQuickItem
    return QMetaObject.invokeMethod(root, "itemAtIndex", Q_RETURN_ARG(QQuickItem), Q_ARG(int, 0))


def test_long_current_line_fits_two_rows(view):
    root = view.rootObject()
    root.setProperty("refWidth", 1920)
    root.setProperty("lines", [{"t": 0.0, "text": LONG}, {"t": 10.0, "text": "next"}])
    root.setProperty("position", 1.0)
    pump(0.6)
    item = first_line(root)
    assert item is not None and item.property("current") is True
    assert item.property("lineCount") <= 2
    assert not item.property("truncated")  # shrunk to fit, not cut off


def test_short_line_keeps_full_size(view):
    root = view.rootObject()
    root.setProperty("refWidth", 1920)
    root.setProperty("size", "large")
    root.setProperty("lines", [{"t": 0.0, "text": "I will shelter you"}])
    root.setProperty("position", 1.0)
    pump(0.6)
    item = first_line(root)
    assert abs(item.property("font").pixelSize() - 1920 * 0.06) < 2


def test_sizes_and_centering(view):
    root = view.rootObject()
    root.setProperty("refWidth", 1920)
    root.setProperty("lines", [{"t": 0.0, "text": "short"}])
    root.setProperty("position", 1.0)
    sizes = {}
    for size in ("small", "medium", "large"):
        root.setProperty("size", size)
        pump(0.5)
        sizes[size] = first_line(root).property("font").pixelSize()
    assert sizes["small"] < sizes["medium"] < sizes["large"]
    assert abs(sizes["medium"] - 1920 * 0.045) < 2
    from PySide6.QtQml import QQmlEngine, QQmlExpression
    line = first_line(root)
    expr = QQmlExpression(QQmlEngine.contextForObject(line), line,
                          "horizontalAlignment === Text.AlignHCenter")
    assert expr.evaluate()[0] is True


def test_translation_shows_under_the_line(view):
    root = view.rootObject()
    root.setProperty("refWidth", 1920)
    root.setProperty("lines", [{"t": 0.0, "text": "hae, ni old school jihi e", "sub": "Hey, not like old school"}])
    root.setProperty("position", 1.0)
    pump(0.5)
    line = first_line(root)
    sub = [c for c in line.childItems() if c.property("text") == "Hey, not like old school"]
    assert sub and sub[0].property("visible")
    assert line.property("bottomPadding") > 0
    assert sub[0].property("font").pixelSize() < line.property("font").pixelSize()


def test_text_from_outside_is_never_rich_text(view):
    root = view.rootObject()
    root.setProperty("lines", [{"t": 0.0, "text": "<img src=http://a.b/c><b>x</b>", "sub": "<h1>big</h1>"}])
    root.setProperty("position", 1.0)
    pump(0.4)
    from PySide6.QtQml import QQmlEngine, QQmlExpression
    line = first_line(root)
    ctx = QQmlEngine.contextForObject(line)
    assert QQmlExpression(ctx, line, "textFormat === Text.PlainText").evaluate()[0] is True
    sub = [c for c in line.childItems() if c.property("text") == "<h1>big</h1>"][0]
    assert QQmlExpression(ctx, sub, "textFormat === Text.PlainText").evaluate()[0] is True


def line_at(root, i):
    from PySide6.QtCore import QMetaObject, Q_ARG, Q_RETURN_ARG
    from PySide6.QtQuick import QQuickItem
    return QMetaObject.invokeMethod(root, "itemAtIndex", Q_RETURN_ARG(QQuickItem), Q_ARG(int, i))


def test_a_line_keeps_its_size_and_wrapping_when_it_becomes_current(view):
    """Text that changes size while you read it is hard to follow: every line is laid out
    once, at the size it has when sung; only its scale and brightness change."""
    root = view.rootObject()
    root.setProperty("refWidth", 1920)
    root.setProperty("lines", [{"t": 0.0, "text": "first line"},
                               {"t": 10.0, "text": "So as long as you're with me you're not alone"},
                               {"t": 20.0, "text": "third"}])
    root.setProperty("position", 1.0)
    pump(0.6)
    nxt = line_at(root, 1)
    before = (nxt.property("font").pixelSize(), nxt.property("lineCount"), nxt.height())
    assert nxt.property("current") is False and nxt.scale() < 1.0
    root.setProperty("position", 11.0)
    pump(0.05)   # mid-transition: nothing re-laid out
    assert (nxt.property("font").pixelSize(), nxt.property("lineCount"), nxt.height()) == before
    pump(0.6)
    assert nxt.property("current") is True and abs(nxt.scale() - 1.0) < 0.01
    assert (nxt.property("font").pixelSize(), nxt.property("lineCount"), nxt.height()) == before
