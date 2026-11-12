"""The remote's Back key, taken before any shortcut sees it.

Kirigami's page stack binds Back (StandardKey.Back) for its own navigation. With
Couchside's Back shortcut as well, Qt treats the key as ambiguous and rotates it between
the two, so presses got lost or popped pages behind Couchside's back. This filter claims
the key app-wide and runs Couchside's own Back logic (close overlays, go back, confirm exit).
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QEvent, QObject, Qt


class BackKeyFilter(QObject):
    def __init__(self, on_back: Callable[[], None]):
        super().__init__()
        self._on_back = on_back

    def eventFilter(self, obj, event) -> bool:  # noqa: N802 (Qt API)
        kind = event.type()
        if kind not in (QEvent.Type.ShortcutOverride, QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
            return False
        if event.key() != Qt.Key.Key_Back:
            return False
        if kind == QEvent.Type.ShortcutOverride:
            event.accept()  # deliver it as a key press, not to a shortcut
        elif kind == QEvent.Type.KeyPress and not event.isAutoRepeat():
            self._on_back()
        return True
