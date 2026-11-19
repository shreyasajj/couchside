"""`couchside-sendspin`: keep the bundled Sendspin daemon running, logging to a file.

Started at login by the Background portal (see autostart.py) and by the UI if
it is not already running. A file lock keeps it single-instance. The daemon's command is
rebuilt from Settings every couple of seconds: when it changes (player name, audio
output, delay) the daemon restarts. A control file asks the supervisor to exit (before
an update relaunches the new version).
"""

from __future__ import annotations

import fcntl
import functools
import hashlib
import json
import logging
import os
import re
import signal
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import IO

from couchside.core.audio_devices import SINK_PREFIX
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
    device = settings.sendspin_audio_device
    if device and device.startswith(SINK_PREFIX):
        # a PipeWire output: play through the pulse device, routed to that output (the
        # variable rides in the command, so changing it restarts the daemon like any option)
        argv = ["env", f"PULSE_SINK={device[len(SINK_PREFIX):]}", *argv, "--audio-device", "pulse"]
    elif device:
        argv += ["--audio-device", device]
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


def status_path() -> Path:
    return state_dir() / "sendspin.status"


@functools.lru_cache(maxsize=1)
def build_id() -> str:
    """Which build of Couchside this is: a hash of its Python files. The app compares it
    with the running supervisor's, so one left running from an older install (it lives on
    across app updates and restarts) is replaced instead of running old code."""
    root = Path(__file__).resolve().parents[1]
    h = hashlib.sha1()
    for p in sorted(root.rglob("*.py")):
        h.update(str(p.relative_to(root)).encode())
        h.update(p.read_bytes())
    return h.hexdigest()[:12]


def write_status(path: Path, state: str, exit_code: int | None = None, build: str | None = None,
                 pid: int | None = None, now: float | None = None) -> None:
    """What the supervisor is doing, for the app: "running", "restarting" (the daemon
    exited with `exit_code` and starts again after a delay) or "stopped"."""
    data = {"state": state, "exit_code": exit_code, "build": build, "pid": pid,
            "updated": time.time() if now is None else now}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data))
        tmp.replace(path)
    except OSError as e:
        log.warning("can't write the Sendspin status: %s", e)


def read_status(path: Path | None = None) -> dict | None:
    try:
        data = json.loads((path or status_path()).read_text())
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def supervisor_running(path: Path | None = None) -> bool:
    """Whether a supervisor holds the lock (any sandbox instance of this app)."""
    fh = acquire_lock(path or lock_path())
    if fh is None:
        return True
    fh.close()
    return False


def acquire_lock(path: Path) -> IO | None:
    """Return an open, exclusively locked file, or None if another instance holds it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fh = open(path, "a+")  # noqa: SIM115 - held open (and locked) for as long as we run
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
              control_file: Path | None = None,
              on_state: Callable[[str, int | None], None] | None = None) -> int:
    """Run the daemon, restarting it after a non-zero exit with a growing delay (reset
    after a run of `healthy_after` seconds). `argv` may be a function: it is called every
    `poll` seconds and the daemon restarts at once when the command changes. Returns on
    clean exit, SIGTERM/SIGINT, or an exit request in `control_file`. `on_state` hears
    ("running", None) whenever the daemon starts and ("restarting", exit code) after it
    fails."""
    report = on_state or (lambda _state, _rc: None)
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
                                         # one-thread supervisor: preexec_fn is safe here
                                         preexec_fn=_die_with_parent)  # noqa: PLW1509
                report("running", None)
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
            if rc == 0 or stopping or _exit_requested(control_file):
                return 0
            if time.monotonic() - started >= healthy_after:
                delay = restart_delay
            report("restarting", rc)
            with open(log_file, "a") as out:
                out.write(f"couchside-sendspin: daemon exited with {rc}, "
                          f"restarting in {delay:g}s\n")
            # wait out the delay in short steps: an exit request, a signal or new
            # settings (e.g. an unplugged device switched back to Default) act at once
            remaining = delay
            while remaining > 0 and not stopping:
                step = min(poll, remaining)
                sleep(step)
                remaining -= step
                if _exit_requested(control_file):
                    return 0
                try:
                    wanted = make()
                except Exception:
                    wanted = current
                if wanted != current:
                    current = wanted
                    delay = restart_delay
                    break
            else:
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
        sendspin_dir = sendspin_settings_dir()
        sendspin_dir.mkdir(parents=True, exist_ok=True)
        path = log_path()
        prepare_log(path)

        def argv() -> list[str]:
            return build_daemon_argv(load_settings(), sendspin_dir)

        def on_state(state: str, rc: int | None) -> None:
            write_status(status_path(), state, rc, build=build_id(), pid=os.getpid())
        return supervise(argv, path, control_file=control_path(), on_state=on_state)
    finally:
        write_status(status_path(), "stopped", build=build_id(), pid=os.getpid())
        lock.close()


if __name__ == "__main__":
    sys.exit(main())
