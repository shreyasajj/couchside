import asyncio

import pytest

QtCore = pytest.importorskip("PySide6.QtCore")

from couchside.core.playback import NowPlaying  # noqa: E402
from couchside.core.settings import AppSettings  # noqa: E402

PROXY = "http://ma:8095/imageproxy/abc?size=512&fmt=jpg"


@pytest.fixture
def ctl(tmp_path, monkeypatch, qt_app):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from couchside.ui.controller import AppController
    c = AppController(AppSettings())
    c.playback.now_playing = NowPlaying(
        "T", "A", "B", PROXY, "playing", duration=261, elapsed=12.5, elapsed_at=1000.0,
        shuffle=True, repeat="all", volume=40, palette_dark=(25, 28, 41), queue_id="q")
    return c


def test_progress_and_modes(ctl):
    assert ctl.hasDuration and ctl.duration == 261
    assert (ctl.positionBase, ctl.positionAt) == (12.5, 1000.0)
    assert ctl.shuffle and ctl.repeatMode == "all"
    assert ctl.volume == 40 and ctl.hasVolume
    assert ctl.backgroundColour == "#191c29"


def test_artwork_sizes(ctl):
    assert "size=1024" in ctl.artUrlLarge
    assert "size=1024" in ctl.artUrl  # 600 requested, proxy only serves 256/512/1024


def test_no_volume_control(ctl):
    from dataclasses import replace
    ctl.playback.now_playing = replace(ctl.playback.now_playing, volume=None, duration=None)
    assert ctl.volume == -1 and not ctl.hasVolume
    assert not ctl.hasDuration and ctl.duration == 0


def test_nothing_playing_defaults(ctl):
    ctl.playback.now_playing = None
    assert ctl.artUrl == "" and ctl.artUrlLarge == ""
    assert ctl.repeatMode == "off" and not ctl.shuffle and not ctl.hasVolume
    assert ctl.backgroundColour == "#0d0b1a"


def test_format_time_slot(ctl):
    assert ctl.formatTime(261) == "4:21"


async def test_slots_schedule_playback_commands(ctl, monkeypatch):
    calls = []

    def stub(name):
        async def f(*args):
            calls.append((name, *args))
        return f

    for name in ("cycle_repeat", "toggle_shuffle", "set_volume", "step_volume"):
        monkeypatch.setattr(ctl.playback, name, stub(name))
    ctl.cycleRepeat()
    ctl.toggleShuffle()
    ctl.setVolume(55)
    ctl.volumeUp()
    ctl.volumeDown()
    await asyncio.sleep(0)
    assert calls == [("cycle_repeat",), ("toggle_shuffle",), ("set_volume", 55),
                     ("step_volume", 5), ("step_volume", -5)]


# --- Phase 3: library, queue, speakers -------------------------------------------

from types import SimpleNamespace as NS  # noqa: E402

from couchside.core.connection import ConnState  # noqa: E402
from couchside.core.library import MediaCard, SearchOutcome  # noqa: E402
from couchside.core.queue import QueueRow  # noqa: E402

CARD = MediaCard("x://t/1", "track", "Song", "Artist", PROXY, "x://t/1")


def wire(ctl, players=()):
    by_id = {p.player_id: p for p in players}
    ctl.conn.client = NS(players=NS(get=by_id.get, __iter__=None), player_queues=NS(get=lambda q: None))
    ctl.conn.client.players = type("P", (), {"get": staticmethod(by_id.get),
                                             "__iter__": lambda self: iter(by_id.values())})()
    ctl.conn.state = ConnState.CONNECTED
    ctl.playback.active_player_id = "tv"


async def settle():
    for _ in range(5):
        await asyncio.sleep(0)


async def test_search_rows_shape(ctl, monkeypatch):
    wire(ctl)

    async def fake_search(client, q, limit=12):
        return SearchOutcome(rows=[("Tracks", [CARD])])
    monkeypatch.setattr("couchside.ui.controller.library.search", fake_search)
    ctl.search("love")
    await settle()
    assert ctl.libraryRows == [{"title": "Tracks", "items": [
        {"key": "x://t/1", "kind": "track", "title": "Song", "subtitle": "Artist",
         "imageUrl": PROXY.replace("size=512", "size=256"), "uri": "x://t/1"}]}]
    assert ctl.libraryError == "" and not ctl.libraryBusy


