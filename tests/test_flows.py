"""Whole journeys through the app, end to end: the real controller, connection, playback,
library, queue, speakers, guest server and settings, on a fake Music Assistant
(tests/fake_ma.py). Each test is one thing a person does, start to finish."""

import asyncio

import aiohttp
import pytest
from music_assistant_models.errors import AuthenticationFailed, InvalidToken

from couchside.core.connection import ConnState
from couchside.core.settings import AppSettings, load_settings, save_token
from tests.conftest import NoLyrics, free_port, settle, until
from tests.fake_ma import CATALOGUE, KITCHEN, TV, FakeMA

pytest.importorskip("PySide6.QtCore")


def rows_by_title(ctl):
    return {r["title"]: [c["title"] for c in r["items"]] for r in ctl.libraryRows}


def speaker(ctl, pid):
    return next(r for r in ctl.speakerRows if r["playerId"] == pid)


# --- starting up ------------------------------------------------------------------------
async def test_start_finds_this_tv_and_shows_what_it_plays(house):
    ctl = house.ctl
    assert ctl.connState == "connected"
    assert ctl.hasLocalPlayer and not ctl.needsSetup
    assert (ctl.title, ctl.artist, ctl.album) == ("Neon Tide", "Marisol Vega", "Afterglow")
    assert ctl.isPlaying and ctl.hasDuration and ctl.duration == 200
    assert (ctl.nextTitle, ctl.nextArtist) == ("Glass Harbour", "Marisol Vega")
    tv = speaker(ctl, TV)
    assert tv["controlled"] and tv["local"] and tv["name"] == "Living Room TV"


# --- the remote's transport buttons -----------------------------------------------------
async def test_play_pause_next_previous_shuffle_repeat_and_volume(house):
    ctl, ma = house.ctl, house.ma
    ctl.playPause()
    await until(lambda: not ctl.isPlaying, what="paused")
    ctl.playPause()
    await until(lambda: ctl.isPlaying, what="playing again")
    ctl.next()
    await until(lambda: ctl.title == "Glass Harbour", what="next song")
    assert ctl.nextTitle == "Slow Comet"
    ctl.previous()
    await until(lambda: ctl.title == "Neon Tide", what="previous song")
    ctl.toggleShuffle()
    await until(lambda: ctl.shuffle, what="shuffle on")
    for mode in ("all", "one", "off"):
        ctl.cycleRepeat()
        await until(lambda: ctl.repeatMode == mode, what=f"repeat {mode}")
    ctl.setVolume(55)
    await until(lambda: ctl.volume == 55, what="volume 55")
    ctl.volumeUp()
    await until(lambda: ctl.volume == 60, what="volume up")
    ctl.volumeDown()
    await until(lambda: ctl.volume == 55, what="volume down")
    names = [c[0] for c in ma.calls]
    for cmd in ("play_pause", "next_track", "previous_track", "shuffle", "repeat", "volume_set"):
        assert cmd in names
    assert all(c[1] == TV for c in ma.calls if c[0] in ("play_pause", "next_track", "volume_set"))


# --- search and play ----------------------------------------------------------------------
async def test_search_then_play_now_next_and_add(house):
    ctl, ma = house.ctl, house.ma
    ctl.search("lanterns")
    await until(lambda: not ctl.libraryBusy and ctl.libraryRows, what="search results")
    found = rows_by_title(ctl)
    assert found["Tracks"] == ["Paper Moons", "Night Swim"]
    assert found["Artists"] == ["The Lanterns"]
    assert ctl.libraryError == ""
    assert ("search", "lanterns", True) in ma.calls       # the quick library-only pass first
    assert ("search", "lanterns", False) in ma.calls      # then everything

    paper, night = CATALOGUE[3].uri, CATALOGUE[4].uri
    ctl.playUri(paper, "next")
    await until(lambda: ma.titles()[1:2] == ["Paper Moons"], what="play next")
    ctl.playUri(night, "add")
    await until(lambda: ma.titles()[-1] == "Night Swim", what="add to queue")
    ctl.playUri(CATALOGUE[5].uri, "now")
    await until(lambda: ctl.title == "Tidal Love", what="play now")
    assert ctl.toast == ""


