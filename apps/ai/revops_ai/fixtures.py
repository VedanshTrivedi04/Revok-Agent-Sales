"""Golden fixture I/O: tests/golden/cases/<nn>_<name>/{account.json, events.jsonl, usage.json, expected.json}."""

import json
from pathlib import Path

from revops_ai.domain import Account, Contact, Deal, Event, Expected, Fixture, Org, UsagePoint

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "tests" / "golden"
CASES = GOLDEN / "cases"


def write_case(idx: int, fx: Fixture, exp: Expected, readme: str, base: Path = CASES) -> Path:
    d = base / f"{idx:02d}_{fx.case_id}"
    d.mkdir(parents=True, exist_ok=True)
    meta = {
        "case_id": fx.case_id, "now": fx.now.isoformat(), "org": fx.org.model_dump(mode="json"),
        "account": fx.account.model_dump(mode="json"),
        "contacts": [c.model_dump(mode="json") for c in fx.contacts],
        "deals": [x.model_dump(mode="json") for x in fx.deals],
    }  # fmt: skip
    (d / "account.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    (d / "usage.json").write_text(
        json.dumps([u.model_dump(mode="json") for u in fx.usage], indent=1), encoding="utf-8"
    )
    (d / "events.jsonl").write_text(
        "\n".join(json.dumps(e.model_dump(mode="json"), ensure_ascii=False) for e in fx.events)
        + "\n",
        encoding="utf-8",
    )
    (d / "expected.json").write_text(exp.model_dump_json(indent=1), encoding="utf-8")
    (d / "README.md").write_text(readme, encoding="utf-8")
    return d


def load_case(d: Path) -> tuple[Fixture, Expected]:
    meta = json.loads((d / "account.json").read_text(encoding="utf-8"))
    events = [
        Event.model_validate_json(line)
        for line in (d / "events.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()
    ]  # fmt: skip
    usage = [UsagePoint.model_validate(u) for u in json.loads((d / "usage.json").read_text(encoding="utf-8"))]  # fmt: skip
    fx = Fixture(
        case_id=meta["case_id"], now=meta["now"], org=Org.model_validate(meta["org"]),
        account=Account.model_validate(meta["account"]),
        contacts=[Contact.model_validate(c) for c in meta["contacts"]],
        deals=[Deal.model_validate(x) for x in meta["deals"]], usage=usage, events=events,
    )  # fmt: skip
    exp = Expected.model_validate_json((d / "expected.json").read_text(encoding="utf-8"))
    return fx, exp


def load_all(base: Path = CASES) -> list[tuple[Fixture, Expected]]:
    return [load_case(d) for d in sorted(base.iterdir()) if d.is_dir()]
