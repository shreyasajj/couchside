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
                              "duration": 200, "current": True}]


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