async def test_search_error_text(ctl, monkeypatch):
    wire(ctl)

    async def fake_search(client, q, limit=12):
        return SearchOutcome(error="Search failed — check the connection")
    monkeypatch.setattr("couchside.ui.controller.library.search", fake_search)
    ctl.search("love")
    await settle()
    assert ctl.libraryRows == [] and ctl.libraryError.startswith("Search failed")


async def test_play_uri_uses_controlled_player(ctl, monkeypatch):
    wire(ctl)
    calls = []

    async def fake_play(client, queue_id, uri, mode):
        calls.append((queue_id, uri, mode))
        return True
    monkeypatch.setattr("couchside.ui.controller.library.play", fake_play)
    ctl.playUri("x://t/1", "next")
    await settle()
    assert calls == [("tv", "x://t/1", "next")]


async def test_failed_action_sets_toast(ctl, monkeypatch):
    wire(ctl)

    async def fake_play(client, queue_id, uri, mode):
        return False
    monkeypatch.setattr("couchside.ui.controller.library.play", fake_play)
    ctl.playUri("x://t/1", "add")
    await settle()
    assert ctl.toast == "Couldn't add to the queue"
    ctl.clearToast()
    assert ctl.toast == ""


async def test_queue_rows_shape(ctl, monkeypatch):
    wire(ctl)

    async def fake_load(client, queue_id, current):
        return [QueueRow("a", "Song", "Artist", None, 200, True)]
    monkeypatch.setattr("couchside.ui.controller.queue.load_queue", fake_load)
    ctl.loadQueue()
    await settle()
    assert ctl.queueRows == [{"itemId": "a", "title": "Song", "subtitle": "Artist", "imageUrl": "",
                              "duration": 200, "current": True, "addedBy": ""}]


def test_speaker_rows_shape(ctl):
    tv = NS(player_id="tv", name="Living Room TV", available=True, enabled=True, type=NS(value="player"),
            group_members=[], can_group_with=["mac"], synced_to=None, current_media=None)
    mac = NS(player_id="mac", name="Mac mini", available=True, enabled=True, type=NS(value="player"),
             group_members=[], can_group_with=["tv"], synced_to=None, current_media=None)
    wire(ctl, [tv, mac])
    ctl.playback.local_player_found = True
    ctl._local_id = lambda: "tv"
    rows = ctl.speakerRows
    assert rows[0] == {"playerId": "tv", "name": "Living Room TV", "isGroup": False, "available": True,
                       "controlled": True, "local": True, "syncedTo": "", "members": [],
                       "canSync": False, "playing": ""}
    assert rows[1]["canSync"]


async def test_control_speaker_switches_playback(ctl):
    wire(ctl)
    refreshed = []
    ctl.playback.refresh = lambda: refreshed.append(1)
    ctl.controlSpeaker("mac")
    assert ctl.playback.user_player_id == "mac" and refreshed


def test_speakers_signal_only_when_rows_change(ctl):
    tv = NS(player_id="tv", name="TV", available=True, enabled=True, type=NS(value="player"),
            group_members=[], can_group_with=[], synced_to=None, current_media=None)
    wire(ctl, [tv])
    fired = []
    ctl.speakersChanged.connect(lambda: fired.append(1))
    evt = NS(event=NS(value="player_updated"), object_id="tv")
    ctl._on_event(evt)
    ctl._on_event(evt)           # nothing changed: no second signal
    tv.name = "Den TV"
    ctl._on_event(evt)
    assert len(fired) == 2


def test_queue_reload_only_on_item_or_current_change(ctl, monkeypatch):
    wire(ctl)
    loads = []
    monkeypatch.setattr(ctl, "loadQueue", lambda: loads.append(1))
    ctl._queue_visible = True
    current = ["a"]
    monkeypatch.setattr(ctl, "_current_item_id", lambda qid: current[0])
    upd = NS(event=NS(value="queue_updated"), object_id="tv")
    ctl._on_event(upd)
    ctl._on_event(upd)           # same current item: no reload
    current[0] = "b"
    ctl._on_event(upd)           # track changed
    ctl._on_event(NS(event=NS(value="queue_items_updated"), object_id="tv"))
    assert len(loads) == 3


async def test_queue_reloads_when_controlled_speaker_changes(ctl, monkeypatch):
    wire(ctl)
    loads = []
    monkeypatch.setattr(ctl, "loadQueue", lambda: loads.append(1))
    ctl._queue_visible = True
    ctl._on_update()                     # remembers the current queue (tv)
    loads.clear()
    ctl._on_update()                     # nothing changed
    assert loads == []
    ctl.playback.active_player_id = "mac"   # e.g. fell back / switched speaker
    ctl._on_update()
    assert loads == [1]