async def test_a_search_done_before_is_answered_from_memory(house):
    ctl, ma = house.ctl, house.ma
    ctl.search("comet")
    await until(lambda: not ctl.libraryBusy and ctl.libraryRows)
    asked = len([c for c in ma.calls if c[0] == "search"])
    ctl.search("Comet ")
    await settle(0.05)
    assert rows_by_title(ctl)["Tracks"] == ["Slow Comet"]
    assert len([c for c in ma.calls if c[0] == "search"]) == asked


async def test_recently_played_and_added_fill_an_empty_search(house):
    ctl = house.ctl
    ctl.loadRecents()
    await until(lambda: not ctl.libraryBusy and ctl.libraryRows)
    found = rows_by_title(ctl)
    assert found["Recently played"] == ["Paper Moons", "Night Swim"]
    assert found["Recently added"][0] == "Tidal Love"
    ctl.search("   ")           # emptying the search box goes back to them
    await until(lambda: not ctl.libraryBusy and "Recently played" in rows_by_title(ctl))


# --- the queue ------------------------------------------------------------------------------
async def test_queue_rows_follow_every_queue_action(house):
    ctl, ma = house.ctl, house.ma
    ctl.queueVisible = True
    await until(lambda: len(ctl.queueRows) == 3, what="queue rows")
    rows = ctl.queueRows
    assert [r["title"] for r in rows] == ["Neon Tide", "Glass Harbour", "Slow Comet"]
    assert rows[0]["current"] and not rows[1]["current"]
    assert rows[1]["duration"] == 200 and rows[1]["addedBy"] == ""

    def titles():
        return [r["title"] for r in ctl.queueRows]
    slow = rows[2]["itemId"]
    ctl.queueAction(slow, "up")
    await until(lambda: titles() == ["Neon Tide", "Slow Comet", "Glass Harbour"], what="moved up")
    ctl.queueAction(slow, "down")
    await until(lambda: titles() == ["Neon Tide", "Glass Harbour", "Slow Comet"], what="moved down")
    ctl.queueAction(slow, "next")
    await until(lambda: titles() == ["Neon Tide", "Slow Comet", "Glass Harbour"], what="play next")
    ctl.queueAction(slow, "remove")
    await until(lambda: titles() == ["Neon Tide", "Glass Harbour"], what="removed")
    glass = ctl.queueRows[1]["itemId"]
    ctl.queueAction(glass, "play")
    await until(lambda: ctl.title == "Glass Harbour", what="played from the queue")
    await until(lambda: titles() == ["Glass Harbour"], what="history hidden")
    assert ma.titles() == ["Neon Tide", "Glass Harbour"]
    assert ctl.toast == ""


# --- speakers and groups ------------------------------------------------------------------------
async def test_switch_sync_move_and_group_speakers(house):
    ctl, ma = house.ctl, house.ma
    assert speaker(ctl, KITCHEN)["canSync"] and not speaker(ctl, "den")["available"]

    ctl.speakerAction(KITCHEN, "sync")
    await until(lambda: speaker(ctl, KITCHEN)["syncedTo"] == TV, what="synced")
    ctl.speakerAction(KITCHEN, "unsync")
    await until(lambda: speaker(ctl, KITCHEN)["syncedTo"] == "", what="unsynced")

    ctl.speakerAction(KITCHEN, "transfer")
    await until(lambda: ma.titles(KITCHEN) == ["Neon Tide", "Glass Harbour", "Slow Comet"], what="moved")
    assert ma.titles(TV) == []

    ctl.controlSpeaker(KITCHEN)
    await until(lambda: speaker(ctl, KITCHEN)["controlled"], what="controlling the kitchen")
    assert ctl.title == "Neon Tide" and ctl.isPlaying
    assert ctl.speakerRows[0]["playerId"] == KITCHEN          # the controlled one comes first
    ctl.next()
    await until(lambda: ctl.title == "Glass Harbour")
    assert ("next_track", KITCHEN) in ma.calls

    ctl.createGroup([TV, KITCHEN])
    await until(lambda: any(r["isGroup"] for r in ctl.speakerRows), what="group made")
    group = next(r for r in ctl.speakerRows if r["isGroup"])
    assert group["name"] == "Living Room TV + Kitchen" and group["members"] == [TV, KITCHEN]
    ctl.editGroup(group["playerId"], [KITCHEN])
    await until(lambda: speaker(ctl, group["playerId"])["members"] == [KITCHEN], what="group edited")
    ctl.speakerAction(group["playerId"], "delete_group")
    await until(lambda: not any(r["isGroup"] for r in ctl.speakerRows), what="group deleted")

    ctl.controlSpeaker(TV)
    await until(lambda: speaker(ctl, TV)["controlled"])
    assert ctl.toast == ""


