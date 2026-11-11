import asyncio

from couchside.core.tasks import keep_running


async def test_keep_running_restarts_after_crash():
    runs = []

    async def flaky():
        runs.append(1)
        if len(runs) < 3:
            raise OSError("boom")
        await asyncio.Event().wait()

    task = asyncio.ensure_future(keep_running(flaky, "flaky", delay=0))
    for _ in range(100):
        if len(runs) >= 3:
            break
        await asyncio.sleep(0.005)
    assert len(runs) == 3 and not task.done()
    task.cancel()


async def test_keep_running_stops_on_clean_return():
    runs = []

    async def once():
        runs.append(1)

    await asyncio.wait_for(keep_running(once, "once", delay=0), 1)
    assert runs == [1]
