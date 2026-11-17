"""What counts as broken, for the warning button in the top bar."""

from couchside.core.connection import ConnState
from couchside.core.health import ProblemWatch, diagnose, supervisor_outdated

OK = dict(status={"state": "running", "build": "b1"}, running=True, conn=ConnState.CONNECTED,
          local_player=True, has_token=True)


def ids(problems):
    return [p.id for p in problems]


def test_nothing_wrong():
    assert diagnose(**OK) == []


def test_speaker_keeps_stopping_shows_its_exit_code():
    got = diagnose(**{**OK, "status": {"state": "restarting", "exit_code": 1}})
    assert ids(got) == ["speaker-crashing"] and "exit code 1" in got[0].message


def test_speaker_not_running():
    assert ids(diagnose(**{**OK, "running": False})) == ["speaker-stopped"]


def test_music_assistant_problems():
    assert ids(diagnose(**{**OK, "conn": ConnState.NO_SERVER})) == ["server"]
    assert ids(diagnose(**{**OK, "conn": ConnState.RECONNECTING})) == ["server"]
    assert ids(diagnose(**{**OK, "conn": ConnState.AUTH_FAILED})) == ["login"]
    assert diagnose(**{**OK, "conn": ConnState.AUTH_FAILED, "has_token": False}) == []  # first run
    assert diagnose(**{**OK, "conn": ConnState.CONNECTING}) == []
    # connected, but this TV's player isn't there: only worth saying when the speaker runs
    assert ids(diagnose(**{**OK, "local_player": False})) == ["player-missing"]
    assert ids(diagnose(**{**OK, "local_player": False, "running": False})) == ["speaker-stopped"]


def test_an_outdated_supervisor_is_one_from_another_build():
    assert supervisor_outdated({"build": "b1"}, True, "b1") is False
    assert supervisor_outdated({"build": "b0"}, True, "b1") is True
    assert supervisor_outdated(None, True, "b1") is True        # too old to write a status
    assert supervisor_outdated({"build": "b0"}, False, "b1") is False   # nothing running


def test_problems_show_only_once_they_last():
    watch = ProblemWatch(hold=10.0)
    crash = diagnose(**{**OK, "status": {"state": "restarting", "exit_code": 1}})
    server = diagnose(**{**OK, "conn": ConnState.RECONNECTING})
    assert watch.update(server, now=0.0) == []           # a short reconnect is nothing
    assert watch.update(server, now=9.0) == []
    assert ids(watch.update(server, now=10.5)) == ["server"]
    assert watch.update([], now=11.0) == []              # fixed: gone at once
    assert watch.update(server, now=12.0) == []          # and the clock starts again
    assert ids(watch.update(crash, now=12.0)) == ["speaker-crashing"]   # a crash shows at once