async def test_a_controlled_speaker_that_goes_offline_hands_back_to_this_tv(house):
    ctl, ma = house.ctl, house.ma
    ctl.controlSpeaker(KITCHEN)
    await until(lambda: speaker(ctl, KITCHEN)["controlled"])
    ma.players.items[KITCHEN].available = False
    ma.changed(player=KITCHEN)
    await until(lambda: speaker(ctl, TV)["controlled"], what="back to this TV")
    assert ctl.title == "Neon Tide"


# --- crossfade (Settings → This speaker) --------------------------------------------------------
async def test_crossfade_settings_reach_music_assistant(house):
    ctl, ma = house.ctl, house.ma
    ctl.loadCrossfade()
    await until(lambda: ctl.crossfadeKnown, what="crossfade read")
    assert not ctl.crossfadeEnabled and ctl.crossfadeSeconds == 8 and ctl.crossfadeLengthApplies
    ctl.toggleCrossfade()
    await until(lambda: ctl.crossfadeEnabled, what="crossfade on")
    ctl.setCrossfadeMode("smart_crossfade")
    await until(lambda: ctl.crossfadeModeLabel.startswith("Smart"), what="smart style")
    assert not ctl.crossfadeLengthApplies
    ctl.stepCrossfadeSeconds(1)
    await until(lambda: ctl.crossfadeSeconds == 9, what="longer")
    assert ma.config == {"crossfade_mode": "smart_crossfade", "server_crossfade_mode": "standard_crossfade",
                         "crossfade_duration": 9}
    assert ma.player_queues.items[TV].crossfade_enabled


# --- losing the server -------------------------------------------------------------------------
async def test_a_server_restart_reconnects_and_carries_on(house):
    ctl, ma = house.ctl, house.ma
    seen = []
    ctl.changed.connect(lambda: seen.append(ctl.connState))
    ma.drop()
    await until(lambda: "reconnecting" in seen, what="reconnecting shown")
    await until(lambda: ctl.connState == "connected" and ctl.title == "Neon Tide", what="back")
    assert ma.connects == 2
    ctl.next()
    await until(lambda: ctl.title == "Glass Harbour", what="controls work again")


async def test_actions_while_disconnected_say_so_and_never_crash(house):
    ctl, ma = house.ctl, house.ma
    ma.refuse_connect = ConnectionRefusedError("down")
    ma.drop()
    await until(lambda: ctl.connState != "connected", what="disconnected")
    calls = len(ma.calls)
    for action in (ctl.playPause, ctl.next, ctl.previous, ctl.toggleShuffle, ctl.cycleRepeat,
                   ctl.volumeUp, ctl.loadQueue, ctl.loadRecents, ctl.loadCrossfade):
        action()
    ctl.playUri(CATALOGUE[0].uri, "add")
    assert ctl.toast == "Couldn't add to the queue"
    ctl.queueAction("qi1", "remove")
    ctl.speakerAction(KITCHEN, "sync")
    ctl.search("anything")
    await until(lambda: not ctl.libraryBusy)
    assert ctl.libraryError != "" and ctl.speakerRows == [] and ctl.title == ""
    assert len(ma.calls) == calls                     # nothing reached the server
    ma.refuse_connect = None
    await until(lambda: ctl.connState == "connected" and ctl.title == "Neon Tide", timeout=5,
                what="reconnected by itself")


