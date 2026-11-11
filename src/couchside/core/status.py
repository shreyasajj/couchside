"""User-facing status line for the connection / player state."""

from __future__ import annotations

from couchside.core.connection import ConnState


def needs_setup(state: ConnState, has_token: bool) -> bool:
    """Open the Connect page: no token, token refused, or no server to be found."""
    return not has_token or state in (ConnState.AUTH_FAILED, ConnState.NO_SERVER)


def status_text(state: ConnState, has_local_player: bool, has_token: bool = True) -> str:
    if state is ConnState.CONNECTED:
        return "" if has_local_player else "Waiting for this TV's speaker…"
    if state is ConnState.RECONNECTING:
        return "Reconnecting…"
    if state is ConnState.AUTH_FAILED:
        if not has_token:
            return "Enter your Music Assistant token in Settings"
        return "Login failed — check token in Settings"
    if state is ConnState.NO_SERVER:
        return "No Music Assistant server found"
    return "Connecting to Music Assistant…"
