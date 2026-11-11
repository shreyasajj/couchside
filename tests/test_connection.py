import asyncio

from music_assistant_client.exceptions import CannotConnect, ConnectionClosed
from music_assistant_models.errors import AuthenticationFailed, InvalidToken

from couchside.core.connection import Connection, ConnState


class FakeClient:
    """Stands in for MusicAssistantClient. `script` decides each connect outcome."""

    def __init__(self, outcome, drop_event: asyncio.Event | None = None, never_ready=False):
        self.outcome = outcome  # None = ok, or an exception instance to raise
        self.never_ready = never_ready
        self.drop_event = drop_event or asyncio.Event()
        self.disconnected = False
        self.subscribers = []

    async def connect(self):
        if self.outcome is not None:
            raise self.outcome

    async def start_listening(self, init_ready=None):
        await self.connect()
        if init_ready is not None and not self.never_ready:
            init_ready.set()
        await self.drop_event.wait()  # returns when the "socket" drops

    async def disconnect(self):
        self.disconnected = True
        self.drop_event.set()  # like the real client: listening ends on disconnect

    def subscribe(self, cb, event_filter=None, id_filter=None):
        self.subscribers.append(cb)
        return lambda: self.subscribers.remove(cb)


class Harness:
    def __init__(self, outcomes, url="http://ma:8095", token="tok", sleep_blocks=False,
                 never_ready=False, init_timeout=30.0):
        self.outcomes = list(outcomes)
        self.clients: list[FakeClient] = []
        self.sleeps: list[float] = []
        self.states: list[ConnState] = []
        self.url = url
        self.token = token
        self.urls_used: list = []

        async def get_url():
            if isinstance(self.url, Exception):
                raise self.url
            self.urls_used.append(self.url)
            return self.url

        def factory(url, token):
            outcome = self.outcomes.pop(0) if self.outcomes else None
            c = FakeClient(outcome, never_ready=never_ready)
            self.clients.append(c)
            return c

        async def fake_sleep(d):
            self.sleeps.append(d)
            if sleep_blocks:
                await asyncio.Event().wait()  # only retry_now()/stop() can end it
            await asyncio.sleep(0)

        self.conn = Connection(get_url, lambda: self.token, client_factory=factory, sleep=fake_sleep,
                               init_timeout=init_timeout)
        self.conn.on_state(self.states.append)

    def start(self):
        return asyncio.create_task(self.conn.run())

    async def until(self, predicate, timeout=2.0):
        async def wait():
            while not predicate():
                await asyncio.sleep(0.005)
        await asyncio.wait_for(wait(), timeout)

    async def run_until(self, predicate, timeout=2.0):
        task = self.start()
        await self.until(predicate, timeout)
        return task

    async def finish(self, task):
        await self.conn.stop()
        await asyncio.wait_for(task, 2)


async def test_connects_and_reports_connected():
    h = Harness([None])
    task = await h.run_until(lambda: h.conn.state is ConnState.CONNECTED)
    assert h.states[:2] == [ConnState.CONNECTING, ConnState.CONNECTED]
    assert h.conn.client is h.clients[0]
    await h.finish(task)


async def test_backoff_sequence():
    h = Harness([CannotConnect("x")] * 7 + [None])
    task = await h.run_until(lambda: h.conn.state is ConnState.CONNECTED)
    assert h.sleeps == [1, 2, 4, 8, 16, 30, 30]
    await h.finish(task)


async def test_reconnects_after_drop():
    h = Harness([CannotConnect("x"), None, None])
    task = await h.run_until(lambda: h.conn.state is ConnState.CONNECTED)
    assert h.sleeps == [1]
    h.clients[-1].drop_event.set()
    await h.until(lambda: len(h.clients) == 3 and h.conn.state is ConnState.CONNECTED)
    assert ConnState.RECONNECTING in h.states
    assert h.sleeps == [1, 1]  # backoff restarted after the successful connect
    assert h.clients[1].disconnected
    await h.finish(task)


