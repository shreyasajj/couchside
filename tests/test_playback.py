from types import SimpleNamespace as NS

from couchside.core.connection import ConnState
from couchside.core.playback import NowPlaying, Playback, find_local_player

CID = "client-abc"


def player(pid, name="Speaker", protocols=(), state="idle", media=None):
    return NS(
        player_id=pid,
        name=name,
        available=True,
        output_protocols=[NS(output_protocol_id=p) for p in protocols],
        playback_state=state,
        current_media=media,
    )


class FakePlayers:
    def __init__(self, players):
        self.items = {p.player_id: p for p in players}
        self.calls = []

    def __iter__(self):
        return iter(list(self.items.values()))

    def get(self, pid):
        return self.items.get(pid)

    async def play_pause(self, pid):
        self.calls.append(("play_pause", pid))

    async def next_track(self, pid):
        self.calls.append(("next", pid))

    async def previous_track(self, pid):
        self.calls.append(("previous", pid))


class FakeConn:
    def __init__(self, players):
        self.client = NS(players=FakePlayers(players))
        self.state = ConnState.CONNECTED
        self.state_cbs, self.event_cbs = [], []

    def on_state(self, cb):
        self.state_cbs.append(cb)

    def on_event(self, cb):
        self.event_cbs.append(cb)

    def fire_event(self, evt="player_updated"):
        for cb in self.event_cbs:
            cb(evt)


def make(players, client_id=CID):
    conn = FakeConn(players)
    pb = Playback(conn, lambda: client_id)
    changes = []
    pb.on_change(lambda: changes.append(1))
    return conn, pb, changes


def test_selects_local_player_by_client_id():
    _, pb, _ = make([player("a"), player(CID, "Living Room TV"), player("b")])
    pb.refresh()
    assert pb.active_player_id == CID
    assert pb.local_player_found


def test_selects_player_exposing_client_id_as_output_protocol():
    assert find_local_player([player("x"), player("parent", protocols=[CID])], CID).player_id == "parent"


def test_ignores_same_name_other_player():
    _, pb, _ = make([player("other", "Living Room TV")])
    pb.refresh()
    assert pb.active_player_id is None
    assert not pb.local_player_found


def test_no_client_id_selects_nothing():
    _, pb, _ = make([player(CID)], client_id=None)
    pb.refresh()
    assert pb.active_player_id is None


def test_selects_when_player_appears_later():
    conn, pb, changes = make([])
    pb.refresh()
    assert not pb.local_player_found
    conn.client.players.items[CID] = player(CID)
    conn.fire_event()
    assert pb.local_player_found and pb.active_player_id == CID
    assert changes


def test_refreshes_on_connected_state():
    conn, pb, _ = make([player(CID)])
    for cb in conn.state_cbs:
        cb(ConnState.CONNECTED)
    assert pb.active_player_id == CID


def test_disconnect_clears_now_playing():
    media = NS(title="T", artist="A", album="B", image_url=None)
    conn, pb, _ = make([player(CID, state="playing", media=media)])
    pb.refresh()
    conn.client = None
    for cb in conn.state_cbs:
        cb(ConnState.RECONNECTING)
    assert pb.now_playing is None


async def test_transport_calls_active_player():
    conn, pb, _ = make([player(CID)])
    pb.refresh()
    await pb.play_pause()
    await pb.next()
    await pb.previous()
    assert conn.client.players.calls == [("play_pause", CID), ("next", CID), ("previous", CID)]


async def test_transport_noop_when_disconnected():
    conn, pb, _ = make([player(CID)])
    pb.refresh()
    conn.client = None
    await pb.play_pause()  # must not raise


async def test_transport_noop_without_player():
    conn, pb, _ = make([])
    pb.refresh()
    await pb.next()
    assert conn.client.players.calls == []


def test_now_playing_from_player_media():
    media = NS(title="Midnight City", artist="M83", album="Hurry Up, We're Dreaming",
               image_url="http://img/1.jpg")
    _, pb, _ = make([player(CID, state="playing", media=media)])
    pb.refresh()
    assert pb.now_playing == NowPlaying("Midnight City", "M83", "Hurry Up, We're Dreaming",
                                        "http://img/1.jpg", "playing")


def test_now_playing_none_when_nothing_loaded():
    _, pb, _ = make([player(CID)])
    pb.refresh()
    assert pb.now_playing is None
