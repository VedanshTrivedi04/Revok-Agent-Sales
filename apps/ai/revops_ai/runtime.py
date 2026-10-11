"""Process entry helper: psycopg's async mode (used by the Postgres checkpointer) needs a selector
event loop, which is not Windows' default. Linux workers are unaffected."""

import asyncio
import selectors
import sys
from collections.abc import Coroutine
from typing import Any


def run_async(coro: Coroutine[Any, Any, Any]) -> Any:
    if sys.platform == "win32":
        return asyncio.run(
            coro, loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector())
        )
    return asyncio.run(coro)
