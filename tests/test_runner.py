import sys
from pathlib import Path

from couchside.core.settings import AppSettings
from couchside.sendspin.runner import acquire_lock, build_daemon_argv, prepare_log, supervise


def test_argv():
    argv = build_daemon_argv(AppSettings(), Path("/cfg/sendspin"))
    # sendspin has no __main__ module, so call its console-script entry point.
    assert argv == [sys.executable, "-c", "import sys; from sendspin.cli import main; sys.exit(main())",
                    "daemon", "--settings-dir", "/cfg/sendspin", "--port", "8937",
                    "--name", "Living Room TV"]


def test_argv_uses_sendspin_port():
    argv = build_daemon_argv(AppSettings(sendspin_port=9000), Path("/x"))
    assert argv[argv.index("--port") + 1] == "9000"


def test_argv_uses_player_name():
    argv = build_daemon_argv(AppSettings(player_name="Den TV"), Path("/x"))
    assert argv[-2:] == ["--name", "Den TV"]


def test_single_instance(tmp_path):
    first = acquire_lock(tmp_path / "sendspin.lock")
    assert first is not None
    assert acquire_lock(tmp_path / "sendspin.lock") is None
    first.close()
    again = acquire_lock(tmp_path / "sendspin.lock")
    assert again is not None
    again.close()


def test_log_truncated_when_large(tmp_path):
    p = tmp_path / "sendspin.log"
    p.write_text("x" * 2_000_000)
    prepare_log(p, max_bytes=1_000_000)
    assert p.stat().st_size == 0


def test_log_kept_when_small(tmp_path):
    p = tmp_path / "sendspin.log"
    p.write_text("hello\n")
    prepare_log(p, max_bytes=1_000_000)
    assert p.read_text() == "hello\n"


def test_supervise_restarts_after_failure(tmp_path):
    counter = tmp_path / "count"
    script = (
        "import pathlib,sys;p=pathlib.Path(sys.argv[1]);"
        "n=int(p.read_text()) if p.exists() else 0;p.write_text(str(n+1));"
        "print('run',n+1);sys.exit(1 if n==0 else 0)"
    )
    log = tmp_path / "out.log"
    rc = supervise([sys.executable, "-c", script, str(counter)], log, restart_delay=0)
    assert rc == 0
    assert counter.read_text() == "2"
    assert "run 1" in log.read_text() and "run 2" in log.read_text()


FAIL_N_TIMES = (
    "import pathlib,sys;p=pathlib.Path(sys.argv[1]);"
    "n=int(p.read_text()) if p.exists() else 0;p.write_text(str(n+1));"
    "print('x'*100);sys.exit(1 if n < int(sys.argv[2]) else 0)"
)


def test_sigterm_during_restart_delay_starts_no_new_daemon(tmp_path):
    import os
    import signal
    import threading
    counter = tmp_path / "count"
    timer = threading.Timer(0.3, lambda: os.kill(os.getpid(), signal.SIGTERM))
    timer.start()
    try:
        rc = supervise([sys.executable, "-c", FAIL_N_TIMES, str(counter), "99"],
                       tmp_path / "out.log", restart_delay=1.0)
    finally:
        timer.cancel()
    assert rc == 0
    assert counter.read_text() == "1"  # stopped while waiting; never started again


def test_restart_delay_backs_off(tmp_path):
    delays = []
    rc = supervise([sys.executable, "-c", FAIL_N_TIMES, str(tmp_path / "c"), "3"],
                   tmp_path / "out.log", restart_delay=3.0, sleep=delays.append)
    assert rc == 0
    assert delays == [3.0, 6.0, 12.0]


def test_restart_delay_capped(tmp_path):
    delays = []
    supervise([sys.executable, "-c", FAIL_N_TIMES, str(tmp_path / "c"), "6"],
              tmp_path / "out.log", restart_delay=10.0, max_delay=60.0, sleep=delays.append)
    assert delays == [10.0, 20.0, 40.0, 60.0, 60.0, 60.0]


def test_log_trimmed_between_restarts(tmp_path):
    log = tmp_path / "out.log"
    supervise([sys.executable, "-c", FAIL_N_TIMES, str(tmp_path / "c"), "2"],
              log, restart_delay=0, max_log_bytes=150, sleep=lambda d: None)
    assert log.stat().st_size < 300  # three runs of 100+ bytes each, trimmed on the way