async def test_a_refused_token_asks_for_a_new_one_and_a_new_token_connects(house):
    ctl, ma = house.ctl, house.ma
    err = AuthenticationFailed("no")
    err.__cause__ = InvalidToken("bad token")
    ma.refuse_connect = err
    ma.drop()
    await until(lambda: ctl.connState == "auth_failed", what="auth failed")
    assert ctl.needsSetup or ctl.hasToken
    ma.refuse_connect = None
    ctl.saveConnection("http://ma.test:8095", "new-token")
    await until(lambda: ctl.connState == "connected", what="connected with the new token")


async def test_music_assistant_refusing_a_command_shows_a_toast(house):
    ctl, ma = house.ctl, house.ma
    ma.fail |= {"play_media", "delete_item", "set_members", "transfer_queue"}
    ctl.playUri(CATALOGUE[4].uri, "next")
    await until(lambda: ctl.toast == "Couldn't add it as next")
    ctl.clearToast()
    ctl.queueAction(ma.player_queues.items[TV].items[1].queue_item_id, "remove")
    await until(lambda: ctl.toast == "Couldn't remove it")
    ctl.speakerAction(KITCHEN, "sync")
    await until(lambda: ctl.toast == "Couldn't sync that speaker")
    ctl.speakerAction(KITCHEN, "transfer")
    await until(lambda: ctl.toast == "Couldn't move the queue")
    assert ma.titles() == ["Neon Tide", "Glass Harbour", "Slow Comet"]   # nothing changed
    ma.fail |= {"search"}
    ctl.search("tide")
    await until(lambda: not ctl.libraryBusy)
    assert ctl.libraryError == "Search failed — check the connection"


# --- settings are kept -------------------------------------------------------------------------
async def test_settings_changed_on_the_tv_are_there_after_a_restart(house):
    ctl = house.ctl
    ctl.cycleGuestSkips()
    ctl.cycleGuestBoosts()
    ctl.cycleGuestCooldown()
    ctl.setQrCaption("Add a song!")
    ctl.cycleLyricsSize()
    ctl.cycleLyricsLanguage()
    ctl.visualizerMode = "bars"
    ctl.visualizerEdges = True
    ctl.visualizerIntensity = 1.5
    ctl.setAccent(ctl.accents[1]["id"])
    ctl.lyricsEnabled = False
    port = free_port()
    ctl.setGuestPort(str(port))
    saved = load_settings()
    assert (saved.guest_skips, saved.guest_boosts, saved.guest_cooldown) == (
        ctl.guestSkips, ctl.guestBoosts, ctl.guestCooldown)
    assert saved.qr_caption == "Add a song!" and saved.guest_port == port
    assert saved.lyrics_size == ctl.lyricsSize and saved.lyrics_language == ctl.lyricsLanguage
    assert (saved.visualizer_mode, saved.visualizer_edges, saved.visualizer_intensity) == ("bars", True, 1.5)
    assert saved.accent == ctl.accents[1]["id"] and not saved.lyrics_enabled

    from couchside.ui.controller import AppController
    again = AppController(saved)
    try:
        assert (again.guestSkips, again.qrCaption, again.visualizerMode, again.guestPort) == (
            ctl.guestSkips, "Add a song!", "bars", port)
        assert again.accent1 == ctl.accent1 and not again.lyricsEnabled
    finally:
        await again.close()


# --- guest mode, from a phone ------------------------------------------------------------------
DEVICE, OTHER = "device-aaaaaaaa1", "device-bbbbbbbb2"


class Phone:
    """A guest's phone on the LAN, talking to the TV's guest page."""

    def __init__(self, http, base, device):
        self.http, self.base, self.device = http, base, device

    async def post(self, path, **body):
        async with self.http.post(self.base + "api/" + path, json={"deviceId": self.device, **body}) as r:
            return r.status, await r.json()

    async def get(self, path, **params):
        async with self.http.get(self.base + "api/" + path, params={"deviceId": self.device, **params}) as r:
            return r.status, await r.json()


