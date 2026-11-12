"""`couchside-sendspin`: keep the bundled Sendspin daemon running, logging to a file.

Started at login by the Background portal (see autostart.py) and by the UI if
it is not already running. A file lock keeps it single-instance. The daemon's command is
rebuilt from Settings every couple of seconds: when it changes (player name, audio
output, delay) the daemon restarts. A control file asks the supervisor to exit (before
an update relaunches the new version).
"""

from __future__ import annotations

import fcntl
import re
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
    argv = [sys.executable, "-c", DAEMON_ENTRY, "daemon",
            "--settings-dir", str(sendspin_dir), "--port", str(settings.sendspin_port),
            "--name", settings.player_name]
    if settings.sendspin_audio_device:
        argv += ["--audio-device", settings.sendspin_audio_device]
    if settings.sendspin_delay_ms:
        argv += ["--output-delay-ms", str(int(settings.sendspin_delay_ms))]
    return argv


AUDIO_DEVICES_ARGV = [sys.executable, "-c", DAEMON_ENTRY, "audio-devices", "list"]
_DEVICE_LINE = re.compile(r"^\s*\[\d+\]\s+(.+?)\s*$")


def parse_audio_devices(text: str) -> list[str]:
    """Device names from `sendspin audio-devices list` (the default entry is left out:
    "Default" in Settings means no --audio-device at all)."""
    names = []
    for line in text.splitlines():
        m = _DEVICE_LINE.match(line)
        if m:
            name = m.group(1)
            if name == "default" or name.endswith("(default)"):
                continue
            names.append(name)
    return names


def control_path() -> Path:
    return state_dir() / "sendspin.control"


def request_exit(path: Path | None = None) -> None:
    """Ask the running supervisor (any sandbox instance) to stop its daemon and exit."""
    path = path or control_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("exit")


def _exit_requested(path: Path | None) -> bool:
    if path is None:
        return False
    try:
        wanted = path.read_text().strip() == "exit"
    except OSError:
        return False
    if wanted:
        path.unlink(missing_ok=True)
    return wanted


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


def supervise(argv: list[str] | Callable[[], list[str]], log_file: Path, restart_delay: float = 3.0,
              max_delay: float = 60.0, max_log_bytes: int = MAX_LOG_BYTES,
              sleep: Callable[[float], None] = time.sleep,
              healthy_after: float = 60.0, poll: float = 2.0,
              control_file: Path | None = None) -> int:
    """Run the daemon, restarting it after a non-zero exit with a growing delay (reset
    after a run of `healthy_after` seconds). `argv` may be a function: it is called every
    `poll` seconds and the daemon restarts at once when the command changes. Returns on
    clean exit, SIGTERM/SIGINT, or an exit request in `control_file`."""
    stopping = False
    child: subprocess.Popen | None = None
    make = argv if callable(argv) else (lambda: argv)

    def on_term(signum, _frame):
        nonlocal stopping
        stopping = True
        if child is not None and child.poll() is None:
            child.send_signal(signum)

    def stop_child():
        child.terminate()
        try:
            child.wait(timeout=10)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()

    old_term = signal.signal(signal.SIGTERM, on_term)
    old_int = signal.signal(signal.SIGINT, on_term)
    if control_file is not None:
        control_file.unlink(missing_ok=True)  # an old request is not for this run
    delay = restart_delay
    current = make()
    try:
        while not stopping:
            prepare_log(log_file, max_log_bytes)
            started = time.monotonic()
            changed = False
            with open(log_file, "a", buffering=1) as out:
                child = subprocess.Popen(current, stdout=out, stderr=subprocess.STDOUT,
                                         stdin=subprocess.DEVNULL,
                                         preexec_fn=_die_with_parent)
                if stopping:  # signal landed while starting: pass it on
                    child.terminate()
                while True:
                    try:
                        rc = child.wait(timeout=poll)
                        break
                    except subprocess.TimeoutExpired:
                        pass
                    if _exit_requested(control_file):
                        stopping = True
                        stop_child()
                        return 0
                    try:
                        wanted = make()
                    except Exception as e:  # unreadable settings: keep what runs
                        log.warning("can't rebuild the Sendspin command: %s", e)
                        continue
                    if wanted != current:
                        out.write("couchside-sendspin: settings changed, restarting the daemon\n")
                        current, changed = wanted, True
                        stop_child()
                        rc = None
                        break
            if changed:
                delay = restart_delay
                continue
            if rc == 0 or stopping:
                return 0 if stopping else rc
            if time.monotonic() - started >= healthy_after:
                delay = restart_delay
            with open(log_file, "a") as out:
                out.write(f"couchside-sendspin: daemon exited with {rc}, "
                          f"restarting in {delay:g}s\n")
            sleep(delay)
            delay = min(delay * 2, max_delay) if delay else 0
            try:
                current = make()
            except Exception:
                pass
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
        sendspin_dir = sendspin_settings_dir()
        sendspin_dir.mkdir(parents=True, exist_ok=True)
        path = log_path()
        prepare_log(path)

        def argv() -> list[str]:
            return build_daemon_argv(load_settings(), sendspin_dir)
        return supervise(argv, path, control_file=control_path())
    finally:
        lock.close()


if __name__ == "__main__":
    sys.exit(main())
