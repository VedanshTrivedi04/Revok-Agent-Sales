"""Send one real graph run to a Langfuse server and verify the trace arrived with no raw emails/phones.

Start the server:  docker compose -f infra/docker-compose.langfuse.yml up -d
Run:  LANGFUSE_HOST=http://localhost:3300 LANGFUSE_PUBLIC_KEY=pk-lf-local-dev LANGFUSE_SECRET_KEY=sk-lf-local-dev \
      uv run python scripts/langfuse_check.py [--live]
"""

import argparse
import asyncio
import base64
import json
import re
import sys
import time
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from revops_ai.adapters.inprocess import FakeBackend, FixtureProvider  # noqa: E402
from revops_ai.config import get_settings  # noqa: E402
from revops_ai.evals.suites_t1 import make_llm  # noqa: E402
from revops_ai.fixtures import load_all  # noqa: E402
from revops_ai.graph.graph import Deps  # noqa: E402
from revops_ai.graph.runner import AccountRunner, checkpointer  # noqa: E402
from revops_ai.observability.tracing import sink_from_settings  # noqa: E402
from revops_ai.observability.versions import select_prompts  # noqa: E402

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def api(s, path: str) -> dict:
    tok = base64.b64encode(f"{s.langfuse_public_key}:{s.langfuse_secret_key}".encode()).decode()
    req = urllib.request.Request(
        s.langfuse_host.rstrip("/") + path, headers={"Authorization": f"Basic {tok}"}
    )
    with urllib.request.urlopen(req, timeout=20) as r:  # noqa: S310 - local dev server
        return json.load(r)


async def main(live: bool) -> int:
    s = get_settings()
    sink = sink_from_settings(s)
    if sink is None:
        print("LANGFUSE_HOST / LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY not set")
        return 2
    fixtures = [fx for fx, _ in load_all()]
    deps = Deps(
        llm=make_llm(live), provider=FixtureProvider(fixtures),
        backend=FakeBackend(fixtures={f.account.id: f for f in fixtures}),
        prompts=select_prompts("org-demo"), sink=sink,
    )  # fmt: skip
    rid = f"lfcheck-{uuid.uuid4().hex[:6]}"
    acme = next(f for f in fixtures if f.case_id == "acme_high_risk")
    async with checkpointer() as saver:
        st = await AccountRunner(deps, saver).run("org-demo", acme.account.id, rid)
    print("run status:", st["status"])
    # positive control: a trace that contains an email/phone on purpose must come back masked
    from revops_ai.observability.tracing import RunTrace

    ctl = RunTrace(
        run_id=f"{rid}-ctl",
        org_id="org-demo",
        account_id="x",
        meta={"note": "contact jane.doe@customer.example.com or +1 415 555 0100"},
    )
    with ctl.span("control"):
        pass
    sink.emit(ctl)
    sink.client.flush()
    for _ in range(12):  # ingestion is async (worker + clickhouse)
        time.sleep(5)
        traces = api(s, "/api/public/traces?limit=50").get("data", [])
        mine = [t for t in traces if t.get("name") == f"run:{rid}"]
        if mine:
            break
    if not mine:
        print("FAIL: trace not found in Langfuse")
        return 1
    t = mine[0]
    detail = api(s, f"/api/public/traces/{t['id']}")
    blob = json.dumps(detail)
    leaks = sorted(set(EMAIL.findall(blob)))
    obs = detail.get("observations", [])
    print(
        f"trace {t['id']} name={t['name']} observations={len(obs)} names={sorted({o['name'] for o in obs})[:12]}"
    )
    print("emails found in stored trace:", leaks or "none")
    for _ in range(6):
        cl = [
            x
            for x in api(s, "/api/public/traces?limit=50").get("data", [])
            if x.get("name") == f"run:{rid}-ctl"
        ]
        if cl:
            break
        time.sleep(5)
    cblob = json.dumps(api(s, f"/api/public/traces/{cl[0]['id']}")) if cl else ""
    ctl_ok = bool(cl) and "jane.doe@" not in cblob and "415 555" not in cblob and "[email]" in cblob
    print("masking control (email+phone redacted):", "PASS" if ctl_ok else "FAIL")
    return 0 if (not leaks and ctl_ok and st["status"] != "failed") else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    sys.exit(asyncio.run(main(ap.parse_args().live)))