async def test_auth_failure_stops_retrying():
    h = Harness([AuthenticationFailed("bad token"), None])
    task = await h.run_until(lambda: h.conn.state is ConnState.AUTH_FAILED)
    await asyncio.sleep(0.05)
    assert len(h.clients) == 1
    h.conn.retry_now()
    await h.until(lambda: h.conn.state is ConnState.CONNECTED)
    assert len(h.clients) == 2
    await h.finish(task)


async def test_missing_token_is_auth_failed_without_connecting():
    h = Harness([None], token=None)
    task = await h.run_until(lambda: h.conn.state is ConnState.AUTH_FAILED)
    assert h.clients == []
    await h.finish(task)


async def test_no_server_state():
    h = Harness([None], url=None)
    task = await h.run_until(lambda: h.conn.state is ConnState.NO_SERVER and len(h.sleeps) >= 2)
    assert h.sleeps[:2] == [1, 2]
    assert h.clients == []
    await h.finish(task)


async def test_events_forwarded():
    h = Harness([None])
    got = []
    h.conn.on_event(got.append)
    task = await h.run_until(lambda: h.conn.state is ConnState.CONNECTED)
    h.clients[0].subscribers[0]("evt")
    assert got == ["evt"]
    await h.finish(task)


async def test_unexpected_error_is_retried_not_raised():
    h = Harness([RuntimeError("boom"), None])
    task = await h.run_until(lambda: h.conn.state is ConnState.CONNECTED)
    assert h.sleeps == [1]
    await h.finish(task)


async def test_retry_now_while_connected_reconnects_with_new_url():
    h = Harness([None, None])
    task = await h.run_until(lambda: h.conn.state is ConnState.CONNECTED)
    h.url = "http://other:8095"
    h.conn.retry_now()
    await h.until(lambda: len(h.clients) == 2 and h.conn.state is ConnState.CONNECTED)
    assert h.clients[0].disconnected
    assert h.urls_used[-1] == "http://other:8095"
    assert h.sleeps == []  # reconnected straight away, no backoff
    await h.finish(task)


async def test_retry_during_connect_attempt_is_not_lost():
    h = Harness([CannotConnect("x"), None], sleep_blocks=True)
    task = h.start()
    await h.until(lambda: len(h.clients) == 1)
    h.conn.retry_now()  # arrives while the first attempt is still failing
    await h.until(lambda: h.conn.state is ConnState.CONNECTED)
    await h.finish(task)


async def test_initial_state_timeout_backs_off():
    h = Harness([None, None], never_ready=True, init_timeout=0.05)
    task = h.start()
    await h.until(lambda: len(h.clients) >= 2)
    assert h.clients[0].disconnected
    assert h.sleeps and h.sleeps[0] == 1
    assert ConnState.CONNECTED not in h.states
    await h.finish(task)


async def test_get_url_error_is_no_server_and_retried():
    h = Harness([None], url=OSError("no network"))
    task = await h.run_until(lambda: len(h.sleeps) >= 2)
    assert h.conn.state is ConnState.NO_SERVER
    h.url = "http://ma:8095"
    await h.until(lambda: h.conn.state is ConnState.CONNECTED)
    await h.finish(task)


def _auth_error(cause):
    err = AuthenticationFailed(f"Authentication failed: {cause}")
    err.__cause__ = cause
    return err


async def test_transient_error_during_login_is_retried():
    h = Harness([_auth_error(ConnectionClosed("closed")), None])
    task = await h.run_until(lambda: h.conn.state is ConnState.CONNECTED)
    assert h.sleeps == [1]
    assert ConnState.AUTH_FAILED not in h.states
    await h.finish(task)


async def test_server_rejected_token_is_auth_failed():
    h = Harness([_auth_error(InvalidToken("expired")), None])
    task = await h.run_until(lambda: h.conn.state is ConnState.AUTH_FAILED)
    await asyncio.sleep(0.05)
    assert len(h.clients) == 1
    await h.finish(task)
