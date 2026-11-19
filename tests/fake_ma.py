"""A small, stateful Music Assistant server for tests: players, queues, a music catalogue
and the events MA sends when they change. It stands in for MusicAssistantClient, so the
real Connection, Playback, controller and guest server run on top of it unchanged.

Every command is recorded in `calls` as (name, *args). Put a command's name in `fail` to
make it raise, the way a refusing or broken server would.
"""

from __future__ import annotations

import asyncio
import itertools
import time
from types import SimpleNamespace as NS
from typing import Any

TV = "tv-sendspin"        # this TV's Sendspin player (its client id)
KITCHEN = "kitchen"
DEN = "den"               # offline


def track(n: int, title: str, artist: str = "Marisol Vega", album: str = "Afterglow",
          duration: int = 200) -> NS:
    return NS(name=title, uri=f"library://track/{n}", artist_str=artist, album=NS(name=album),
              media_type=NS(value="track"), duration=duration, image=None,
              metadata=NS(lrc_lyrics=None))


CATALOGUE = [
    track(1, "Neon Tide"), track(2, "Glass Harbour"), track(3, "Slow Comet"),
    track(4, "Paper Moons", artist="The Lanterns", album="Low Light"),
    track(5, "Night Swim", artist="The Lanterns", album="Low Light"),
    track(6, "Tidal Love", artist="Aria Stone", album="Blue"),
]
ALBUMS = [NS(name="Afterglow", uri="library://album/1", artist_str="Marisol Vega",
             media_type=NS(value="album"), image=None)]
ARTISTS = [NS(name="The Lanterns", uri="library://artist/1", media_type=NS(value="artist"), image=None)]
PLAYLISTS = [NS(name="Party Mix", uri="library://playlist/1", owner="Host",
                media_type=NS(value="playlist"), image=None)]
RADIO = [NS(name="Night FM", uri="library://radio/1", media_type=NS(value="radio"), image=None)]


class _Failing:
    def __init__(self, ma: FakeMA) -> None:
        self._ma = ma

    def _call(self, name: str, *args: Any) -> None:
        self._ma.calls.append((name, *args))
        if name in self._ma.fail:
            raise RuntimeError(f"{name} refused")


class FakeQueue:
    def __init__(self, queue_id: str) -> None:
        self.queue_id = queue_id
        self.items: list[NS] = []
        self.current_id: str | None = None
        self.shuffle_enabled = False
        self.repeat_mode = "off"
        self.crossfade_enabled = False
        self.elapsed_time = 0.0
        self.elapsed_time_last_updated = time.time()

    def _index(self) -> int | None:
        ids = [i.queue_item_id for i in self.items]
        return ids.index(self.current_id) if self.current_id in ids else None

    @property
    def current_index(self) -> int | None:
        return self._index()

    @property
    def current_item(self) -> NS | None:
        i = self._index()
        return self.items[i] if i is not None else None

    @property
    def next_item(self) -> NS | None:
        i = self._index()
        return self.items[i + 1] if i is not None and i + 1 < len(self.items) else None


