import { describe, expect, it } from "vitest";
import {
  acceptsRun,
  applyStepEvent,
  flowAtCursor,
  flowFromRun,
  flowPhase,
  framesOf,
  isRunStepEvent,
  markRunDone,
  runTotals,
  stepChips,
  stepSummary,
  visibleSteps,
  type RunStepEvent,
} from "./agent-flow";

const evt = (over: Partial<RunStepEvent>): RunStepEvent => ({
  run_id: "r1",
  account_id: "a1",
  seq: 1,
  step: "context",
  status: "started",
  ...over,
});

describe("applyStepEvent", () => {
  it("creates the run and a step from the first event", () => {
    const flow = applyStepEvent(undefined, evt({}));
    expect(flow.runId).toBe("r1");
    expect(flow.steps).toHaveLength(1);
    expect(flow.steps[0].status).toBe("started");
  });

  it("keeps the data of a step when a later event carries none", () => {
    let flow = applyStepEvent(undefined, evt({ seq: 2, status: "ok", duration_ms: 12, data: { open_deals: 3 } }));
    flow = applyStepEvent(flow, evt({ seq: 3, status: "ok", data: {} }));
    expect(flow.steps[0].data).toEqual({ open_deals: 3 });
  });

  it("drops stale and duplicate events", () => {
    const ok = applyStepEvent(undefined, evt({ seq: 2, status: "ok" }));
    expect(applyStepEvent(ok, evt({ seq: 1, status: "started" }))).toBe(ok);
    expect(applyStepEvent(ok, evt({ seq: 2, status: "ok" }))).toBe(ok);
  });

  it("starts a fresh flow for a different run", () => {
    const first = applyStepEvent(undefined, evt({ seq: 2, status: "ok" }));
    const second = applyStepEvent(first, evt({ run_id: "r2" }));
    expect(second.runId).toBe("r2");
    expect(second.steps).toHaveLength(1);
  });
});

describe("run ownership", () => {
  it("only switches run once the watched run is done", () => {
    const running = applyStepEvent(undefined, evt({}));
    expect(acceptsRun(running, "r2")).toBe(false);
    expect(acceptsRun(running, "r1")).toBe(true);
    expect(acceptsRun(markRunDone(running, "r1"), "r2")).toBe(true);
    expect(acceptsRun(undefined, "r2")).toBe(true);
  });
});

describe("flowPhase / visibleSteps", () => {
  it("is idle without a run and always lists the known steps as pending", () => {
    expect(flowPhase(undefined)).toBe("idle");
    expect(visibleSteps(undefined).map((s) => [s.name, s.status])).toEqual(
      ["trigger", "context", "rules", "evidence", "scoring", "explain", "findings", "actions"].map((n) => [n, "pending"]),
    );
  });

  it("reports running, failed and completed from the real steps", () => {
    const running = applyStepEvent(undefined, evt({}));
    expect(flowPhase(running)).toBe("running");
    expect(flowPhase(markRunDone(running, "r1"))).toBe("completed");
    expect(flowPhase(applyStepEvent(running, evt({ seq: 2, status: "failed", detail: "boom" })))).toBe("failed");
  });

  it("appends steps the agent reported beyond the known ones", () => {
    const flow = applyStepEvent(undefined, evt({ step: "ai", status: "ok", seq: 2 }));
    expect(visibleSteps(flow).map((s) => s.name)).toEqual([
      "trigger", "context", "rules", "evidence", "scoring", "explain", "findings", "actions", "ai",
    ]);
  });

  it("never includes phantom pending steps when a run is finished", () => {
    const realRun = flowFromRun({
      id: "r1",
      account_id: "a1",
      status: "completed",
      error: null,
      steps: [
        { name: "load_context", status: "ok", duration_ms: 120, data: {} },
        { name: "rules", status: "ok", duration_ms: 160, data: {} },
        { name: "explain", status: "ok", duration_ms: 200, data: {} },
        { name: "plan_actions", status: "ok", duration_ms: 240, data: {} },
        { name: "policy", status: "ok", duration_ms: 280, data: {} },
      ],
    });
    const visible = visibleSteps(realRun);
    expect(visible.map((s) => s.name)).toEqual([
      "load_context",
      "rules",
      "explain",
      "plan_actions",
      "policy",
    ]);
    expect(visible.every((s) => s.status === "ok")).toBe(true);
    expect(visible.some((s) => s.status === "pending")).toBe(false);
  });

  it("tracks the AI pipeline when AI markers are present during live run", () => {
    const liveAiFlow = applyStepEvent(undefined, evt({ step: "load_context", status: "ok", seq: 1 }));
    const visible = visibleSteps(liveAiFlow);
    expect(visible.map((s) => s.name)).toEqual([
      "load_context",
      "rules",
      "explain",
      "plan_actions",
      "policy",
    ]);
    expect(visible[0].status).toBe("ok");
    expect(visible[1].status).toBe("pending");
  });
});

