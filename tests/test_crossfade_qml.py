"""Loads the real CrossfadeImage.qml offscreen and checks which picture ends up shown."""

import time
from pathlib import Path

import pytest

pytest.importorskip("PySide6.QtQuick")
from PySide6.QtCore import QCoreApplication, QUrl  # noqa: E402
from PySide6.QtGui import QColor, QImage  # noqa: E402
from PySide6.QtQml import QQmlComponent, QQmlEngine  # noqa: E402

QML = Path(__file__).parents[1] / "src/couchside/ui/qml/CrossfadeImage.qml"


def png(path: Path, colour: str) -> str:
    img = QImage(8, 8, QImage.Format.Format_RGB32)
    img.fill(QColor(colour))
    assert img.save(str(path))
    return QUrl.fromLocalFile(str(path)).toString()


def pump(until, timeout=3.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        QCoreApplication.processEvents()
        if until():
            return True
        time.sleep(0.01)
    return until()


@pytest.fixture
def fade(qt_app):
    engine = QQmlEngine()
    comp = QQmlComponent(engine, QUrl.fromLocalFile(str(QML)))
    item = comp.create()
    assert item is not None, comp.errors()
    item.setProperty("duration", 0)
    yield item
    item.deleteLater()
    engine.deleteLater()


def shown(item) -> str:
    return item.property("shownSource").toString() if hasattr(item.property("shownSource"), "toString") \
        else str(item.property("shownSource") or "")


def test_shows_new_source(fade, tmp_path):
    a = png(tmp_path / "a.png", "red")
    fade.setProperty("source", a)
    assert pump(lambda: shown(fade) == a)


def test_back_to_previous_source_shows_it(fade, tmp_path):
    # Next then Previous: A -> B -> A must end on A, not stay on B.
    a, b = png(tmp_path / "a.png", "red"), png(tmp_path / "b.png", "blue")
    fade.setProperty("source", a)
    assert pump(lambda: shown(fade) == a)
    fade.setProperty("source", b)
    assert pump(lambda: shown(fade) == b)
    fade.setProperty("source", a)
    assert pump(lambda: shown(fade) == a), shown(fade)


def test_failed_load_clears_old_picture(fade, tmp_path):
    a = png(tmp_path / "a.png", "red")
    fade.setProperty("source", a)
    assert pump(lambda: shown(fade) == a)
    fade.setProperty("source", QUrl.fromLocalFile(str(tmp_path / "missing.png")).toString())
    assert pump(lambda: not fade.property("hasImage")), shown(fade)