@pytest.fixture
async def party(house):
    ctl = house.ctl
    ctl.toggleGuestMode()
    await until(lambda: ctl.guestUrl != "", what="guest link")
    port = house.settings.guest_port
    token = ctl.guestUrl.rstrip("/").rsplit("/", 1)[-1]
    base = f"http://127.0.0.1:{port}/g/{token}/"
    async with aiohttp.ClientSession() as http:
        for _ in range(100):           # the server starts in the background
            try:
                async with http.get(base) as r:
                    if r.status == 200:
                        break
            except aiohttp.ClientError:
                pass
            await settle(0.02)
        yield house, Phone(http, base, DEVICE), Phone(http, base, OTHER), http, base


async def test_guest_joins_searches_adds_boosts_and_skips(party):
    house, sam, alex, _http, _base = party
    ctl, ma = house.ctl, house.ma
    assert ctl.guestMode and ctl.qrRows and ctl.guestUrl.endswith("/")
    assert (await sam.post("join", name="Sam")) == (200, {"name": "Sam"})
    assert (await alex.post("join", name="Alex"))[0] == 200
    await until(lambda: ctl.guestCount == 2, what="two guests on the TV")
    assert sorted(r["name"] for r in ctl.guestRows) == ["Alex", "Sam"]

    status, body = await sam.get("search", q="lanterns")
    assert status == 200 and [r["title"] for r in body["results"]] == ["Paper Moons", "Night Swim"]

    assert (await sam.post("add", uri=CATALOGUE[3].uri))[0] == 200     # Paper Moons
    assert (await alex.get("search", q="night"))[0] == 200
    assert (await alex.post("add", uri=CATALOGUE[4].uri)) == (200, {"ok": True})  # Night Swim, after Sam's
    assert ma.titles()[:3] == ["Neon Tide", "Paper Moons", "Night Swim"]

    ctl.queueVisible = True
    await until(lambda: [r["addedBy"] for r in ctl.queueRows][:3] == ["", "Sam", "Alex"], what="credits")

    status, state = await alex.get("state")
    assert status == 200 and state["nowPlaying"]["title"] == "Neon Tide"
    mine = next(u for u in state["upcoming"] if u["mine"])
    assert mine["title"] == "Night Swim" and state["remaining"]["boosts"] == 2

    assert (await alex.post("boost", itemId=mine["itemId"]))[0] == 200
    assert ma.titles()[:3] == ["Neon Tide", "Night Swim", "Paper Moons"]

    current = state["nowPlaying"]["itemId"]
    assert (await sam.post("skip", currentItemId=current))[0] == 200
    await until(lambda: ctl.title == "Night Swim", what="skipped to Alex's song")
    await until(lambda: ctl.nowPlayingCredit != "", what="credit on Now Playing")
    assert "Alex" in ctl.nowPlayingCredit
    sam_row = next(r for r in ctl.guestRows if r["name"] == "Sam")
    assert sam_row["skipsLeft"] == 2


async def test_guest_limits_and_wrong_links_are_refused_with_a_reason(party):
    house, sam, alex, http, base = party
    ctl = house.ctl
    assert (await sam.post("skip", currentItemId="x"))[0] == 400            # not joined yet
    await sam.post("join", name="Sam")
    await alex.post("join", name="Alex")
    status, body = await alex.post("add", uri=CATALOGUE[3].uri)
    assert status == 400 and "from your search" in body["error"]          # only what they searched
    await sam.get("search", q="a")
    for n in range(3):
        assert (await sam.post("add", uri=CATALOGUE[3 + n].uri))[0] == 200
    status, body = await sam.post("add", uri=CATALOGUE[0].uri)
    assert status == 400 and "3 songs waiting" in body["error"]
    status, body = await sam.post("boost", itemId=house.ma.player_queues.items[TV].items[-1].queue_item_id)
    assert status == 400 and "own songs" in body["error"]
    status, _body = await sam.post("add", uri=CATALOGUE[1].uri)
    assert status == 429                                                     # too many, too fast
    status, body = await sam.post("admin/volume", level=10)
    assert status == 403 or "admin" in body.get("error", "").lower()
    async with http.get(base.replace(base.split("/g/")[1].split("/")[0], "not-the-token-123")) as r:
        assert r.status == 403
    assert ctl.volume == 40                                                  # untouched


