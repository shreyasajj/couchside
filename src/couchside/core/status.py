"""User-facing status line for the connection / player state."""

from __future__ import annotations

from couchside.core.connection import ConnState


def status_text(state: ConnState, has_local_player: bool) -> str:
    if state is ConnState.CONNECTED:
        return "" if has_local_player else "Waiting for this TV's speaker…"
    if state is ConnState.RECONNECTING:
        return "Reconnecting…"
    if state is ConnState.AUTH_FAILED:
        return "Login failed — check token in Settings"
    if state is ConnState.NO_SERVER:
        return "No Music Assistant server found"
    return "Connecting to Music Assistant…"
