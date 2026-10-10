"""Write app/mocks/*.json from app.mocks.data (committed; a test fails if they drift).

Run: PYTHONPATH=. uv run python scripts/gen_mocks.py
"""

import json
from pathlib import Path

from app.mocks.data import build_files

TARGET = Path(__file__).resolve().parents[1] / "app" / "mocks"


def render() -> dict[str, str]:
    return {
        name: json.dumps(payload, indent=1, sort_keys=True, ensure_ascii=False) + "\n"
        for name, payload in build_files().items()
    }


if __name__ == "__main__":
    for name, text in render().items():
        (TARGET / name).write_text(text, encoding="utf-8")
    print(f"wrote {len(render())} files to {TARGET}")
