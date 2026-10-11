"""Regenerate the synthetic golden dataset (deterministic).

    uv run python scripts/gen_golden.py

Writes tests/golden/cases/* (30 cases) and tests/golden/messages.jsonl (labeled T1 messages).
"""

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from revops_ai.fixtures import CASES, GOLDEN, write_case  # noqa: E402
from revops_ai.synth.messages import generate_messages  # noqa: E402
from revops_ai.synth.world import build_all  # noqa: E402


def main() -> None:
    if CASES.exists():
        shutil.rmtree(CASES)
    for i, case in enumerate(build_all(), 1):
        fx, exp = case.fixture(), case.expected()
        readme = (
            f"# {fx.case_id}\n\nSynthetic account **{fx.account.name}**.\n\n"
            f"- expected rule hits: {', '.join(exp.rule_hits) or 'none'}\n"
            f"- expected finding: {exp.finding_type} / {exp.severity}\n"
            f"- contradictions: {exp.contradictions_expected or 'none'}\n"
            f"- unknowns: {exp.unknowns_expected or 'none'}\n"
            f"- injection case: {exp.injection}\n"
        )
        write_case(i, fx, exp, readme)
        print(f"{i:02d} {fx.case_id:28s} hits={exp.rule_hits} -> {exp.finding_type}/{exp.severity}")
    msgs = generate_messages(per_kind=10, seed=7)
    with (GOLDEN / "messages.jsonl").open("w", encoding="utf-8") as f:
        for m in msgs:
            f.write(json.dumps({
                "id": m.id, "direction": m.direction, "from_role": m.from_role, "category": m.category,
                "text": m.text, "signals": [s.model_dump() for s in m.signals],
            }, ensure_ascii=False) + "\n")  # fmt: skip
    from revops_ai.synth.holdout import holdout_messages

    hold = holdout_messages()
    with (GOLDEN / "messages_holdout.jsonl").open("w", encoding="utf-8") as f:
        for m in hold:
            f.write(json.dumps({"id": m.id, "direction": m.direction, "from_role": m.from_role, "category": m.category, "text": m.text, "signals": [s.model_dump() for s in m.signals]}, ensure_ascii=False) + chr(10))  # fmt: skip
    print(f"messages: {len(msgs)} dev + {len(hold)} holdout")


if __name__ == "__main__":
    main()
