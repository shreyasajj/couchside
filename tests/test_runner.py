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


# --- Phase 7: Sendspin settings and a live supervisor ----------------------------------

from couchside.sendspin.runner import parse_audio_devices, request_exit  # noqa: E402

SLEEPER = ("import pathlib,sys,time;p=pathlib.Path(sys.argv[1]);"
           "p.write_text(p.read_text()+sys.argv[2]+',' if p.exists() else sys.argv[2]+',');time.sleep(30)")


def test_argv_audio_device_and_delay():
    argv = build_daemon_argv(AppSettings(sendspin_audio_device="HD-Audio Generic: HISENSE (hw:0,3)",
                                         sendspin_delay_ms=150), Path("/x"))
    assert argv[argv.index("--audio-device") + 1] == "HD-Audio Generic: HISENSE (hw:0,3)"
    assert argv[argv.index("--output-delay-ms") + 1] == "150"


def test_argv_defaults_leave_sendspin_to_choose():
    argv = build_daemon_argv(AppSettings(), Path("/x"))
    assert "--audio-device" not in argv and "--output-delay-ms" not in argv


def test_supervise_restarts_when_the_command_changes_and_exits_on_request(tmp_path):
    import threading
    import time

    seen = tmp_path / "seen"
    control = tmp_path / "control"
    which = {"v": "a"}

    def argv():
        return [sys.executable, "-c", SLEEPER, str(seen), which["v"]]

    def drive():
        deadline = time.monotonic() + 10
        while not (seen.exists() and "a," in seen.read_text()) and time.monotonic() < deadline:
            time.sleep(0.05)
        which["v"] = "b"  # e.g. the player name changed in Settings
        while not (seen.exists() and "b," in seen.read_text()) and time.monotonic() < deadline:
            time.sleep(0.05)
        request_exit(control)
    t = threading.Thread(target=drive)
    t.start()
    started = time.monotonic()
    rc = supervise(argv, tmp_path / "out.log", restart_delay=0, poll=0.1, control_file=control)
    t.join()
    assert rc == 0
    assert seen.read_text() == "a,b,"           # one daemon each, no failure restarts
    assert time.monotonic() - started < 10      # didn't wait for the 30 s sleeps
    assert not control.exists()                 # the request is consumed


def test_supervise_keeps_running_when_settings_cant_be_read(tmp_path):
    import threading

    seen = tmp_path / "seen"
    control = tmp_path / "control"
    calls = {"n": 0}

    def argv():
        calls["n"] += 1
        if calls["n"] > 1:
            raise ValueError("corrupt settings")
        return [sys.executable, "-c", SLEEPER, str(seen), "a"]
    threading.Timer(0.8, request_exit, [control]).start()
    assert supervise(argv, tmp_path / "out.log", restart_delay=0, poll=0.1, control_file=control) == 0
    assert seen.read_text() == "a,"


def test_parse_audio_devices():
    text = """Available audio output devices:

  [0] HD-Audio Generic: HISENSE (hw:0,3)
       Channels: 8, Sample rate: 44100.0 Hz
  [4] HD-Audio Generic: ALC897 Analog (hw:2,0)
       Channels: 2, Sample rate: 44100.0 Hz
  [8] pulse
       Channels: 32, Sample rate: 44100.0 Hz
  [9] default (default)
       Channels: 32, Sample rate: 44100.0 Hz

To select an audio device:
  sendspin --audio-device 0
"""
    assert parse_audio_devices(text) == ["HD-Audio Generic: HISENSE (hw:0,3)",
                                         "HD-Audio Generic: ALC897 Analog (hw:2,0)", "pulse"]
    assert parse_audio_devices("") == []
