"""Loads the real ActionSheet.qml offscreen (focus fallback, double-press guard)."""

import time
from pathlib import Path

import pytest

pytest.importorskip("PySide6.QtQuick")
from PySide6.QtCore import QCoreApplication, QUrl  # noqa: E402
from PySide6.QtQuick import QQuickView  # noqa: E402

QML_DIR = Path(__file__).parents[1] / "src/couchside/ui/qml"
HARNESS = Path(__file__).parent / "qml/SheetHarness.qml"


def pump(seconds=0.05):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        QCoreApplication.processEvents()
        time.sleep(0.005)


@pytest.fixture
def harness(qt_app):
    view = QQuickView()
    view.engine().addImportPath(str(QML_DIR))
    # The harness sits outside the qml dir; make ActionSheet resolvable as a type.
    view.engine().rootContext().setContextProperty("app", None)
    src = HARNESS.read_text().replace("import QtQuick", f'import QtQuick\nimport "{QML_DIR.as_uri()}"', 1)
    tmp = HARNESS.with_name("_SheetHarness_run.qml")
    tmp.write_text(src)
    view.setSource(QUrl.fromLocalFile(str(tmp)))
    assert view.status() == QQuickView.Status.Ready, view.errors()
    view.show()
    pump()
    yield view.rootObject()
    view.close()
    tmp.unlink(missing_ok=True)


def call(obj, name, *args):
    from PySide6.QtCore import QMetaObject, Q_ARG, Q_RETURN_ARG  # noqa: F401
    return QMetaObject.invokeMethod(obj, name)


def sheet(root):
    return root.findChild(object, "sheet")


def test_focus_lost_signal_when_opener_destroyed(harness):
    call(harness, "makeOpener")
    call(harness, "openSheet")
    pump(0.4)
    harness.property("opener").deleteLater()
    from PySide6.QtCore import QEvent
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
    pump()
    assert harness.property("opener") is None  # the row was rebuilt
    call(sheet(harness), "close")
    pump()
    assert harness.property("lostCount") == 1


def test_no_focus_lost_when_opener_alive(harness):
    call(harness, "makeOpener")
    call(harness, "openSheet")
    pump(0.4)
    call(sheet(harness), "close")
    pump()
    assert harness.property("lostCount") == 0


def test_ok_right_after_open_is_ignored(harness):
    # A double press on the opener must not run the sheet's first action.
    from PySide6.QtCore import QMetaObject, Q_ARG
    call(harness, "makeOpener")
    call(harness, "openSheet")
    QMetaObject.invokeMethod(sheet(harness), "run", Q_ARG("QVariant", 0))
    pump()
    assert list(harness.property("ran").toVariant() if hasattr(harness.property("ran"), "toVariant")
                else harness.property("ran")) == []
    pump(0.4)
    QMetaObject.invokeMethod(sheet(harness), "run", Q_ARG("QVariant", 0))
    pump()
    ran = harness.property("ran")
    ran = ran.toVariant() if hasattr(ran, "toVariant") else ran
    assert list(ran) == ["first"]