# --- Phase 4: lyrics -------------------------------------------------------------

from dataclasses import replace  # noqa: E402

from couchside.core.lyrics import LyricLine  # noqa: E402


class FakeLyrics:
    def __init__(self, result=None, gate=None):
        self.result, self.gate, self.asked = result, gate, []

    async def get(self, info):
        self.asked.append(info)
        if self.gate is not None:
            await self.gate.wait()
        return self.result


def song(ctl, uri, title="T"):
    ctl.playback.now_playing = replace(ctl.playback.now_playing, uri=uri, title=title)
    ctl._on_update()


async def test_lyrics_fetched_on_track_change(ctl):
    ctl._lyrics_fetcher = FakeLyrics([LyricLine(1.0, "hello")])
    song(ctl, "x://1")
    await settle()
    assert ctl.hasLyrics and ctl.lyricLines == [{"t": 1.0, "text": "hello", "sub": ""}]
    info = ctl._lyrics_fetcher.asked[0]
    assert (info.title, info.artist, info.album, info.duration, info.uri) == ("T", "A", "B", 261, "x://1")


async def test_stale_lyrics_dropped(ctl):
    gate = asyncio.Event()
    slow = FakeLyrics([LyricLine(1.0, "old song")], gate=gate)
    ctl._lyrics_fetcher = slow
    song(ctl, "x://1")
    await settle()
    ctl._lyrics_fetcher = FakeLyrics(None)
    song(ctl, "x://2")            # skipped before the first lookup finished
    gate.set()
    await settle()
    assert not ctl.hasLyrics and ctl.lyricLines == []


async def test_lyrics_disabled_skips_fetch(ctl):
    f = FakeLyrics([LyricLine(1.0, "x")])
    ctl._lyrics_fetcher = f
    ctl.lyricsEnabled = False
    song(ctl, "x://1")
    await settle()
    assert f.asked == [] and not ctl.hasLyrics
    ctl.lyricsEnabled = True           # turning it back on fetches for the current song
    await settle()
    assert ctl.hasLyrics


async def test_same_track_does_not_refetch(ctl):
    f = FakeLyrics([LyricLine(1.0, "x")])
    ctl._lyrics_fetcher = f
    song(ctl, "x://1")
    song(ctl, "x://1")
    await settle()
    assert len(f.asked) == 1


async def test_lyrics_pending_while_looking(ctl):
    gate = asyncio.Event()
    ctl._lyrics_fetcher = FakeLyrics([LyricLine(1.0, "x")], gate=gate)
    song(ctl, "x://1")
    await settle()
    assert ctl.lyricsPending and not ctl.hasLyrics
    gate.set()
    await settle()
    assert not ctl.lyricsPending and ctl.hasLyrics


async def test_metadata_change_on_same_uri_refetches(ctl):
    # A radio-style stream keeps its uri while the title changes.
    f = FakeLyrics(None)
    ctl._lyrics_fetcher = f
    song(ctl, "x://station", title="Song A")
    song(ctl, "x://station", title="Song B")
    await settle()
    assert [i.title for i in f.asked] == ["Song A", "Song B"]


def test_lyrics_size_cycles_and_saves(ctl, tmp_path):
    from couchside.core.settings import load_settings
    assert ctl.lyricsSize == "medium"
    ctl.cycleLyricsSize()
    assert ctl.lyricsSize == "large"
    ctl.cycleLyricsSize()
    assert ctl.lyricsSize == "small"
    assert load_settings().lyrics_size == "small"


def test_unknown_lyrics_size_reads_as_medium(ctl):
    ctl._settings.lyrics_size = "huge"
    assert ctl.lyricsSize == "medium"


# --- lyrics language / translation ---------------------------------------------------

PUNJABI = [LyricLine(1.0, "ਹਾਏ, ਨੀ old school ਜਿਹੀ ਏ"), LyricLine(2.0, ""), LyricLine(3.0, "ਲਾਲ ਗੱਲਾਂ")]
ENGLISH = [LyricLine(1.0, "I will shelter you"), LyricLine(2.0, "For days, for weeks, for years")]


class FakeTranslator:
    def __init__(self, result=None, gate=None):
        self.result, self.gate, self.asked = result, gate, []

    async def translate(self, lines):
        self.asked.append(lines)
        if self.gate is not None:
            await self.gate.wait()
        return self.result


async def lyrics_for(ctl, lines, uri="x://1"):
    ctl._lyrics_fetcher = FakeLyrics(lines)
    song(ctl, uri)
    await settle()