class FakePlayers(_Failing):
    def __init__(self, ma: FakeMA) -> None:
        super().__init__(ma)
        self.items: dict[str, NS] = {}

    def add(self, pid: str, name: str, *, available: bool = True, group: bool = False,
            members: list[str] | None = None, can_group_with: list[str] | None = None) -> NS:
        p = NS(player_id=pid, name=name, available=available, enabled=True,
               type=NS(value="group" if group else "player"), group_members=list(members or []),
               can_group_with=list(can_group_with or []), synced_to=None, current_media=None,
               active_source=None, playback_state="idle", volume_control="internal", volume_level=40,
               output_protocols=[])
        self.items[pid] = p
        return p

    def __iter__(self):
        return iter(list(self.items.values()))

    def get(self, pid: str) -> NS | None:
        return self.items.get(pid)

    async def play_pause(self, pid: str) -> None:
        self._call("play_pause", pid)
        p = self.items[pid]
        p.playback_state = "paused" if p.playback_state == "playing" else "playing"
        self._ma.changed(player=pid)

    async def next_track(self, pid: str) -> None:
        self._call("next_track", pid)
        self._ma.step(pid, 1)

    async def previous_track(self, pid: str) -> None:
        self._call("previous_track", pid)
        self._ma.step(pid, -1)

    async def volume_set(self, pid: str, level: int) -> None:
        self._call("volume_set", pid, level)
        self.items[pid].volume_level = level
        self._ma.changed(player=pid)

    async def set_members(self, target: str, player_ids_to_add=None, player_ids_to_remove=None) -> None:
        self._call("set_members", target, list(player_ids_to_add or []), list(player_ids_to_remove or []))
        leader = self.items[target]
        for pid in player_ids_to_add or []:
            if pid not in leader.group_members:
                leader.group_members.append(pid)
            if leader.type.value != "group":
                self.items[pid].synced_to = target
        for pid in player_ids_to_remove or []:
            if pid in leader.group_members:
                leader.group_members.remove(pid)
            self.items[pid].synced_to = None
        self._ma.changed(player=target)

    async def create_group_player(self, provider: str, name: str, members: list[str]) -> NS:
        self._call("create_group_player", provider, name, list(members))
        pid = f"group-{next(self._ma.ids)}"
        group = self.add(pid, name, group=True, members=members)
        self._ma.changed(player=pid, kind="player_added")
        return group

    async def remove_group_player(self, pid: str) -> None:
        self._call("remove_group_player", pid)
        self.items.pop(pid, None)
        self._ma.changed(player=pid, kind="player_removed")


class FakeQueues(_Failing):
    def __init__(self, ma: FakeMA) -> None:
        super().__init__(ma)
        self.items: dict[str, FakeQueue] = {}

    def get(self, qid: str) -> FakeQueue | None:
        return self.items.get(qid)

    async def get_queue_items(self, qid: str, limit: int = 500, offset: int = 0) -> list[NS]:
        self._call("get_queue_items", qid)
        return list(self.items[qid].items[offset:offset + limit])

    async def play_media(self, qid: str, media: str, option: Any = None) -> None:
        mode = str(getattr(option, "value", option) or "play")
        self._call("play_media", qid, media, mode)
        q = self.items[qid]
        item = self._ma.queue_item(media)
        i = q._index()
        if mode == "add" or i is None:
            q.items.append(item)
        else:
            q.items.insert(i + 1, item)
        if mode == "play" or q.current_id is None:
            q.current_id = item.queue_item_id
            self._ma.players.items[qid].playback_state = "playing"
        self._ma.changed(queue=qid, items=True)

    def _move(self, qid: str, item_id: str, to: int) -> None:
        q = self.items[qid]
        ids = [i.queue_item_id for i in q.items]
        it = q.items.pop(ids.index(item_id))
        q.items.insert(max(0, min(len(q.items), to)), it)
        self._ma.changed(queue=qid, items=True)

    async def move_item(self, qid: str, item_id: str, pos_shift: int = 1) -> None:
        self._call("move_item", qid, item_id, pos_shift)
        ids = [i.queue_item_id for i in self.items[qid].items]
        self._move(qid, item_id, ids.index(item_id) + pos_shift)

    async def move_up(self, qid: str, item_id: str) -> None:
        self._call("move_up", qid, item_id)
        ids = [i.queue_item_id for i in self.items[qid].items]
        self._move(qid, item_id, ids.index(item_id) - 1)

    async def move_down(self, qid: str, item_id: str) -> None:
        self._call("move_down", qid, item_id)
        ids = [i.queue_item_id for i in self.items[qid].items]
        self._move(qid, item_id, ids.index(item_id) + 1)

    async def move_next(self, qid: str, item_id: str) -> None:
        self._call("move_next", qid, item_id)
        q = self.items[qid]
        ids = [i.queue_item_id for i in q.items]
        it = q.items.pop(ids.index(item_id))
        cur = q._index()
        q.items.insert(0 if cur is None else cur + 1, it)
        self._ma.changed(queue=qid, items=True)

    async def delete_item(self, qid: str, item_id: str) -> None:
        self._call("delete_item", qid, item_id)
        q = self.items[qid]
        q.items = [i for i in q.items if i.queue_item_id != item_id]
        self._ma.changed(queue=qid, items=True)

    async def play_index(self, qid: str, item_id: str) -> None:
        self._call("play_index", qid, item_id)
        self.items[qid].current_id = item_id
        self._ma.players.items[qid].playback_state = "playing"
        self._ma.changed(queue=qid)

    async def shuffle(self, qid: str, enabled: bool) -> None:
        self._call("shuffle", qid, enabled)
        self.items[qid].shuffle_enabled = enabled
        self._ma.changed(queue=qid)

    async def repeat(self, qid: str, mode: Any) -> None:
        value = str(getattr(mode, "value", mode))
        self._call("repeat", qid, value)
        self.items[qid].repeat_mode = value
        self._ma.changed(queue=qid)

    async def transfer_queue(self, source: str, target: str, auto_play: bool = False) -> None:
        self._call("transfer_queue", source, target, auto_play)
        src, dst = self.items[source], self.items.setdefault(target, FakeQueue(target))
        dst.items, dst.current_id = src.items, src.current_id
        src.items, src.current_id = [], None
        self._ma.players.items[target].playback_state = "playing" if auto_play else "idle"
        self._ma.players.items[source].playback_state = "idle"
        self._ma.changed(queue=source, items=True)
        self._ma.changed(queue=target, items=True)


