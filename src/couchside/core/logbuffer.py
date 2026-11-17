"""The app's recent log lines, kept in memory so the Logs screen can show them (the app
logs to stderr, which nobody sees on a TV). Qt-free."""

from __future__ import annotations

import collections
import logging

FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


class RingHandler(logging.Handler):
    def __init__(self, maxlen: int = 500) -> None:
        super().__init__()
        self._lines: collections.deque[str] = collections.deque(maxlen=maxlen)
        self.setFormatter(logging.Formatter(FORMAT, "%H:%M:%S"))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._lines.append(self.format(record))
        except Exception:
            self.handleError(record)

    def lines(self) -> list[str]:
        return list(self._lines)


_installed: RingHandler | None = None


def install(maxlen: int = 500) -> RingHandler:
    """Keep the root logger's lines from now on (once)."""
    global _installed
    if _installed is None:
        _installed = RingHandler(maxlen)
        logging.getLogger().addHandler(_installed)
    return _installed


def recent() -> list[str]:
    return _installed.lines() if _installed is not None else []
