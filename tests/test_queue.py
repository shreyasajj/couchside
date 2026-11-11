from types import SimpleNamespace as NS

from couchside.core.queue import QueueRow, load_queue, queue_action


def qitem(iid, name="Artist - Song", media=None, duration=200):
    return NS(queue_item_id=iid, name=name, media_item=media, duration=duration, image=None)


class FakeQueues:
    def __init__(self, items=(), fail=False):
        self.items, self.fail, self.calls = list(items), fail, []

    async def get_queue_items(self, queue_id, limit=500, offset=0):
        self.calls.append(("get", queue_id))
        return self.items

    def _rec(name):
        async def f(self, queue_id, item_id):
            self.calls.append((name, queue_id, item_id))
            if self.fail:
                raise RuntimeError("nope")
        return f

    play_index = _rec("play_index")
    move_next = _rec("move_next")
    move_up = _rec("move_up")
    move_down = _rec("move_down")
    delete_item = _rec("delete_item")


class FakeMusic:
    def get_media_item_image(self, item, *_):
        return None


def client(queues):
    return NS(player_queues=queues, music=FakeMusic(), server_info=NS(base_url="http://ma:8095"))


async def test_rows_start_at_current():
    q = FakeQueues([qitem("a"), qitem("b"), qitem("c")])
    rows = await load_queue(client(q), "q1", "b")
    assert [r.item_id for r in rows] == ["b", "c"]
    assert rows[0].current and not rows[1].current


async def test_unknown_current_keeps_all_rows():
    rows = await load_queue(client(FakeQueues([qitem("a"), qitem("b")])), "q1", None)
    assert [r.item_id for r in rows] == ["a", "b"] and not any(r.current for r in rows)


async def test_titles_prefer_media_item():
    media = NS(name="Song", artist_str="Artist", image=None)
    rows = await load_queue(client(FakeQueues([qitem("a", media=media)])), "q1", "a")
    assert rows[0] == QueueRow("a", "Song", "Artist", None, 200, True)


async def test_title_falls_back_to_item_name():
    rows = await load_queue(client(FakeQueues([qitem("a", name="Radio stream")])), "q1", "a")
    assert (rows[0].title, rows[0].subtitle) == ("Radio stream", "")


async def test_no_queue_is_empty():
    q = FakeQueues([qitem("a")])
    assert await load_queue(client(q), None, None) == []
    assert q.calls == []


async def test_load_failure_is_empty():
    class Broken(FakeQueues):
        async def get_queue_items(self, *a, **k):
            raise RuntimeError("down")
    assert await load_queue(client(Broken()), "q1", None) == []


async def test_actions_call_queue_api():
    q = FakeQueues()
    c = client(q)
    for action in ("play", "next", "up", "down", "remove"):
        assert await queue_action(c, "q1", "a", action)
    assert [x[0] for x in q.calls] == ["play_index", "move_next", "move_up", "move_down", "delete_item"]
    assert all(x[1:] == ("q1", "a") for x in q.calls)


async def test_unknown_action_is_false():
    assert not await queue_action(client(FakeQueues()), "q1", "a", "shuffle")


async def test_action_failure_is_false():
    assert not await queue_action(client(FakeQueues(fail=True)), "q1", "a", "remove")
    assert not await queue_action(client(FakeQueues()), None, "a", "remove")