async def test_romanized_by_default(ctl):
    await lyrics_for(ctl, PUNJABI)
    assert [l["text"] for l in ctl.lyricLines] == ["hae, ni old school jihi e", "", "lal gallan"]
    assert all(l["sub"] == "" for l in ctl.lyricLines)


async def test_original_keeps_script(ctl):
    await lyrics_for(ctl, PUNJABI)
    ctl.cycleLyricsLanguage()                     # romanized -> original
    assert ctl.lyricsLanguage == "original"
    assert ctl.lyricLines[0]["text"] == "ਹਾਏ, ਨੀ old school ਜਿਹੀ ਏ"


async def test_english_only_hides_other_languages(ctl):
    await lyrics_for(ctl, PUNJABI)
    ctl.cycleLyricsLanguage()
    ctl.cycleLyricsLanguage()                     # -> english_only
    assert ctl.lyricsLanguage == "english_only" and not ctl.hasLyrics
    await lyrics_for(ctl, ENGLISH, uri="x://2")
    assert ctl.hasLyrics and ctl.lyricLines[0]["text"] == "I will shelter you"
    ctl.cycleLyricsLanguage()                     # back to romanized
    assert ctl.lyricsLanguage == "romanized"


async def test_translation_fills_lines_underneath(ctl, monkeypatch):
    t = FakeTranslator(["Hey, not like old school", "", "red things"])
    monkeypatch.setattr(ctl, "_translator", lambda: t)
    ctl.toggleLyricsTranslate()
    await lyrics_for(ctl, PUNJABI)
    await settle()
    assert [l["sub"] for l in ctl.lyricLines] == ["Hey, not like old school", "", "red things"]
    assert t.asked == [[l.text for l in PUNJABI]]  # the original text is translated


async def test_translation_off_or_english_sends_nothing(ctl, monkeypatch):
    t = FakeTranslator(["x"])
    monkeypatch.setattr(ctl, "_translator", lambda: t)
    await lyrics_for(ctl, PUNJABI)                # switch is off by default
    await lyrics_for(ctl, ENGLISH, uri="x://2")
    ctl.toggleLyricsTranslate()                   # on, but this song is already English
    await settle()
    assert t.asked == []


async def test_stale_translation_dropped(ctl, monkeypatch):
    gate = asyncio.Event()
    slow = FakeTranslator(["old", "", "old"], gate=gate)
    monkeypatch.setattr(ctl, "_translator", lambda: slow)
    ctl.toggleLyricsTranslate()
    await lyrics_for(ctl, PUNJABI)
    await lyrics_for(ctl, ENGLISH, uri="x://2")   # next song before the translation came back
    gate.set()
    await settle()
    assert all(l["sub"] == "" for l in ctl.lyricLines)


def test_translate_service_cycles_and_saves(ctl):
    from couchside.core.settings import load_settings
    assert ctl.translateService == "google"
    ctl.cycleTranslateService()
    assert ctl.translateService == "deepl"
    ctl.cycleTranslateService()
    assert ctl.translateService == "libretranslate"
    assert load_settings().translate_service == "libretranslate"
    ctl.setLibretranslateUrl(" http://pi:5000 ")
    assert ctl.libretranslateUrl == "http://pi:5000"


def test_deepl_key_saved_privately(ctl):
    from couchside.core.settings import load_secret
    assert not ctl.hasDeeplKey
    ctl.saveDeeplKey("abc:fx")
    assert ctl.hasDeeplKey and load_secret("deepl_key") == "abc:fx"


# --- Phase 5: guest mode ---------------------------------------------------------------

class FakeGuestServer:
    def __init__(self, *a, **k):
        self.started = self.stopped = 0
        self.notified = 0

    async def start(self):
        self.started += 1

    async def stop(self):
        self.stopped += 1

    def notify_changed(self):
        self.notified += 1


@pytest.fixture
def guest_ctl(ctl, monkeypatch):
    fake = FakeGuestServer()
    monkeypatch.setattr(ctl, "_make_guest_server", lambda: fake)
    calls = []

    def fake_lan_ip(probe=""):
        calls.append(probe)
        return "192.168.30.153"
    monkeypatch.setattr("couchside.ui.controller.lan_ip", fake_lan_ip)
    ctl._fake_server = fake
    ctl._lan_calls = calls
    return ctl


async def settle_long():
    for _ in range(100):
        await asyncio.sleep(0.002)


