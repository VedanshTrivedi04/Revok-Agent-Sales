from collections.abc import Iterator

import pytest

from tests.fake_llm_server import FakeLLMServer


@pytest.fixture
def llm_server() -> Iterator[FakeLLMServer]:
    s = FakeLLMServer().start()
    yield s
    s.stop()


def pytest_asyncio_loop_factories(config, item):  # type: ignore[no-untyped-def]
    """psycopg async (Postgres checkpointer) cannot use Windows' default ProactorEventLoop."""
    import asyncio
    import selectors
    import sys

    if sys.platform == "win32":
        return {"selector": lambda: asyncio.SelectorEventLoop(selectors.SelectSelector())}
    return {"default": asyncio.new_event_loop}
