import asyncio

from music_assistant_client.exceptions import CannotConnect
from music_assistant_models.errors import AuthenticationFailed

from couchside.core.connection import Connection, ConnState


class FakeClient:
    """Stands in for MusicAssistantClient. `script` decides each connect outcome."""

    def __init__(self, outcome, drop_event: asyncio.Event | None = None):
        self.outcome = outcome  # None = ok, or an exception instance to raise
        self.drop_event = drop_event or asyncio.Event()
        self.disconnected = False
        self.subscribers = []

    async def connect(self):
        if self.outcome is not None:
            raise self.outcome

    async def start_listening(self, init_ready=None):
        await self.connect()
        if init_ready is not None:
            init_ready.set()
        await self.drop_event.wait()  # returns when the "socket" drops

    async def disconnect(self):
        self.disconnected = True
        self.drop_event.set()  # like the real client: listening ends on disconnect

    def subscribe(self, cb, event_filter=None, id_filter=None):
        self.subscribers.append(cb)
        return lambda: self.subscribers.remove(cb)


class Harness:
    def __init__(self, outcomes, url="http://ma:8095", token="tok"):
        self.outcomes = list(outcomes)
        self.clients: list[FakeClient] = []
        self.sleeps: list[float] = []
        self.states: list[ConnState] = []
        self.url = url
        self.token = token

        async def get_url():
            return self.url

        def factory(url, token):
            outcome = self.outcomes.pop(0) if self.outcomes else None
            c = FakeClient(outcome)
            self.clients.append(c)
            return c

        async def fake_sleep(d):
            self.sleeps.append(d)
            await asyncio.sleep(0)

        self.conn = Connection(get_url, lambda: self.token, client_factory=factory, sleep=fake_sleep)
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