async def test_guest_mode_starts_server_and_rotates_link(guest_ctl):
    ctl = guest_ctl
    assert not ctl.guestMode and ctl.guestUrl == ""
    ctl.toggleGuestMode()
    await settle_long()
    assert ctl.guestMode and ctl._fake_server.started == 1
    first = ctl.guestUrl
    assert first.startswith("http://192.168.30.153:8765/g/") and first.endswith("/")
    ctl.toggleGuestMode()
    await settle_long()
    assert not ctl.guestMode and ctl._fake_server.stopped == 1 and ctl.guestUrl == ""
    ctl.toggleGuestMode()
    await settle_long()
    assert ctl.guestUrl != first  # new link every time


async def test_guest_url_uses_public_url(guest_ctl):
    ctl = guest_ctl
    ctl.setGuestPublicUrl(" https://party.example.com/ ")
    ctl.toggleGuestMode()
    await settle_long()
    assert ctl.guestUrl.startswith("https://party.example.com/g/")


async def test_qr_rows_encode_the_link(guest_ctl):
    ctl = guest_ctl
    ctl.toggleGuestMode()
    await settle_long()
    rows = ctl.qrRows
    assert len(rows) >= 21 and all(len(r) == len(rows) for r in rows)
    assert rows[0].startswith("1111111")  # finder pattern
    assert set("".join(rows)) <= {"0", "1"}


async def test_guest_rules_cycle_save_and_apply_live(guest_ctl):
    from couchside.core.settings import load_settings
    ctl = guest_ctl
    ctl.toggleGuestMode()
    await settle_long()
    before = ctl.guestSkips
    ctl.cycleGuestSkips()
    assert ctl.guestSkips != before
    assert load_settings().guest_skips == ctl.guestSkips
    assert ctl._guest_session.rules.skips == ctl.guestSkips
    for slot, prop in (("cycleGuestBoosts", "guestBoosts"), ("cycleGuestMaxWaiting", "guestMaxWaiting"),
                       ("cycleGuestCooldown", "guestCooldown")):
        old = getattr(ctl, prop)
        getattr(ctl, slot)()
        assert getattr(ctl, prop) != old


async def test_credits_on_queue_rows_and_now_playing(guest_ctl, monkeypatch):
    ctl = guest_ctl
    wire(ctl)
    ctl.toggleGuestMode()
    await settle_long()
    g = ctl._guest_session.join("device-abcdef12", "Sam")
    ctl._guest_session.note_added(g, "a", now=0)

    async def fake_load(client, queue_id, current):
        return [QueueRow("a", "Song", "Artist", None, 200, True), QueueRow("b", "Other", "X", None, 100, False)]
    monkeypatch.setattr("couchside.ui.controller.queue.load_queue", fake_load)
    monkeypatch.setattr(ctl, "_current_item_id", lambda qid: "a")
    ctl.loadQueue()
    await settle()
    assert [r["addedBy"] for r in ctl.queueRows] == ["Sam", ""]
    assert ctl.nowPlayingCredit == "Sam"


async def test_guests_notified_on_queue_changes(guest_ctl, monkeypatch):
    ctl = guest_ctl
    wire(ctl)
    ctl.toggleGuestMode()
    await settle_long()
    ctl._on_event(NS(event=NS(value="queue_items_updated"), object_id="tv"))
    assert ctl._fake_server.notified >= 1


async def test_qr_link_worked_out_once_per_session(guest_ctl):
    ctl = guest_ctl
    ctl.toggleGuestMode()
    await settle_long()
    for _ in range(5):
        ctl.guestUrl, ctl.qrRows
        ctl.guestChanged.emit()          # joins, adds, song changes
    assert len(ctl._lan_calls) == 1
    ctl.toggleGuestMode()
    await settle_long()
    ctl.toggleGuestMode()                # new session: worked out again
    await settle_long()
    assert len(ctl._lan_calls) == 2


# --- Phase 6: admin access ---------------------------------------------------------------

async def guests_on(ctl):
    ctl.toggleGuestMode()
    await settle_long()
    s = ctl._guest_session
    return s, s.join("device-aaaaaaaa", "Ana"), s.join("device-bbbbbbbb", "Ben")


async def test_guest_rows_for_the_tv(guest_ctl):
    ctl = guest_ctl
    assert ctl.guestRows == []
    s, ana, ben = await guests_on(ctl)
    ben.skips_used = 1
    rows = ctl.guestRows
    assert [(r["id"], r["name"], r["admin"]) for r in rows] == [(ana.public_id, "Ana", False), (ben.public_id, "Ben", False)]
    assert rows[1]["skipsLeft"] == s.rules.skips - 1
    assert "device" not in repr(rows)


