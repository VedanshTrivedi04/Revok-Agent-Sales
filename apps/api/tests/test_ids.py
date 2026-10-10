import time
from uuid import UUID

from app.utils.ids import new_id


def test_uuid7_version_variant_and_ordering() -> None:
    a = new_id()
    time.sleep(0.002)
    b = new_id()
    assert isinstance(a, UUID) and a.version == 7 and a.variant == "specified in RFC 4122"
    assert a < b
    assert len({new_id() for _ in range(1000)}) == 1000
