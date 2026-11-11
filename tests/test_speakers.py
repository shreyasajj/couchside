from types import SimpleNamespace as NS

from couchside.core.speakers import SpeakerRow, speaker_action, speaker_rows

TV, MAC, DEN, GRP = "tv", "mac", "den", "grp"


def p(pid, name, available=True, enabled=True, kind="player", members=(), can=(), synced_to=None,
      media=None, active_source=None):
    return NS(player_id=pid, name=name, available=available, enabled=enabled, type=NS(value=kind),
              group_members=list(members), can_group_with=list(can), synced_to=synced_to,
              current_media=media, active_source=active_source)


def players():
    return [
        p(DEN, "Den", available=False),
        p(MAC, "Mac mini", can=[TV], media=NS(title="Song", artist="Band")),
        p(TV, "Living Room TV", can=[MAC]),
        p("off", "Old", enabled=False),
        p(GRP, "Party", kind="group", members=[TV, MAC]),
    ]


def test_rows_order_and_flags():
    rows = speaker_rows(players(), controlled_id=MAC, local_id=TV)
    assert [r.player_id for r in rows] == [MAC, TV, GRP, DEN]
    mac, tv, grp, den = rows
    assert mac.controlled and not mac.local
    assert tv.local and not tv.controlled
    assert grp.is_group and grp.members == (TV, MAC)
    assert not den.available


def test_disabled_players_hidden():
    assert "off" not in [r.player_id for r in speaker_rows(players(), TV, TV)]


def test_playing_text():
    rows = {r.player_id: r for r in speaker_rows(players(), TV, TV)}
    assert rows[MAC].playing == "Song — Band"
    assert rows[TV].playing == ""


def test_can_sync_uses_can_group_with():
    rows = {r.player_id: r for r in speaker_rows(players(), TV, TV)}
    assert rows[MAC].can_sync          # TV can group with the Mac
    assert not rows[DEN].can_sync      # unavailable, not groupable
    assert not rows[TV].can_sync       # never with itself


def test_synced_to_reported():
    ps = players()
    ps[1].synced_to = TV
    rows = {r.player_id: r for r in speaker_rows(ps, TV, TV)}
    assert rows[MAC].synced_to == TV


class FakePlayers:
    def __init__(self, items, fail=False):
        self.items = {x.player_id: x for x in items}
        self.calls, self.fail = [], fail

    def __iter__(self):
        return iter(self.items.values())

    def get(self, pid):
        return self.items.get(pid)

    async def set_members(self, target, player_ids_to_add=None, player_ids_to_remove=None):
        self._rec(("set_members", target, player_ids_to_add, player_ids_to_remove))

    async def create_group_player(self, provider, name, members, dynamic=None):
        self._rec(("create", provider, name, members))

    async def remove_group_player(self, pid):
        self._rec(("remove_group", pid))

    def _rec(self, call):
        self.calls.append(call)
        if self.fail:
            raise RuntimeError("nope")


class FakeQueues:
    def __init__(self):
        self.calls = []

    async def transfer_queue(self, src, dst, auto_play=None):
        self.calls.append(("transfer", src, dst, auto_play))


def client(fail=False):
    ps = players()
    ps[2].active_source = "tvqueue"
    return NS(players=FakePlayers(ps, fail), player_queues=FakeQueues())


async def test_sync_and_unsync_calls():
    c = client()
    assert await speaker_action(c, TV, MAC, "sync")
    c.players.items[MAC].synced_to = TV
    assert await speaker_action(c, TV, MAC, "unsync")
    assert c.players.calls == [("set_members", TV, [MAC], None), ("set_members", TV, None, [MAC])]


async def test_transfer_uses_active_queue():
    c = client()
    assert await speaker_action(c, TV, MAC, "transfer")
    assert c.player_queues.calls == [("transfer", "tvqueue", MAC, True)]


async def test_create_group_name_from_members():
    c = client()
    assert await speaker_action(c, TV, "", "create_group", members=[TV, MAC])
    assert c.players.calls == [("create", "sync_group", "Living Room TV + Mac mini", [TV, MAC])]


async def test_edit_group_diff():
    c = client()
    assert await speaker_action(c, TV, GRP, "edit_group", members=[TV, DEN])
    assert c.players.calls == [("set_members", GRP, [DEN], [MAC])]


async def test_delete_group():
    c = client()
    assert await speaker_action(c, TV, GRP, "delete_group")
    assert c.players.calls == [("remove_group", GRP)]


async def test_action_failure_is_false():
    assert not await speaker_action(client(fail=True), TV, MAC, "sync")
    assert not await speaker_action(client(), TV, MAC, "explode")
    assert not await speaker_action(client(), TV, "missing", "transfer")
