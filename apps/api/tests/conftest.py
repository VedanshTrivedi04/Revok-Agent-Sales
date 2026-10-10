import pytest_asyncio

from app.db import session as db_session


@pytest_asyncio.fixture(autouse=True)
async def _fresh_engine():  # type: ignore[no-untyped-def]
    """Each test gets its own engine/loop-bound pool."""
    db_session.get_engine.cache_clear()
    db_session._sessionmaker.cache_clear()
    yield
    await db_session.get_engine().dispose()
    db_session.get_engine.cache_clear()
    db_session._sessionmaker.cache_clear()
