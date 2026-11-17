"""What counts as broken, for the warning button in the top bar: this TV's speaker (the
bundled Sendspin daemon) stopped or keeps stopping, Music Assistant can't be reached or
refused the token, or this TV's player is missing from Music Assistant. Qt-free."""

from __future__ import annotations

from dataclasses import dataclass

from couchside.core.connection import ConnState

# shown as soon as they are seen; the rest only once they have lasted (a reconnect, or the
# speaker starting up, is not a problem)
AT_ONCE = {"speaker-crashing"}


@dataclass(frozen=True)
class Problem:
    id: str
    message: str


def supervisor_outdated(status: dict | None, running: bool, build: str) -> bool:
    """A supervisor runs, but from another build (or one too old to say which)."""
    return running and (status is None or status.get("build") != build)


def diagnose(*, status: dict | None, running: bool, conn: ConnState, local_player: bool,
             has_token: bool) -> list[Problem]:
    out = []
    if not running:
        out.append(Problem("speaker-stopped", "This TV's speaker isn't running"))
    elif status and status.get("state") == "restarting":
        code = status.get("exit_code")
        out.append(Problem("speaker-crashing", "This TV's speaker keeps stopping"
                           + (f" (exit code {code})" if code is not None else "")))
    if conn in (ConnState.NO_SERVER, ConnState.RECONNECTING):
        out.append(Problem("server", "Can't reach Music Assistant"))
    elif conn is ConnState.AUTH_FAILED and has_token:
        out.append(Problem("login", "Music Assistant refused the token"))
    elif conn is ConnState.CONNECTED and not local_player and not out:
        out.append(Problem("player-missing", "This TV's speaker isn't in Music Assistant"))
    return out


class ProblemWatch:
    """Problems as they should be shown: each from when it has lasted `hold` seconds
    (those in AT_ONCE straight away), gone as soon as it is."""

    def __init__(self, hold: float = 15.0) -> None:
        self._hold = hold
        self._since: dict[str, float] = {}

    def update(self, problems: list[Problem], now: float) -> list[Problem]:
        self._since = {p.id: self._since.get(p.id, now) for p in problems}
        return [p for p in problems if p.id in AT_ONCE or now - self._since[p.id] >= self._hold]
