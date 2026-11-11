"""Keep a long-running background coroutine alive: log a crash and start it again."""

from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable

log = logging.getLogger(__name__)


async def keep_running(factory: Callable[[], Awaitable[None]], name: str,
                       delay: float = 5.0) -> None:
    """Run `factory()` until it returns normally; restart it after any exception."""
    while True:
        try:
            await factory()
            return
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("%s crashed; restarting in %ss", name, delay)
            await asyncio.sleep(delay)
