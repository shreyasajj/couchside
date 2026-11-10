"""`couchside-sendspin`: keep the bundled Sendspin daemon running, logging to a file.

Started at login by the Background portal (see autostart.py) and by the UI if
it is not already running. A file lock keeps it single-instance.
"""

from __future__ import annotations

import fcntl
import logging
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import IO

from couchside.core.paths import sendspin_settings_dir, state_dir
from couchside.core.settings import AppSettings, load_settings

log = logging.getLogger(__name__)

MAX_LOG_BYTES = 1_000_000


def build_daemon_argv(settings: AppSettings, sendspin_dir: Path) -> list[str]:
    # The explicit app ("daemon") must come right after "sendspin".
    return [sys.executable, "-m", "sendspin", "daemon",
            "--settings-dir", str(sendspin_dir), "--name", settings.player_name]


def log_path() -> Path:
    return state_dir() / "sendspin.log"


def lock_path() -> Path:
    return state_dir() / "sendspin.lock"


def acquire_lock(path: Path) -> IO | None:
    """Return an open, exclusively locked file, or None if another instance holds it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fh = open(path, "a+")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fh.close()
        return None
    return fh


def prepare_log(path: Path, max_bytes: int = MAX_LOG_BYTES) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        if path.stat().st_size > max_bytes:
            path.write_text("")
    except FileNotFoundError:
        pass


def supervise(argv: list[str], log_file: Path, restart_delay: float = 3.0) -> int:
    """Run argv, restarting it after a non-zero exit. Returns on clean exit or SIGTERM."""
    stopping = False
    child: subprocess.Popen | None = None

    def on_term(signum, _frame):
        nonlocal stopping
        stopping = True
        if child is not None and child.poll() is None:
            child.send_signal(signum)

    old_term = signal.signal(signal.SIGTERM, on_term)
    old_int = signal.signal(signal.SIGINT, on_term)
    try:
        while True:
            with open(log_file, "a", buffering=1) as out:
                child = subprocess.Popen(argv, stdout=out, stderr=subprocess.STDOUT,
                                         stdin=subprocess.DEVNULL)
                rc = child.wait()
            if rc == 0 or stopping:
                return 0 if stopping else rc
            with open(log_file, "a") as out:
                out.write(f"couchside-sendspin: daemon exited with {rc}, restarting\n")
            time.sleep(restart_delay)
    finally:
        signal.signal(signal.SIGTERM, old_term)
        signal.signal(signal.SIGINT, old_int)


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    lock = acquire_lock(lock_path())
    if lock is None:
        log.info("couchside-sendspin already running")
        return 0
    try:
        settings = load_settings()
        sendspin_dir = sendspin_settings_dir()
        sendspin_dir.mkdir(parents=True, exist_ok=True)
        path = log_path()
        prepare_log(path)
        return supervise(build_daemon_argv(settings, sendspin_dir), path)
    finally:
        lock.close()


if __name__ == "__main__":
    sys.exit(main())
