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
from typing import IO, Callable

from couchside.core.paths import sendspin_settings_dir, state_dir
from couchside.core.settings import AppSettings, load_settings

log = logging.getLogger(__name__)

MAX_LOG_BYTES = 1_000_000
DAEMON_ENTRY = "import sys; from sendspin.cli import main; sys.exit(main())"


def build_daemon_argv(settings: AppSettings, sendspin_dir: Path) -> list[str]:
    # sendspin has no __main__ module; call its console-script entry point.
    # The explicit app ("daemon") must come right after the program name.
    return [sys.executable, "-c", DAEMON_ENTRY, "daemon",
            "--settings-dir", str(sendspin_dir), "--port", str(settings.sendspin_port),
            "--name", settings.player_name]


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


def _die_with_parent() -> None:
    """In the child: get SIGTERM if the supervisor dies, so no orphan keeps the port."""
    try:
        import ctypes

        PR_SET_PDEATHSIG = 1
        ctypes.CDLL(None, use_errno=True).prctl(PR_SET_PDEATHSIG, signal.SIGTERM)
    except Exception:
        pass  # not Linux, or no libc prctl: best effort


def supervise(argv: list[str], log_file: Path, restart_delay: float = 3.0,
              max_delay: float = 60.0, max_log_bytes: int = MAX_LOG_BYTES,
              sleep: Callable[[float], None] = time.sleep,
              healthy_after: float = 60.0) -> int:
    """Run argv, restarting it after a non-zero exit with a growing delay (reset after
    a run of `healthy_after` seconds). Returns on clean exit or SIGTERM/SIGINT."""
    stopping = False
    child: subprocess.Popen | None = None

    def on_term(signum, _frame):
        nonlocal stopping
        stopping = True
        if child is not None and child.poll() is None:
            child.send_signal(signum)

    old_term = signal.signal(signal.SIGTERM, on_term)
    old_int = signal.signal(signal.SIGINT, on_term)
    delay = restart_delay
    try:
        while not stopping:
            prepare_log(log_file, max_log_bytes)
            started = time.monotonic()
            with open(log_file, "a", buffering=1) as out:
                child = subprocess.Popen(argv, stdout=out, stderr=subprocess.STDOUT,
                                         stdin=subprocess.DEVNULL,
                                         preexec_fn=_die_with_parent)
                if stopping:  # signal landed while starting: pass it on
                    child.terminate()
                rc = child.wait()
            if rc == 0 or stopping:
                return 0 if stopping else rc
            if time.monotonic() - started >= healthy_after:
                delay = restart_delay
            with open(log_file, "a") as out:
                out.write(f"couchside-sendspin: daemon exited with {rc}, "
                          f"restarting in {delay:g}s\n")
            sleep(delay)
            delay = min(delay * 2, max_delay) if delay else 0
        return 0
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
