from types import SimpleNamespace as NS

from couchside.core.connection import ConnState
from music_assistant_models.enums import RepeatMode

from couchside.core.playback import NowPlaying, Playback, find_local_player, position_at

CID = "client-abc"


def player(pid, name="Speaker", protocols=(), state="idle", media=None, **extra):
    return NS(
        player_id=pid,
        name=name,
        available=True,
        output_protocols=[NS(output_protocol_id=p) for p in protocols],
        playback_state=state,
        current_media=media,
        **extra,
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

    async def volume_set(self, pid, level):
        self.calls.append(("volume_set", pid, level))


class FakeQueues:
    def __init__(self, queues=()):
        self.items = {q.queue_id: q for q in queues}
        self.calls = []

    def get(self, qid):
        return self.items.get(qid)

    async def shuffle(self, qid, enabled):
        self.calls.append(("shuffle", qid, enabled))

    async def repeat(self, qid, mode):
        self.calls.append(("repeat", qid, mode))


class FakeConn:
    def __init__(self, players, queues=()):
        self.client = NS(players=FakePlayers(players), player_queues=FakeQueues(queues))
        self.state = ConnState.CONNECTED
        self.state_cbs, self.event_cbs = [], []

    def on_state(self, cb):
        self.state_cbs.append(cb)

    def on_event(self, cb):
        self.event_cbs.append(cb)

    def fire_event(self, evt="player_updated"):
        for cb in self.event_cbs:
            cb(evt)


def make(players, client_id=CID, queues=()):
    conn = FakeConn(players, queues)
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
    from dataclasses import replace
    # no timestamp in this media: it gets a local one (see test_missing_timestamp_*)
    assert replace(pb.now_playing, elapsed_at=0.0) == NowPlaying(
        "Midnight City", "M83", "Hurry Up, We're Dreaming", "http://img/1.jpg", "playing")


def test_now_playing_none_when_nothing_loaded():
    _, pb, _ = make([player(CID)])
    pb.refresh()
    assert pb.now_playing is None


# --- Phase 2: progress, queue modes, volume -----------------------------------

def queue(qid=CID, state="playing", elapsed=0.0, at=0.0, shuffle=False, repeat="off", duration=None):
    item = NS(duration=duration) if duration is not None else None
    return NS(queue_id=qid, state=state, elapsed_time=elapsed, elapsed_time_last_updated=at,
              shuffle_enabled=shuffle, repeat_mode=RepeatMode(repeat), current_item=item)


def make_playing(queue=None, media_elapsed=0.0, media_at=0.0, duration=200, volume=50,
                 volume_control="some-protocol", state="playing", palette=None):
    media = NS(title="T", artist="A", album="B", image_url=None, duration=duration,
               elapsed_time=media_elapsed, elapsed_time_last_updated=media_at, palette=palette)
    p = player(CID, state=state, media=media, active_source=CID, volume_level=volume,
               volume_control=volume_control)
    conn, pb, _ = make([p], queues=[queue] if queue is not None else [])
    pb.refresh()
    return pb.now_playing


def test_progress_from_queue_when_paused():
    np = make_playing(queue=queue(state="idle", elapsed=42.0, at=1000.0), media_elapsed=3.0,
                      duration=261, state="idle")
    assert np.elapsed == 42.0 and np.elapsed_at == 1000.0 and np.duration == 261
    assert position_at(np, now=1010.0) == 42.0


def test_position_ticks_while_playing():
    np = NowPlaying("t", "a", "b", None, "playing", duration=200, elapsed=10.0, elapsed_at=1000.0)
    assert position_at(np, 1005.5) == 15.5
    assert position_at(np, 2000.0) == 200  # clamped to duration
    assert position_at(np, 900.0) == 0     # clock skew never goes negative


def test_progress_without_duration():
    np = NowPlaying("radio", "", "", None, "playing", duration=None, elapsed=5.0, elapsed_at=0.0)
    assert position_at(np, 100.0) == 105.0


def test_progress_falls_back_to_current_media_without_queue():
    np = make_playing(queue=None, media_elapsed=7.0, media_at=500.0, duration=180)
    assert (np.elapsed, np.elapsed_at, np.duration) == (7.0, 500.0, 180)
    assert np.queue_id is None


def test_duration_from_queue_item_when_media_has_none():
    np = make_playing(queue=queue(duration=99), duration=None)
    assert np.duration == 99


def test_shuffle_repeat_volume_read():
    np = make_playing(queue=queue(shuffle=True, repeat="one"), volume=35)
    assert (np.shuffle, np.repeat, np.volume, np.queue_id) == (True, "one", 35, CID)


def test_unknown_repeat_reads_as_off():
    assert make_playing(queue=queue(repeat="unknown")).repeat == "off"


def test_volume_unavailable():
    assert make_playing(volume=35, volume_control="none").volume is None


def test_palette_read():
    pal = NS(background_dark=(25, 28, 41))
    assert make_playing(palette=pal).palette_dark == (25, 28, 41)


def _with_queue(**q):
    media = NS(title="T", artist="A", album="B", image_url=None)
    p = player(CID, state="playing", media=media, active_source=CID, volume_level=3,
               volume_control="x")
    conn, pb, _ = make([p], queues=[queue(**q)])
    pb.refresh()
    return conn, pb


async def test_cycle_repeat_sends_next_mode():
    for current, expected in [("off", RepeatMode.ALL), ("all", RepeatMode.ONE), ("one", RepeatMode.OFF)]:
        conn, pb = _with_queue(repeat=current)
        await pb.cycle_repeat()
        assert conn.client.player_queues.calls == [("repeat", CID, expected)]


async def test_toggle_shuffle_sends_inverse():
    conn, pb = _with_queue(shuffle=True)
    await pb.toggle_shuffle()
    assert conn.client.player_queues.calls == [("shuffle", CID, False)]


async def test_set_volume_clamps():
    conn, pb = _with_queue()
    await pb.set_volume(130)
    await pb.step_volume(-5)  # from 3
    assert conn.client.players.calls == [("volume_set", CID, 100), ("volume_set", CID, 0)]


async def test_queue_commands_noop_when_disconnected():
    conn, pb = _with_queue()
    conn.state = ConnState.RECONNECTING
    await pb.toggle_shuffle()
    await pb.cycle_repeat()
    await pb.set_volume(10)
    assert conn.client.player_queues.calls == [] and conn.client.players.calls == []


def test_missing_timestamp_is_stamped_with_snapshot_time(monkeypatch):
    # PlayerMedia.elapsed_time_last_updated defaults to None (sources without an MA queue).
    import couchside.core.playback as pbm
    monkeypatch.setattr(pbm.time, "time", lambda: 5000.0)
    np = make_playing(queue=None, media_elapsed=30.0, media_at=None, duration=None)
    assert np.elapsed_at == 5000.0
    assert position_at(np, 5002.0) == 32.0  # not ~5000 s


def test_stamped_time_kept_across_refreshes(monkeypatch):
    # Re-stamping on every event would make the progress jump back each refresh.
    import couchside.core.playback as pbm
    clock = [5000.0]
    monkeypatch.setattr(pbm.time, "time", lambda: clock[0])
    media = NS(title="T", artist="A", album="", image_url=None, duration=None,
               elapsed_time=30.0, elapsed_time_last_updated=None, palette=None)
    p = player(CID, state="playing", media=media, active_source=CID, volume_level=1, volume_control="x")
    conn, pb, _ = make([p])
    pb.refresh()
    clock[0] = 5010.0
    conn.fire_event()
    assert pb.now_playing.elapsed_at == 5000.0
    media.elapsed_time = 12.0  # a new position report (seek / new track) gets a new stamp
    conn.fire_event()
    assert pb.now_playing.elapsed_at == 5010.0