async def test_guest_actions_from_the_tv(guest_ctl):
    ctl = guest_ctl
    s, ana, ben = await guests_on(ctl)
    seen = []
    ctl.guestChanged.connect(lambda: seen.append(1))
    ctl.guestAction(ana.public_id, "promote")
    assert ana.admin and "Ana" in ctl.toast
    ctl.guestAction(ana.public_id, "revoke")
    assert not ana.admin
    ben.skips_used = 2
    ctl.guestAction(ben.public_id, "reset")
    assert ben.skips_used == 0
    ctl.guestAction(ben.public_id, "remove")
    assert "device-bbbbbbbb" not in s.guests
    ctl.guestAction("gone", "promote")  # a guest who left: no crash
    assert seen and ctl._fake_server.notified >= 4


async def test_admin_code_shown_and_cancelled(guest_ctl):
    ctl = guest_ctl
    assert ctl.adminCode == ""
    ctl.showAdminCode()  # guest mode off: nothing
    assert ctl.adminCode == ""
    s, ana, _ = await guests_on(ctl)
    ctl.showAdminCode()
    code = ctl.adminCode
    assert len(code) == 6 and s.admin_code == code
    ctl.closeAdminCode()
    assert ctl.adminCode == "" and s.admin_code is None


async def test_admin_code_used_closes_it_with_a_toast(guest_ctl):
    ctl = guest_ctl
    s, ana, _ = await guests_on(ctl)
    ctl.showAdminCode()
    s.redeem_code(ana, ctl.adminCode, now=__import__("time").time())
    ctl._on_admin_event("admin", "Ana")
    assert ctl.adminCode == "" and "Ana is now an admin" in ctl.toast
    ctl.showAdminCode()
    ctl._on_admin_event("code_cancelled", "")
    assert "cancelled" in ctl.toast


async def test_admin_code_expires(guest_ctl, monkeypatch):
    ctl = guest_ctl
    await guests_on(ctl)
    ctl.showAdminCode()
    s = ctl._guest_session
    s.code_expires = 0  # long gone
    assert ctl.adminCode == ""


async def test_admin_host_reflects_the_tv(guest_ctl, monkeypatch):
    ctl = guest_ctl
    wire(ctl)
    host = ctl._admin_host()
    assert host.volume() == 40 and host.shuffle() is True
    calls = []

    async def fake_cmd(name, value):
        calls.append((name, value))
    monkeypatch.setattr(ctl.playback, "_queue_command", fake_cmd)
    await host.set_shuffle(True)   # already on: nothing to do
    await host.set_shuffle(False)
    assert calls == [("shuffle", False)]
    ctl.conn.client = None
    assert ctl._admin_host() is None


# --- Phase 7: Sendspin settings, versions and updates ------------------------------------

def test_sendspin_settings_cycle_and_save(ctl, tmp_path):
    from couchside.core.settings import load_settings
    assert ctl.sendspinDelay == 0
    ctl.cycleSendspinDelay()
    assert ctl.sendspinDelay == 25
    ctl._audio_devices = ["HD-Audio Generic: HISENSE (hw:0,3)", "pulse"]
    assert ctl.audioDevice == "Default"
    ctl.cycleAudioDevice()
    assert ctl.audioDevice == "HD-Audio Generic: HISENSE (hw:0,3)"
    ctl.cycleAudioDevice()
    ctl.cycleAudioDevice()
    assert ctl.audioDevice == "Default"
    ctl.setPlayerName("  Den TV  ")
    ctl.setPlayerName("   ")  # ignored
    saved = load_settings()
    assert saved.player_name == "Den TV" and ctl.playerName == "Den TV"
    assert saved.sendspin_delay_ms == 25 and saved.sendspin_audio_device is None


async def test_audio_devices_loaded_from_sendspin(ctl, monkeypatch):
    async def fake_list():
        return ["Speaker A", "Speaker B"]
    monkeypatch.setattr(ctl, "_list_audio_devices", fake_list)
    ctl.loadAudioDevices()
    await settle()
    assert ctl._audio_devices == ["Speaker A", "Speaker B"]