async def test_admin_code_turns_a_guest_into_an_admin_with_every_admin_power(party):
    house, sam, alex, _http, _base = party
    ctl, ma = house.ctl, house.ma
    await sam.post("join", name="Sam")
    await alex.post("join", name="Alex")
    ctl.showAdminCode()
    code = ctl.adminCode
    assert len(code) == 6
    assert (await sam.post("code", code=code))[0] == 200
    await until(lambda: ctl.adminCode == "" and ctl.toast == "Sam is now an admin", what="admin toast")
    assert next(r for r in ctl.guestRows if r["name"] == "Sam")["admin"]

    status, state = await sam.get("state")
    assert state["admin"] and state["adminInfo"]["volume"] == 40
    assert (await sam.post("admin/volume", level=25))[0] == 200
    await until(lambda: ctl.volume == 25, what="admin volume")
    assert (await sam.post("admin/shuffle", on=True))[0] == 200
    await until(lambda: ctl.shuffle, what="admin shuffle")
    last = ma.player_queues.items[TV].items[-1].queue_item_id
    assert (await sam.post("admin/queue", itemId=last, action="remove"))[0] == 200
    assert ma.titles() == ["Neon Tide", "Glass Harbour"]
    assert (await sam.post("admin/speaker", playerId=KITCHEN, action="control"))[0] == 200
    await until(lambda: speaker(ctl, KITCHEN)["controlled"], what="admin switched speaker")
    assert (await sam.post("admin/speaker", playerId=TV, action="control"))[0] == 200
    await until(lambda: speaker(ctl, TV)["controlled"])
    alex_id = next(r["id"] for r in ctl.guestRows if r["name"] == "Alex")
    assert (await sam.post("admin/guest", guestId=alex_id, action="remove"))[0] == 200
    await until(lambda: [r["name"] for r in ctl.guestRows] == ["Sam"], what="alex removed")
    status, body = await alex.post("join", name="Alex")
    assert status == 403 and "removed" in body["error"]                      # stays out


async def test_the_host_manages_guests_from_the_tv(party):
    house, sam, _alex, _http, _base = party
    ctl = house.ctl
    await sam.post("join", name="Sam")
    await until(lambda: ctl.guestCount == 1)
    sam_id = ctl.guestRows[0]["id"]
    await sam.get("search", q="moons")
    await sam.post("add", uri=CATALOGUE[3].uri)
    await sam.post("skip", currentItemId=house.ma.player_queues.items[TV].current_id)
    await until(lambda: ctl.guestRows[0]["skipsLeft"] == 2)

    ctl.guestAction(sam_id, "reset")
    assert ctl.guestRows[0]["skipsLeft"] == 3 and "skips and boosts back" in ctl.toast
    ctl.guestAction(sam_id, "promote")
    assert ctl.guestRows[0]["admin"] and (await sam.get("state"))[1]["admin"]
    ctl.guestAction(sam_id, "revoke")
    assert not ctl.guestRows[0]["admin"] and not (await sam.get("state"))[1]["admin"]
    ctl.guestAction(sam_id, "remove")
    assert ctl.guestRows == [] and "removed" in ctl.toast


async def test_turning_guest_mode_off_closes_the_page_and_a_new_session_has_a_new_link(party):
    house, sam, _alex, http, base = party
    ctl = house.ctl
    await sam.post("join", name="Sam")
    old = ctl.guestUrl
    ctl.toggleGuestMode()
    assert not ctl.guestMode and ctl.guestUrl == "" and ctl.qrRows == [] and ctl.guestRows == []
    await settle(0.2)
    with pytest.raises(aiohttp.ClientError):
        async with http.get(base) as r:
            await r.read()
    ctl.toggleGuestMode()
    await until(lambda: ctl.guestUrl != "", what="new link")
    assert ctl.guestUrl != old
