"""Show T1 false positives / negatives on the real model for a sample of messages (live endpoint)."""

import asyncio
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from revops_ai.evals.metrics import quotes_match  # noqa: E402
from revops_ai.llm.client import OpenAICompatClient  # noqa: E402
from revops_ai.tasks.extract import extract_signals  # noqa: E402


async def main(limit: int) -> None:
    msgs = [
        json.loads(line)
        for line in (ROOT / "tests/golden/messages.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    sample = [m for m in msgs if m["category"] in ("neutral", "hard_negative")] + [m for m in msgs if m["category"] == "signal"][:: max(1, len(msgs) // limit)]  # fmt: skip
    llm = OpenAICompatClient()
    sem = asyncio.Semaphore(2)
    fp_kinds: Counter[str] = Counter()
    rows = []

    async def one(m: dict) -> None:  # type: ignore[type-arg]
        async with sem:
            r = await extract_signals(llm, text=m["text"], org_name="Demo SaaS", account_name="Acme", date=datetime(2026, 10, 9, tzinfo=UTC))  # fmt: skip
            gold = m["signals"]
            for s in r.signals:
                hit = any(g["kind"] == s.kind and quotes_match(s.quote, g["quote"]) for g in gold)
                if not hit:
                    same_quote = [g["kind"] for g in gold if quotes_match(s.quote, g["quote"])]
                    fp_kinds[s.kind] += 1
                    rows.append((m["category"], s.kind, s.polarity, s.confidence, s.quote[:90], "gold kinds for same quote: " + ",".join(same_quote) if same_quote else "NO GOLD (quote not a labeled signal)"))  # fmt: skip

    await asyncio.gather(*(one(m) for m in sample))
    print(f"messages={len(sample)} false_positives={len(rows)}")
    print("by kind:", dict(fp_kinds))
    for r in sorted(rows)[:40]:
        print(" | ".join(map(str, r)))


asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else 60))