async def test_sendspin_version_text(ctl, monkeypatch):
    import couchside.ui.controller as c
    monkeypatch.setattr(c.updates, "bundled_sendspin_version", lambda: "9.1.0")

    async def latest(_http):
        return "9.2.0"
    monkeypatch.setattr(c.updates, "latest_sendspin_version", latest)
    assert "9.1.0" in ctl.sendspinVersionText
    await ctl.check_sendspin_version()
    assert ctl.sendspinVersionText == "9.1.0 · 9.2.0 available"

    async def none(_http):
        return None
    monkeypatch.setattr(c.updates, "latest_sendspin_version", none)
    await ctl.check_sendspin_version()
    assert ctl.sendspinVersionText == "9.1.0 · couldn't check for a newer one"

    async def same(_http):
        return "9.1.0"
    monkeypatch.setattr(c.updates, "latest_sendspin_version", same)
    await ctl.check_sendspin_version()
    assert ctl.sendspinVersionText == "9.1.0 · up to date"


class FakeUpdater:
    def __init__(self, ok=True):
        self.ok, self.spawned, self.updates = ok, [], 0

    async def start(self, on_available, on_progress):
        self.on_available, self.on_progress = on_available, on_progress
        return self.ok

    async def update(self):
        self.updates += 1
        return True

    async def spawn_latest(self, argv, env=None):
        self.spawned.append(argv)
        return 1


async def test_update_unavailable_outside_a_published_install(ctl):
    up = FakeUpdater(ok=False)
    await ctl.start_update_monitor(up)
    assert ctl.updateState == "unavailable" and "published" in ctl.updateText
    ctl.installUpdate()  # nothing to install: no crash
    await settle()
    assert up.updates == 0


async def test_update_flow_restarts_sendspin_and_the_app(ctl, monkeypatch):
    import couchside.ui.controller as c
    from couchside.core.flatpak_portal import Progress
    up = FakeUpdater()
    await ctl.start_update_monitor(up)
    assert ctl.updateState == "current"
    up.on_available({"remote-commit": "new"})
    assert ctl.updateState == "available" and "Update available" in ctl.updateText
    exits, quits = [], []
    monkeypatch.setattr(c, "request_exit", lambda: exits.append(1))

    async def freed(timeout):
        return True
    monkeypatch.setattr(ctl, "_wait_sendspin_stopped", freed)
    monkeypatch.setattr(ctl, "_quit_app", lambda: quits.append(1))
    ctl.installUpdate()
    await settle()
    assert up.updates == 1 and ctl.updateState == "updating"
    up.on_progress(Progress("running", 40, ""))
    assert "40" in ctl.updateText
    up.on_progress(Progress("done", 100, ""))
    for _ in range(20):
        await settle()
    assert exits == [1]
    assert up.spawned == [["couchside-sendspin"], ["couchside"]]
    assert quits == [1] and ctl.updateState == "restarting"


async def test_failed_update_keeps_running_and_says_why(ctl):
    from couchside.core.flatpak_portal import Progress
    up = FakeUpdater()
    await ctl.start_update_monitor(up)
    up.on_available({})
    ctl.installUpdate()
    await settle()
    up.on_progress(Progress("failed", 0, "No space left"))
    assert ctl.updateState == "available" and "No space left" in ctl.toast


async def test_published_release_offers_the_update_at_once(ctl, monkeypatch):
    import couchside.ui.controller as c
    monkeypatch.setattr(c.updates, "build_info", lambda: {"version": "0.7.2", "commit": "", "feed": "https://f/latest.json"})

    async def newer(_http, feed):
        return "0.7.3"
    monkeypatch.setattr(c.updates, "latest_app_version", newer)
    up = FakeUpdater()
    await ctl.start_update_monitor(up)
    await ctl.check_app_version()
    assert ctl.updateState == "available"


async def test_feed_ignored_without_the_portal_or_when_current(ctl, monkeypatch):
    import couchside.ui.controller as c
    monkeypatch.setattr(c.updates, "build_info", lambda: {"version": "0.7.3", "commit": "", "feed": "https://f/latest.json"})

    async def same(_http, feed):
        return "0.7.3"
    monkeypatch.setattr(c.updates, "latest_app_version", same)
    await ctl.start_update_monitor(FakeUpdater())
    await ctl.check_app_version()
    assert ctl.updateState == "current"
    await ctl.start_update_monitor(FakeUpdater(ok=False))
    await ctl.check_app_version()
    assert ctl.updateState == "unavailable"


