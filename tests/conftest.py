import os

import pytest


@pytest.fixture(scope="session")
def qt_app():
    """One QGuiApplication for every Qt test (offscreen, so it runs headless in CI)."""
    QtGui = pytest.importorskip("PySide6.QtGui")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QtGui.QGuiApplication.instance() or QtGui.QGuiApplication([])
