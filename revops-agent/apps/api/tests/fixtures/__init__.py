"""Recorded provider fixtures (scrubbed/synthetic JSON). Load with `load_fixture("hubspot/companies")`."""

import json
from pathlib import Path
from typing import Any

FIXTURE_DIR = Path(__file__).parent


def load_fixture(name: str) -> Any:
    return json.loads((FIXTURE_DIR / f"{name}.json").read_text(encoding="utf-8"))
