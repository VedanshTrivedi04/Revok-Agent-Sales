# superpower.md — How We Work (Engineering Superpowers) + Product Superpowers

> Two parts:
> **Part 1 — Product superpowers:** the few things that make this product special. Every feature must protect them.
> **Part 2 — Engineering superpowers:** the working method for humans and AI coding agents (plan first, test first, verify before "done"), inspired by the "Superpowers" style of disciplined agent workflows.

---

# Part 1 — Product superpowers (never trade these away)

| # | Superpower | What the user feels | What protects it in code |
|---|---|---|---|
| 1 | **Proof for every sentence** | "I can click and see where this came from." | Evidence IDs, validator, fallback template, UI hides chip-less sentences |
| 2 | **Nothing happens without me** | "It prepares; I decide." | Tiered autonomy, Tier 3 locked, executor re-checks, recipient allowlist |
| 3 | **See the change before it happens** | "I know exactly what will change in HubSpot." | Field-level before/after preview, stale-preview check |
| 4 | **Undo** | "If I'm wrong, I can roll back." | Pre-images, revert flow, conflict detection |
| 5 | **A record of why** | "Six months later I can see who decided what, and why." | Append-only, hash-chained decision log + why replay |
| 6 | **Short list, not noise** | "Three accounts today, not fifty." | Severity thresholds, compound rules, Today cap, dismiss cooldown |
| 7 | **Honest about gaps** | "It tells me what it doesn't know." | Unknown + contradiction detectors passed as evidence |
| 8 | **Risk *and* growth** | "It also tells me who is ready to buy more." | Expansion rules X01–X05 |
| 9 | **Private by design** | "Our customer emails don't go to some AI company." | Self-hosted model, snippet-only prompts, PII masking, RLS |
| 10 | **Works with my CRM in minutes** | "Connected HubSpot, saw my first insight in 15 minutes." | Onboarding flow, field mapping preview, fast first sync |

**Rule:** if a proposed feature weakens any of these, it needs an ADR in `thinking.md` and founder approval.

---

# Part 2 — Engineering superpowers (the working method)

## 2.1 The loop for every task

```
1. Understand  →  2. Plan  →  3. Test first  →  4. Build small  →  5. Verify  →  6. Review  →  7. Ship & note
```

### 1. Understand (before touching code)
- Read the task in `task.md` and its acceptance criteria.
- Read the relevant doc sections (`agent.md` §2 table).
- Write down in 3–5 lines: what changes, what must not change, how you'll know it works.
- If something is unclear or conflicts with a hard rule → ask. Don't guess on customer-visible behavior.

### 2. Plan
- For anything > ~1 hour: write a short plan in the PR description or `plans/<task-id>.md`:
  - files to touch, new tables/endpoints/components, tests to add, risks, rollback.
- Break into steps that each leave the app working (small commits).
- Prefer extending existing patterns (`skill.md`) over inventing new ones.

### 3. Test first (TDD where it pays)
- **Always test-first** for: rules, scoring, validators, idempotency, policy/tier logic, revert, hash chain, payload validation, permissions.
- Write the failing test → run it → see it fail for the right reason → implement → see it pass.
- UI: write the E2E step or component test for the behavior (not for styling).
- AI: add/extend a golden case before changing a prompt.

### 4. Build small
- One concern per PR (≤ ~400 lines changed when possible).
- Keep functions pure where possible (rules, scoring, mapping).
- No drive-by refactors. No new dependency without a reason.
- Keep hard rules (`agent.md` §3) in mind at every step.

### 5. Verify (evidence before "done")
**Never say "done" without proof.** Proof = output you actually saw:
- Tests: paste the command + result summary.
- API: a real request/response (curl/httpie) against local with seed data.
- UI: screenshot or short recording of the page with seed data (mobile width for Today/Inbox/Card).
- AI: eval metrics table vs previous version.
- Migrations: `upgrade` and `downgrade` ran locally.
If you could not verify something, say exactly what is unverified.

### 6. Review
- Self-review the diff first with this checklist:
  - [ ] Hard rules intact (no LLM writes, RLS, evidence, tiers, allowlist, idempotency, append-only log)
  - [ ] Names match glossary
  - [ ] Errors are user-readable; no secrets/PII in logs
  - [ ] Loading/empty/error states (UI)
  - [ ] Tests cover the failure path too
  - [ ] Docs updated
- Then request review. For high-risk changes (executor, policy, RLS, validator, prompts) a **second reviewer who did not write the code** is required. AI agents may do a first-pass review but not the final approval for these.

### 7. Ship & note
- Merge with Conventional Commit title + task id.
- Update `task.md` status.
- If you learned something non-obvious (a provider quirk, a model failure pattern), add it to the relevant doc (handover file "Known issues" section or `thinking.md`).

## 2.2 Systematic debugging

1. **Reproduce** with the smallest input (a golden case or a seed account).
2. **Read the evidence trail**: why replay → rule metrics → model output → executor logs.
3. **Form one hypothesis**, test it (log, breakpoint, unit test). Don't change 3 things at once.
4. **Fix the root cause**, not the symptom (e.g., fix entity resolution, not hide the wrong finding).
5. **Add a regression test** that fails without the fix.
6. Write a 3-line note in the PR: cause, fix, test.

## 2.3 Working with AI coding agents

- Give the agent: task id, acceptance criteria, files to read, hard rules. Ask for a **plan first**, approve it, then let it implement.
- Make it run tests and show output; don't accept "should work".
- Use parallel agents only for independent work (e.g., FE page + BE endpoint after the API contract is fixed).
- Agents must not: edit migrations already applied in prod, change prompts without evals, touch executor/policy/RLS without human review, commit secrets.
- After an agent finishes: run the verification yourself for high-risk areas.

## 2.4 Brainstorming before big features

For a new feature, spend 30 minutes on:
1. What user moment does this improve? (Which persona, which page?)
2. Which product superpower does it strengthen? Which could it weaken?
3. Smallest version that proves value (one rule, one card type, one page).
4. What evidence will it show? What can go wrong for the customer?
5. How will we measure it (approval rate, "not useful" rate, time saved)?
Write the answers in the PR/plan. If the answers are weak, don't build it yet.

## 2.5 Definition of "good enough" per area

| Area | Good enough to ship |
|---|---|
| Rule | Unit tests + golden case + preview count sensible on demo org |
| Prompt | All eval gates pass + 10 human-reviewed outputs |
| Connector | Backfill + incremental + 429 + token refresh tested with fixtures; real sandbox run once |
| Executor handler | Idempotency test (double call), revert test, stale-preview test |
| Page | States + permissions + mobile (if core) + E2E step |
| Migration | Up/down + RLS test |

## 2.6 Daily habits

- Start: check CI, Sentry, failed jobs, eval dashboard.
- Keep PRs small and merged daily.
- End: update `task.md`, push WIP branch, note blockers.
- Weekly: review "not useful" feedback + rejection reasons with the founder → turn into tasks.
