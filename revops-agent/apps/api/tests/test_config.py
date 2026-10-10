import re
from pathlib import Path

from app.config import Settings


def test_env_example_documents_every_setting() -> None:
    text = (Path(__file__).parents[3] / ".env.example").read_text()
    documented = {m.group(1).lower() for m in re.finditer(r"^([A-Z_]+)=", text, re.M)}
    missing = set(Settings.model_fields) - documented
    assert not missing, f"undocumented in .env.example: {sorted(missing)}"
