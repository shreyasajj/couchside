import asyncio

from couchside.sendspin.pairing import PairingEvent, parse_log_line, tail_log


def test_parse_code_line():
    line = "INFO:sendspin.daemon.daemon:Pairing required: enter pairing code 123 456 on the server."
    assert parse_log_line(line) == (PairingEvent.CODE, "123 456")


def test_parse_failed_line():
    line = "WARNING:sendspin.daemon.daemon:Pairing failed: code_mismatch"
    assert parse_log_line(line) == (PairingEvent.FAILED, "code_mismatch")


def test_parse_started_line():
    line = "INFO:sendspin.daemon.daemon:Starting Sendspin daemon: AbC-_123"
    assert parse_log_line(line) == (PairingEvent.STARTED, "AbC-_123")


def test_parse_other_line_none():
    assert parse_log_line("INFO:aiosendspin:connected to server") is None


async def _collect_until(events, n, timeout=2.0):
    async def wait():
        while len(events) < n:
            await asyncio.sleep(0.02)
    await asyncio.wait_for(wait(), timeout)


async def test_tail_reports_appended_lines(tmp_path):
    p = tmp_path / "sendspin.log"
    p.write_text("INFO:x:Pairing required: enter pairing code 999 on the server.\n")  # old: ignored
    events = []
    task = asyncio.create_task(tail_log(p, lambda e, v: events.append((e, v)), poll=0.02))
    await asyncio.sleep(0.1)
    with p.open("a") as fh:
        fh.write("INFO:x:Pairing required: enter pairing code 111 222 on the server.\n")
    await _collect_until(events, 1)
    task.cancel()
    assert events == [(PairingEvent.CODE, "111 222")]


async def test_tail_waits_for_missing_file(tmp_path):
    p = tmp_path / "later.log"
    events = []
    task = asyncio.create_task(tail_log(p, lambda e, v: events.append((e, v)), poll=0.02))
    await asyncio.sleep(0.1)
    p.write_text("INFO:x:Starting Sendspin daemon: id1\n")
    await _collect_until(events, 1)
    task.cancel()
    assert events == [(PairingEvent.STARTED, "id1")]


async def test_tail_handles_truncation(tmp_path):
    p = tmp_path / "sendspin.log"
    p.write_text("x" * 500 + "\n")
    events = []
    task = asyncio.create_task(tail_log(p, lambda e, v: events.append((e, v)), poll=0.02))
    await asyncio.sleep(0.1)
    p.write_text("INFO:x:Starting Sendspin daemon: id2\n")  # shorter than before → truncated
    await _collect_until(events, 1)
    task.cancel()
    assert events == [(PairingEvent.STARTED, "id2")]
