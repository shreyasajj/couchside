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
    root.setProperty("lines", [{"t": 0.0, "text": "I will shelter you"}])
    root.setProperty("position", 1.0)
    pump(0.6)
    item = first_line(root)
    assert abs(item.property("font").pixelSize() - 1920 * 0.06) < 2
