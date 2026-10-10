from uuid import uuid4

from sqlalchemy import text

from app.db.base import NAMING_CONVENTION, Base
from app.db.session import org_session


async def test_org_id_is_set_per_transaction_and_does_not_leak() -> None:
    org_a, org_b = uuid4(), uuid4()
    async with org_session(org_a) as s:
        assert (await s.execute(text("SELECT current_setting('app.org_id')"))).scalar() == str(
            org_a
        )
    async with org_session(org_b) as s:
        assert (await s.execute(text("SELECT current_setting('app.org_id')"))).scalar() == str(
            org_b
        )
    # pool connection reused outside a tenant transaction must not carry the setting
    async with org_session(org_a) as s:
        pass
    from app.db.session import get_engine

    async with get_engine().connect() as c:
        assert (await c.execute(text("SELECT current_setting('app.org_id', true)"))).scalar() in (
            None,
            "",
        )


def test_naming_convention_registered() -> None:
    assert Base.metadata.naming_convention == NAMING_CONVENTION