async def test_failed_relaunch_starts_the_speaker_again(ctl, monkeypatch):
    import couchside.ui.controller as c
    from couchside.core.flatpak_portal import Progress
    up = FakeUpdater()

    async def broken(argv, env=None):
        raise RuntimeError("portal said no")
    up.spawn_latest = broken
    await ctl.start_update_monitor(up)
    up.on_available({})
    monkeypatch.setattr(c, "request_exit", lambda: None)

    async def freed(timeout):
        return True
    monkeypatch.setattr(ctl, "_wait_sendspin_stopped", freed)
    started, quits = [], []
    monkeypatch.setattr(ctl, "_start_local_sendspin", lambda: started.append(1))
    monkeypatch.setattr(ctl, "_quit_app", lambda: quits.append(1))
    ctl.installUpdate()
    await settle()
    up.on_progress(Progress("done", 100, ""))
    for _ in range(20):
        await settle()
    assert started == [1] and quits == [] and "restart Couchside" in ctl.toast


async def test_nothing_to_install_does_not_restart(ctl, monkeypatch):
    from couchside.core.flatpak_portal import Progress
    up = FakeUpdater()
    await ctl.start_update_monitor(up)
    ctl._update_state = "available"  # offered by the release feed; the repo isn't there yet
    restarts = []

    async def restart():
        restarts.append(1)
    monkeypatch.setattr(ctl, "_restart_into_update", restart)
    ctl.installUpdate()
    await settle()
    up.on_progress(Progress("empty", 0, ""))
    await settle()
    assert restarts == [] and ctl.updateState == "current" and "few minutes" in ctl.toast


async def test_already_installed_update_restarts_into_it(ctl, monkeypatch):
    from couchside.core.flatpak_portal import Progress
    up = FakeUpdater()
    await ctl.start_update_monitor(up)
    up.on_available({"running-commit": "old", "local-commit": "new", "remote-commit": "new"})
    restarts = []

    async def restart():
        restarts.append(1)
    monkeypatch.setattr(ctl, "_restart_into_update", restart)
    ctl.installUpdate()
    await settle()
    up.on_progress(Progress("empty", 0, ""))
    await settle()
    assert restarts == [1]


# --- Phase 8: visualizer and party mode ---------------------------------------------------

class FakePulse:
    def __init__(self):
        self.running, self.starts, self.stops = False, 0, 0
        self.level, self.beats = 0.0, 0

    def start(self):
        self.starts += 1
        self.running = True
        return True

    def stop(self):
        self.stops += 1
        self.running = False
        self.level = 0.0


@pytest.fixture
def pulse_ctl(ctl):
    ctl._pulse = FakePulse()
    return ctl


async def test_listens_only_while_shown_and_playing(pulse_ctl):
    from dataclasses import replace
    ctl = pulse_ctl
    assert ctl.visualizerEnabled is True and not ctl._pulse.running
    ctl.pulseVisible = True                 # Now Playing on screen, music playing
    assert ctl._pulse.running
    ctl.playback.now_playing = replace(ctl.playback.now_playing, state="paused")
    ctl._on_update()
    assert not ctl._pulse.running           # paused: nothing to hear
    ctl.playback.now_playing = replace(ctl.playback.now_playing, state="playing")
    ctl._on_update()
    assert ctl._pulse.running
    ctl.pulseVisible = False                # another page or app in front
    assert not ctl._pulse.running


def test_visualizer_off_stops_listening_but_party_mode_still_listens(pulse_ctl, tmp_path):
    from couchside.core.settings import load_settings
    ctl = pulse_ctl
    ctl.pulseVisible = True
    ctl.visualizerEnabled = False
    assert not ctl._pulse.running and load_settings().visualizer_enabled is False
    ctl.togglePartyMode()
    assert ctl.partyMode and ctl._pulse.running
    ctl.togglePartyMode()
    assert not ctl.partyMode and not ctl._pulse.running


def test_pulse_swells_on_beats_and_settles(pulse_ctl):
    ctl = pulse_ctl
    ctl.pulseVisible = True
    seen, other = [], []
    ctl.levelChanged.connect(lambda: seen.append(ctl.audioPulse))
    ctl.pulseChanged.connect(lambda: other.append(1))
    ctl._pulse.level = 0.5
    ctl._poll_pulse()
    assert ctl.audioPulse == 0.3            # level alone, scaled
    ctl._pulse.beats = 1
    ctl._poll_pulse()
    assert ctl.audioPulse == 1.0            # a beat: full swell
    for _ in range(8):
        ctl._poll_pulse()
    assert ctl.audioPulse == 0.3            # decayed back to the level
    n = len(seen)
    ctl._pulse.level = 0.51                 # same 0.05 step: no signal, no redraw
    ctl._poll_pulse()
    assert len(seen) == n and other == []