class FakeMusic(_Failing):
    def __init__(self, ma: FakeMA) -> None:
        super().__init__(ma)
        self.played: list[NS] = []

    def get_media_item_image(self, item: Any, *_: Any) -> Any:
        return getattr(item, "image", None)

    async def search(self, query: str, media_types=None, limit: int = 12, library_only: bool = False) -> NS:
        self._call("search", query, library_only)
        q = query.lower()

        def hits(items, *fields):
            found = [i for i in items if any(q in str(getattr(i, f, "") or "").lower() for f in fields)]
            return found[:limit]
        return NS(tracks=hits(CATALOGUE, "name", "artist_str"), albums=hits(ALBUMS, "name", "artist_str"),
                  artists=hits(ARTISTS, "name"), playlists=hits(PLAYLISTS, "name"), radio=hits(RADIO, "name"))

    async def recently_played(self, limit: int = 10) -> list[NS]:
        self._call("recently_played")
        return self.played[:limit]

    async def get_library_tracks(self, limit: int | None = None, order_by: str | None = None) -> list[NS]:
        self._call("get_library_tracks", order_by)
        return list(reversed(CATALOGUE))[:limit]

    async def get_item_by_uri(self, uri: str) -> NS | None:
        self._call("get_item_by_uri", uri)
        return next((t for t in CATALOGUE if t.uri == uri), None)


