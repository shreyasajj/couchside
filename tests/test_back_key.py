"""The remote's Back key: Kirigami's page stack binds it too, and Qt then rotates the key
between the two shortcuts. An app-wide filter takes it before any shortcut does."""

import pytest

QtCore = pytest.importorskip("PySide6.QtCore")
from PySide6.QtCore import QEvent, QObject, Qt  # noqa: E402
from PySide6.QtGui import QKeyEvent  # noqa: E402

from couchside.ui.keys import BackKeyFilter  # noqa: E402


def key(kind, k):
    return QKeyEvent(kind, k, Qt.KeyboardModifier.NoModifier)


def test_back_key_calls_our_handler_once_and_no_shortcut(qt_app):
    calls = []
    f = BackKeyFilter(lambda: calls.append(1))
    target = QObject()
    override = key(QEvent.Type.ShortcutOverride, Qt.Key.Key_Back)
    override.ignore()
    assert f.eventFilter(target, override) is True and override.isAccepted()  # no shortcut runs
    assert f.eventFilter(target, key(QEvent.Type.KeyPress, Qt.Key.Key_Back)) is True
    assert f.eventFilter(target, key(QEvent.Type.KeyRelease, Qt.Key.Key_Back)) is True
    assert calls == [1]


def test_held_back_key_does_not_repeat(qt_app):
    calls = []
    f = BackKeyFilter(lambda: calls.append(1))
    repeat = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Back, Qt.KeyboardModifier.NoModifier, "", True)
    f.eventFilter(QObject(), repeat)
    assert calls == []


def test_other_keys_pass_through(qt_app):
    calls = []
    f = BackKeyFilter(lambda: calls.append(1))
    for k in (Qt.Key.Key_Escape, Qt.Key.Key_A, Qt.Key.Key_Left):
        assert f.eventFilter(QObject(), key(QEvent.Type.KeyPress, k)) is False
    assert calls == []