describe("flowFromRun", () => {
  it("maps persisted steps and marks finished runs done", () => {
    const flow = flowFromRun({
      id: "r1",
      account_id: "a1",
      status: "completed",
      error: null,
      steps: [{ name: "context", status: "ok", duration_ms: 5, data: { open_deals: 1 } }],
    });
    expect(flow.done).toBe(true);
    expect(flow.steps[0].data).toEqual({ open_deals: 1 });
  });

  it("shows a failed run without recorded steps as failed", () => {
    const flow = flowFromRun({ id: "r1", account_id: "a1", status: "failed", error: "db down", steps: [] });
    expect(flowPhase(flow)).toBe("failed");
  });

  it("shows a run that has reported nothing yet as queued", () => {
    const flow = flowFromRun({ id: "r1", account_id: "a1", status: "queued", error: null, steps: [] });
    expect(flowPhase(flow)).toBe("queued");
  });
});

describe("stepSummary", () => {
  it("only uses real numbers", () => {
    const flow = applyStepEvent(
      undefined,
      evt({ status: "ok", seq: 2, data: { days_since_meeting: 22, unanswered_emails: 2, open_deals: 1 } }),
    );
    expect(stepSummary(flow.steps[0])).toBe("22 days since meeting · 2 unanswered emails · 1 open deal");
  });

  it("says so when there is no meeting on record", () => {
    const flow = applyStepEvent(undefined, evt({ status: "ok", seq: 2, data: { days_since_meeting: null } }));
    expect(stepSummary(flow.steps[0])).toBe("no meeting on record");
  });
});

describe("isRunStepEvent", () => {
  it("rejects malformed payloads", () => {
    expect(isRunStepEvent(null)).toBe(false);
    expect(isRunStepEvent({ run_id: "r", account_id: "a", seq: 1, step: "x", status: "weird" })).toBe(false);
    expect(isRunStepEvent(evt({}))).toBe(true);
  });
});

describe("pacing the reveal of a real run", () => {
  const full = () => {
    let flow = applyStepEvent(undefined, evt({ step: "context", seq: 1, status: "started" }));
    flow = applyStepEvent(flow, evt({ step: "context", seq: 2, status: "ok", duration_ms: 12, data: { open_deals: 2 } }));
    flow = applyStepEvent(flow, evt({ step: "rules", seq: 3, status: "started" }));
    return flow;
  };

  it("has one beat for a step starting and one for its result", () => {
    expect(framesOf(full()).map((f) => `${f.step}:${f.kind}`)).toEqual([
      "context:started",
      "context:resolved",
      "rules:started",
    ]);
  });

  it("shows no data before the beat that reveals it", () => {
    const flow = full();
    const early = flowAtCursor(flow, 1)!;
    expect(early.steps).toHaveLength(1);
    expect(early.steps[0].status).toBe("started");
    expect(early.steps[0].data).toEqual({});
    expect(early.done).toBe(false);
    const later = flowAtCursor(flow, 2)!;
    expect(later.steps[0].status).toBe("ok");
    expect(later.steps[0].data).toEqual({ open_deals: 2 });
  });

  it("is the real flow once every beat has been shown", () => {
    const flow = markRunDone(full(), "r1")!;
    expect(flowAtCursor(flow, 99)).toBe(flow);
    expect(flowAtCursor(flow, 1)!.done).toBe(false);
  });
});

describe("runTotals / stepChips", () => {
  it("sums only recorded durations and counts real hits and findings", () => {
    let flow = applyStepEvent(undefined, evt({ step: "context", seq: 2, status: "ok", duration_ms: 10 }));
    flow = applyStepEvent(flow, evt({ step: "rules", seq: 4, status: "ok", duration_ms: 5, data: { hits: [{ rule_key: "R04_renewal_near_no_plan" }] } }));
    flow = applyStepEvent(flow, evt({ step: "findings", seq: 6, status: "ok", duration_ms: 20, data: { findings: [{ type: "risk", outcome: "created" }, { type: "expansion", outcome: "no_signal" }] } }));
    expect(runTotals(flow)).toEqual({ totalMs: 35, rulesFired: 1, findingsOpened: 1 });
    expect(stepChips(flow.steps[1])).toEqual(["R04 renewal near no plan"]);
    expect(stepChips(flow.steps[2])).toEqual(["risk finding created"]);
  });

  it("reports unknowns as null instead of zero", () => {
    expect(runTotals(undefined)).toEqual({ totalMs: null, rulesFired: null, findingsOpened: null });
  });
});

describe("summaries of the detailed steps", () => {
  const ok = (step: string, data: Record<string, unknown>) =>
    applyStepEvent(undefined, evt({ step, status: "ok", seq: 2, data })).steps[0];

  it("describes evidence, scoring, explanation and actions from their data", () => {
    expect(stepSummary(ok("evidence", { items: [{ type: "risk", outcome: "evidence", count: 4, contradictions: ["x"] }] }))).toBe("4 evidence items collected");
    expect(stepSummary(ok("scoring", { items: [{ type: "risk", priority_score: 71.5 }] }))).toBe("risk priority 71.5");
    expect(stepSummary(ok("explain", { items: [{ type: "risk", model: "template" }] }))).toBe("1 explanation written");
    expect(stepSummary(ok("actions", { cards: [] }))).toBe("No action proposed");
    expect(stepSummary(ok("actions", { cards: [{ id: "c1" }, { id: "c2" }] }))).toBe("2 action cards proposed");
    expect(stepSummary(ok("trigger", { trigger: "manual", account_name: "Acme Corp" }))).toBe("manual run for Acme Corp");
  });

  it("says a quiet account needs no evidence", () => {
    expect(stepSummary(ok("evidence", { items: [{ type: "risk", outcome: "no_signal" }] }))).toBe("No signal, so no evidence needed");
  });
});
