"""The app's recent log lines, kept in memory for the Logs screen."""

import logging

from couchside.core.logbuffer import RingHandler


def test_keeps_the_last_lines_formatted():
    handler = RingHandler(maxlen=3)
    log = logging.getLogger("test.logbuffer")
    log.addHandler(handler)
    log.setLevel(logging.INFO)
    try:
        for i in range(5):
            log.info("line %d", i)
        log.warning("careful")
    finally:
        log.removeHandler(handler)
    lines = handler.lines()
    assert len(lines) == 3
    assert lines[-1].endswith("WARNING test.logbuffer: careful")
    assert "line 4" in lines[-2] and "line 0" not in "\n".join(lines)
