from couchside.core.connection import ConnState
from couchside.core.status import status_text


def test_connecting():
    assert status_text(ConnState.CONNECTING, False) == "Connecting to Music Assistant…"
    assert status_text(ConnState.DISCOVERING, False) == "Connecting to Music Assistant…"
    assert status_text(ConnState.IDLE, False) == "Connecting to Music Assistant…"


def test_reconnecting():
    assert status_text(ConnState.RECONNECTING, True) == "Reconnecting…"


def test_auth_failed():
    assert status_text(ConnState.AUTH_FAILED, False) == "Login failed — check token in Settings"


def test_no_server():
    assert status_text(ConnState.NO_SERVER, False) == "No Music Assistant server found"


def test_waiting_for_local_player():
    assert status_text(ConnState.CONNECTED, False) == "Waiting for this TV's speaker…"


def test_connected_with_player_is_empty():
    assert status_text(ConnState.CONNECTED, True) == ""