class FakeMA:
    """One Music Assistant server. `connect()`/`start_listening()` behave like the real
    client: start_listening reports the initial state, then runs until `drop()`."""

    def __init__(self, base_url: str = "http://ma.test:8095") -> None:
        self.server_info = NS(base_url=base_url, server_id="fake-ma")
        self.calls: list[tuple] = []
        self.fail: set[str] = set()
        self.ids = itertools.count(1)
        self.players = FakePlayers(self)
        self.player_queues = FakeQueues(self)
        self.music = FakeMusic(self)
        self.config = {"crossfade_mode": "global", "server_crossfade_mode": "standard_crossfade",
                       "crossfade_duration": 8}
        self._subs: list = []
        self._dropped: asyncio.Event | None = None
        self.connects = 0
        self.refuse_connect: Exception | None = None

    # --- the house --------------------------------------------------------------------
    @classmethod
    def house(cls) -> FakeMA:
        """This TV playing a three-song queue, a kitchen speaker it can sync with, an
        offline den speaker."""
        ma = cls()
        ma.players.add(TV, "Living Room TV", can_group_with=[KITCHEN])
        ma.players.add(KITCHEN, "Kitchen", can_group_with=[TV])
        ma.players.add(DEN, "Den", available=False)
        for pid in (TV, KITCHEN, DEN):
            ma.player_queues.items[pid] = FakeQueue(pid)
        q = ma.player_queues.items[TV]
        q.items = [ma.queue_item(t.uri) for t in CATALOGUE[:3]]
        q.current_id = q.items[0].queue_item_id
        ma.players.items[TV].playback_state = "playing"
        ma.music.played = [CATALOGUE[3], CATALOGUE[4]]
        for pid in (TV, KITCHEN, DEN):
            ma._refresh_media(pid)
        return ma

    def queue_item(self, uri: str) -> NS:
        t = next((t for t in CATALOGUE if t.uri == uri), None) or NS(
            name=uri.rsplit("/", 1)[-1], uri=uri, artist_str="", album=None, media_type=NS(value="track"),
            duration=180, image=None)
        return NS(queue_item_id=f"qi{next(self.ids)}", name=f"{t.artist_str} - {t.name}",
                  duration=t.duration, image=None, media_item=t)

    def titles(self, qid: str = TV) -> list[str]:
        return [i.media_item.name for i in self.player_queues.items[qid].items]

    def current_title(self, qid: str = TV) -> str | None:
        cur = self.player_queues.items[qid].current_item
        return cur.media_item.name if cur else None

    # --- state changes → events ----------------------------------------------------------
    def _refresh_media(self, pid: str) -> None:
        q = self.player_queues.items.get(pid)
        cur = q.current_item if q else None
        p = self.players.items.get(pid)
        if p is None:
            return
        if cur is None:
            p.current_media = None
            return
        t = cur.media_item
        p.current_media = NS(title=t.name, artist=t.artist_str, album=getattr(t.album, "name", ""),
                             image_url=None, duration=t.duration, uri=t.uri, palette=None,
                             elapsed_time=q.elapsed_time,
                              elapsed_time_last_updated=q.elapsed_time_last_updated)

    def step(self, pid: str, delta: int) -> None:
        q = self.player_queues.items[pid]
        i = q._index()
        if i is not None and 0 <= i + delta < len(q.items):
            q.current_id = q.items[i + delta].queue_item_id
            q.elapsed_time, q.elapsed_time_last_updated = 0.0, time.time()
        self.changed(queue=pid)

    def changed(self, *, player: str | None = None, queue: str | None = None, items: bool = False,
                kind: str | None = None) -> None:
        if queue is not None:
            self._refresh_media(queue)
            self._event("queue_items_updated" if items else "queue_updated", queue)
            self._event("player_updated", queue)
        if player is not None:
            self._refresh_media(player)
            self._event(kind or "player_updated", player)

    def _event(self, kind: str, object_id: str) -> None:
        event = NS(event=NS(value=kind), object_id=object_id, data=None)
        for cb in list(self._subs):
            cb(event)

    # --- the client API ------------------------------------------------------------------
    async def connect(self) -> None:
        self.connects += 1
        if self.refuse_connect is not None:
            raise self.refuse_connect

    async def start_listening(self, init_ready: asyncio.Event | None = None) -> None:
        self._dropped = asyncio.Event()
        if init_ready is not None:
            init_ready.set()
        await self._dropped.wait()
        raise ConnectionResetError("server went away")

    async def disconnect(self) -> None:
        if self._dropped is not None:
            self._dropped.set()

    def drop(self) -> None:
        """The socket closes, as when the MA server restarts."""
        if self._dropped is not None:
            self._dropped.set()

    def subscribe(self, cb, event_filter=None, id_filter=None):
        self._subs.append(cb)
        return lambda: self._subs.remove(cb) if cb in self._subs else None

    async def send_command(self, command: str, **args: Any) -> Any:
        self.calls.append(("send_command", command, args))
        if command in self.fail or "send_command" in self.fail:
            raise RuntimeError(f"{command} refused")
        if command == "config/player_queues/get_value":
            return self.config["crossfade_mode"]
        if command == "config/core/get_value":
            return self.config["server_crossfade_mode" if args.get("key") == "crossfade_mode"
                               else "crossfade_duration"]
        if command == "player_queues/crossfade":
            self.player_queues.items[args["queue_id"]].crossfade_enabled = args["crossfade_enabled"]
        elif command == "config/player_queues/save":
            self.config["crossfade_mode"] = args["values"]["crossfade_mode"]
        elif command == "config/core/save":
            self.config["crossfade_duration"] = args["values"]["crossfade_duration"]
        return None
