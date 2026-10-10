# research.md — Research Summary

> Everything we learned about the problem, market, competitors, technology and compliance, with sources.
> Compiled from the deep research report (Oct 2026) plus follow-up checks on the model, Gmail scopes and vLLM.
> ⚠️ Items marked **(vendor claim)** or **(secondary)** are not independently verified. Items marked **(positioning)** come from general vendor positioning. Always name the source when quoting a number.

---

## 1. The problem in numbers

### 1.1 Retention benchmarks
| Metric | Value | Source |
|---|---|---|
| Median NRR (CY-2025, 342 companies) | 102% (usage-based 108% vs seat-based 98%) | Aleph + Benchmarkit 2026 |
| Median GRR (same dataset) | 84% | Aleph + Benchmarkit 2026 |
| Median GRR, 1,000+ private B2B SaaS | 91% (95% for ACV > $250k); NRR 101% | SaaS Capital 2025 |
| Median NRR (~2,700 companies, many small) | 82% (upper quartile 97%) | ChartMogul 2025 |
| GRR trend | 90% → 88% over three years; expansion = 40–50% of new ARR | Benchmarkit 2025 (n=936) |
| Median annual revenue churn (startups) | 12.50% (customer churn 16.25%) | Lighter Capital 2025 |
| Share of SaaS churn from failed payments | about one-third | Recurly 2026 via Churn Buster (secondary) |

**Takeaway:** a typical SaaS company loses ~9–16% of recurring revenue a year and barely recovers it via expansion. Benchmarks disagree (82% vs 102% NRR) because samples differ.

**Profit impact:** "increasing customer retention rates by 5% increases profits by 25% to 95%" — Reichheld (Bain), summarized in HBR, Amy Gallo, 2014 (old but standard anchor).

**Simple impact model:** $20M ARR company at 88% GRR loses $2.4M/yr. Saving 10% of churning ARR = $240k/yr retained, before expansion.

### 1.2 Time and tools
- Salesforce State of Sales, 7th ed. (2026; 4,050 sales pros, 22 countries): "the average seller spends 40% of their time selling"; Gen Z reps ~35%, losing ~2 hours/week to manual data entry. Earlier editions: 28% and ~30%.
- Salesforce 2023: ~70% of reps overwhelmed by number of tools; 9 in 10 sales orgs planned stack consolidation.
- Gartner (via Cirrus Insight, secondary): AI saves ~4.8 hours per seller per week.

### 1.3 CRM data quality
- Gartner: poor data quality costs organizations "at least $12.9 million a year on average" (2020 research).
- Validity, State of CRM Data Management 2025 (n=602): 37% lose revenue directly due to data quality; average 16 lost deals/quarter; 1 in 4 see ≥20% annual revenue drop.
- Validity (1,250+ companies): 44% estimate >10% of annual revenue lost to bad CRM data.
- B2B contact data decays ~2.1%/month (~22.5%/yr) (Marketing Sherpa, secondary); other estimates 30–34%/yr.

### 1.4 Stakeholder / champion risk
- ~20% of CRM contacts change jobs every year; departing champion called "the second biggest reason for churn" — UserGems **(vendor claim)**.
- UserGems (500 opps): single-threaded deals 5% win vs 30% with five contacts **(vendor claim)**. Gong (1.8M opps): won deals have ~2× buyer contacts (via Salesmotion, secondary).

### 1.5 Agentic AI reality check
- Gartner (June 25, 2025): over 40% of agentic AI projects will be canceled by end of 2027 due to escalating costs, unclear business value or **inadequate risk controls**; only ~130 of thousands of "agentic" vendors are real ("agent washing").
- Gartner: 15% of day-to-day work decisions made autonomously by 2028 (from 0% in 2024); 33% of enterprise apps include agentic AI by 2028 (from <1% in 2024).
- **Use in pitch:** approvals + audit trail answer "inadequate risk controls" directly.

## 2. Why current approaches fail

**Data silos:** CRM, CS platform, product analytics, support, billing — each with its own ID. Unstructured data (emails, meetings) never reaches CRM fields. Entity mismatch ("Acme Corp" in HubSpot, "acme.io" in email, "ACME-EU" in billing, workspace 4411 in analytics). Manual entry decays 20–30%/yr.

**Health scores/alerts:** stale formulas (Gainsight Staircase used fixed modifiers until making them configurable in June 2026); no explanation ("Health = 42"); alert fatigue; no action loop (manager "sees this Sunday night, manually updates CRM, Slacks the rep, hopes they follow up" — Oliv AI blog); no accountability trail.

**Today's manual loop:** signals land in many tools → someone notices (or not) → health score turns red → raised in weekly meeting → rep manually creates task, writes email, updates CRM, pings Slack.

## 3. Market size (directional — reports disagree)
| Segment | Estimate | Source |
|---|---|---|
| Customer success platforms | $1.81B (2024) → $5.89B (2030), 21.8% CAGR | Grand View Research |
| Customer success platforms (alt.) | $3.40B (2026) → $14.0B (2033), 12% CAGR | Coherent Market Insights |
| Customer intelligence platforms | $3.09B (2024) → $13.8B (2030), 29.2% CAGR; India highest CAGR | Grand View Research |
| Revenue intelligence | $2.1B (2024) → $6.7B (2030) / $4.2B (2025) → $10.3B (2034) | Strategic Market Research / Dataintelo |

Spend signals: Agentforce > $1.5B ARR by Aug 2026 (Contrary, secondary); Clari + Salesloft ~$450M ARR, 5,000+ customers; Rox reported $1.2B valuation (TechCrunch, Mar 2026, unnamed sources; Rox did not confirm).

## 4. Competitors

### 4.1 Revenue intelligence
- **Gong** — Mission Andromeda (Feb 25, 2026): Gong Assistant with sourced answers, Account Console/Boards with risk signals + next steps, MCP support. Mission Big Dipper (Jun 24, 2026): Revenue Harness (governed agent execution), Custom Agents. Strength: conversation evidence; 5,000+ customers. Gaps: calls-first, premium, usage not native, not SMB.
- **Salesloft + Clari** — merged (closed Dec 3, 2025); integrated release Apr 15, 2026; Salesloft brand (Sept 2026), Clari Forecast keeps name; MCP server with write-back (Jul 9, 2026). Reported $75–200+/user/month, 10–15 seat minimums, median ~$30.7k/yr (Vendr via SpotSaaS). Gartner MQ for Revenue Action Orchestration (Dec 2025): Clari Leader, Salesloft Visionary, Gong & Outreach Leaders.
- **Outreach, People.ai, BoostUp, Aviso, Revenue Grid, Revenue.io** (positioning) — pre-sale, Salesforce-centric, weak on telemetry and renewals.

### 4.2 Customer success / churn
- **Gainsight (CS + Staircase AI + Atlas)** — category leader. Staircase reads email/meetings/Slack/support; Q2 2026 added Risk, Expansion, Renewal, Churn agents, 14 AI Insight reports ("Account Dark", "No Reach Out", "Churn Risk"), configurable health modifiers, MCP server. Atlas (May 2025) Renewal AI Agent; relaunched May 27, 2026 as AI-native "retention-as-a-service" with configurable autonomy. MCP across CS + Staircase (Apr 2, 2026). Staircase Insight Agent add-on reportedly ~$15k/yr (per Oliv, verify). Gaps: heavy, expensive, enterprise, summaries rather than clickable evidence chain.
- **ChurnZero, Totango/Catalyst, Vitally, Planhat, Custify, ClientSuccess, Velaris** (positioning) — health scores, playbooks; rule-heavy; little evidence-cited reasoning or governed write-back.
- **Hook, Pocus, Common Room** (positioning) — prediction/signals; not approval-governed actions.
- **Rocketlane** (Chennai) — onboarding/PS automation; $60M Series C (Mar 25, 2026); Nitro agentic platform.

### 4.3 CRM-native agents
- **Salesforce Agentforce** — Flex Credits $500/100k (standard action 20 credits = $0.10), $2/conversation, $125/user/month add-on, Agentforce 1 from $550/user/month (pricing secondary). Hosted MCP Servers GA Apr 2026 (Enterprise+; free in Developer Edition) enforcing FLS/sharing; Registry scores MCP tools for tool-poisoning risk (mid-Jul 2026). Acquired Momentum (completed Mar 2, 2026). Gap: best only if all-in on Salesforce.
- **HubSpot Breeze / Agent Hub** — Customer Agent $0.50 per resolved conversation (since Apr 14, 2026), Prospecting $1/lead, Data Agent $0.10/response; agents need Pro/Enterprise. **Remote MCP (mcp.hubspot.com) GA Apr 13, 2026**: OAuth 2.1 + PKCE, free on every tier, read/write standard objects; **no custom objects; executes writes immediately via `manage_crm_objects`; no reviewable plans.**
- **Microsoft Dynamics 365 Copilot** (positioning), **Zoho Zia** (25+ agents, Zia LLM, Agent Studio 700+ actions, MCP — Zoho-only), **Freshworks Freddy AI** (support-first), **Pipedrive AI** (positioning).

### 4.4 AI-native startups
| Company | What | Gap vs us |
|---|---|---|
| Rox | "Hundreds of AI agents" monitoring accounts, updating CRM; $50M seed+A; customers Ramp, MongoDB, New Relic | Enterprise, expensive |
| Momentum.io (now Salesforce) | Deal execution, Customer Retention Agent | Salesforce-only |
| **Oliv AI** | CRM Manager: "Every proposed update surfaces with the exact moment in the conversation that triggered it. Accept, edit, or reject per field." Review default. $5.2M seed | Closest on per-field approval; conversation-sourced, deal-centric |
| Sybill | Call summaries, CRM autofill | Meeting-sourced |
| Attio, Day.ai | AI-native CRMs | CRMs, not risk agents |
| Clay, Default, Unify, 11x, Artisan… | Top-of-funnel | Different job |
| Glean, Relevance AI, Lindy, Zapier Agents, n8n | Horizontal agent builders | No RevOps logic, evidence model or decision log |

### 4.5 Open-source prior art
- **ChurnAlert-AI-v2** — "Full-stack agentic customer churn prediction system with HubSpot MCP, LangGraph, ChromaDB RAG, and LangSmith observability"; Monitor → Score → Reason → Brief → Human Review → Outcome. **Closest prior art — we must go beyond it** (cross-source evidence, reviewable diffs, tiered autonomy, decision record).
- OUTLIER AI (LangGraph + Random Forest + SHAP), churnguard-ai (Stripe/PostHog/HubSpot → XGBoost), competing-risk-churn-agent-v2 (survival analysis), several Devpost hackathon churn projects.

### 4.6 Comparison (●●● strong, ●● partial, ● weak)
| Product | Cross-source | Risk + expansion | Cited explanation | Actions | Human approval | Audit trail | SMB price |
|---|---|---|---|---|---|---|---|
| Gong | ●● | ●●● | ●●● | ●● | ●● | ●● | ● |
| Salesloft + Clari | ●● | ●●● | ●● | ●●● | ●● | ●● | ● |
| Gainsight + Staircase + Atlas | ●●● | ●●● | ●● | ●●● | ●● | ●● | ● |
| Agentforce | ●●● (Data Cloud) | ●● | ●● | ●●● | ●● | ●● | ● |
| HubSpot Agent Hub | ●● | ● | ● | ●● | ● | ● | ●● |
| Rox | ●●● | ●●● | ●● | ●●● | ●● | ● | ● |
| Oliv AI | ●● | ●● | ●●● | ●●● | ●●● | ●● | ●● |
| Open-source repos | ● | ●● | ●● | ● | ●● | ● | ●●● |
| **Our target** | ●●● | ●●● | ●●● | ●●● | ●●● | ●●● | ●●● |

### 4.7 White space (our opportunity)
1. Evidence-linked reasoning across sources with clickable record IDs.
2. Reviewable write plans (field-level diffs) instead of immediate writes.
3. Permanent "why" record: evidence → rule → LLM conclusion → approver → execution → outcome.
4. CRM-agnostic, SMB-affordable (India + global SMB SaaS underserved).
5. Setup in minutes, not months.
6. Transparent learning from approvals/rejections.
7. "What changed" view and action-impact (Phase 2+).
8. Prompt-injection-safe email ingestion.

## 5. Signal taxonomy (what predicts churn/expansion)
| Category | Churn indicators | Expansion indicators | Source |
|---|---|---|---|
| Engagement | Days since last meeting; no next step; cancellations; skipped QBR | Exec asks for roadmap; new teams join | Calendar, CRM |
| Stakeholders | Champion silent/leaving (~20%/yr job change); single-threaded; reorg | Champion promoted; new personas; more threads | Email, CRM |
| Usage | Active users ↓, key features ↓, seat utilization < 60% | Seats at limit, usage above plan, API volume ↑ | Product analytics |
| Sentiment | "Budget", "evaluating alternatives", competitor mention, low NPS | ROI statements, referrals | Email, calls |
| Support (P2) | Ticket spikes, P1 escalations | Higher-tier feature requests | Helpdesk |
| Billing (P2) | Failed payments (~1/3 of churn), downgrades, discount asks | Overages, upgrade inquiries | Stripe |
| Renewal timing | Renewal < 90/60/30 days with no plan | Renewal near + high usage | CRM |
| Company events | Layoffs, M&A, leadership change | Funding, hiring | Enrichment (later) |
**Combinations beat single signals** → compound rule (3+ categories → high severity).

## 6. Technology findings

### 6.1 Agent frameworks
LangGraph (Python) has `interrupt()` + `Command(resume=...)`, human-in-the-loop middleware with approve/edit/reject decisions, and a mandatory checkpointer (`PostgresSaver` for production). Alternatives considered: OpenAI Agents SDK, Claude Agent SDK, CrewAI, Microsoft Agent Framework, Google ADK, Pydantic AI (deferred tool approval, typed outputs), Mastra (TS). **Verdict: LangGraph + Postgres checkpointer + Pydantic action cards.**

### 6.2 Integration platforms
Composio: managed tool-calling + auth, 1,500+ toolkits; pricing changed Aug 2026 (reports conflict — check on signup day). Alternatives: Arcade, Pipedream Connect, Nango (open-source auth + sync), Merge (unified APIs), Paragon, Zapier MCP. Our choice: direct SDKs for core sources (see `thinking.md` ADR-009).

### 6.3 Model (verified Oct 2026)
- **"Qwen 3.9 9B" was not found** in public model trackers (trackers are not exhaustive — confirm with the source you saw).
- **Qwen3.5-9B**: released Mar 2, 2026; Apache 2.0 (VentureBeat); 262K context (tracker).
- **Qwen3.8-27B**: released Aug 14, 2026; Apache 2.0; 262K context extendable to 1M (tracker).

### 6.4 vLLM structured output
vLLM supports guided decoding with a JSON schema (`guided_json`) passed through `extra_body` in the OpenAI client (documented in v0.8.5; parameter names may differ in newer versions — check the deployed version's docs).

### 6.5 Gmail API scopes (compliance)
- Gmail scopes such as `gmail.readonly`, `gmail.compose`, `gmail.modify` are **restricted**. Apps that store/transmit restricted-scope data on their servers need **OAuth app verification + a security assessment (CASA)**, renewed annually; it takes weeks or more and has a cost.
- `gmail.send` is **sensitive** (not restricted).
- Exceptions/limits: apps in **Testing** mode (limited test users), personal use with < 100 users, or **internal-only** apps in a Google Workspace org.
- **Impact:** plan verification early; pilot in testing mode or with HubSpot-logged emails.

### 6.6 Safety & regulation
- Anthropic "Building effective agents" (2024): simple composable workflows; human checkpoints for high-stakes steps.
- OpenAI "A practical guide to building agents" (2025): layered guardrails, tool-risk ratings.
- NIST AI RMF 1.0 + Generative AI Profile (2024): Govern, Map, Measure, Manage.
- EU AI Act: B2B churn agent generally **not** Annex III high-risk; Article 50 transparency relevant for AI-drafted emails → human approve-and-send is the safe pattern.
- India DPDP Act 2023: lawful basis, purpose limitation, safeguards, breach notification for contacts' personal data.
- OWASP Top 10 for LLM apps: prompt injection is the top risk → treat emails as untrusted, allowlist recipients, keep writes behind approval.

### 6.7 Approval design patterns seen in market
Approval inbox with evidence chips; CRM diff previews (Oliv per-field review); Slack approval buttons (Momentum, Rattle); tiered autonomy (auto internal / one-click customer-facing / blocked pricing-contract); undo with pre-images + idempotency keys; edit-and-learn; append-only decision records.

## 7. Trends (2026)
1. Agentic CRM is the default (Salesforce + Momentum, HubSpot Agent Hub, Microsoft, Zoho).
2. MCP is the integration standard (HubSpot, Salesforce, Gainsight, Salesloft, Gong all shipped MCP in 2026) → battleground is **governance over MCP writes**.
3. Consolidation (Clari + Salesloft; Salesforce + Momentum; Gong into enablement/account management).
4. Outcome-based pricing (HubSpot per resolved conversation; Gainsight retention-as-a-service).
5. Bounded autonomy (Gong Revenue Harness, Gainsight configurable autonomy).

## 8. What this means for us (summary)
- Position: **evidence-first, approval-native, CRM-neutral, affordable**. Not "AI health score".
- Must-haves to beat prior art: cross-source evidence fusion, cited claims with validator, field-level diffs + approval, tiered autonomy, decision record with replay + undo, expansion detection.
- Quote carefully: 40% selling time (Salesforce 2026), 84–91% median GRR (Benchmarkit/SaaS Capital), $12.9M bad-data cost (Gartner 2020 research), >40% agentic projects cancelled (Gartner 2025).

## 9. Sources

Retention & productivity
- Aleph NRR 2026 — https://www.getaleph.com/answers/net-revenue-retention-saas-2026
- Churn Buster B2B churn — https://churnbuster.io/articles/b2b-saas-churn-rate/
- Data-Mania B2B SaaS benchmarks 2026 — https://www.data-mania.com/blog/b2b-saas-benchmarks-2026-annual-report/
- Lighter Capital 2025 benchmarks — https://www.lightercapital.com/blog/2025-b2b-saas-startup-benchmarks
- Salesforce sales research 2023 — https://www.salesforce.com/news/stories/sales-research-2023/
- Cirrus Insight sales productivity — https://www.cirrusinsight.com/blog/sales-productivity-statistics
- Databar bad CRM data — https://databar.ai/blog/article/bad-crm-data-why-it-kills-revenue-forecasts-and-how-to-fix-it
- UserGems champion value — https://www.usergems.com/blog/maximize-champion-lifetime-value
- UserGems multithreading — https://www.usergems.com/blog/sales-multithreading
- Salesmotion multi-threading — https://salesmotion.io/blog/multi-threading-sales-strategy
- Gartner agentic AI prediction (Jun 25, 2025) — https://www.gartner.com/en/newsroom/press-releases/2025-06-25-gartner-predicts-over-40-percent-of-agentic-ai-projects-will-be-canceled-by-end-of-2027

Market size
- Grand View — CS platforms — https://www.grandviewresearch.com/horizon/outlook/customer-success-platforms-market-size/global
- Grand View — customer intelligence — https://www.grandviewresearch.com/horizon/outlook/customer-intelligence-platform-market-size/global
- Coherent Market Insights — https://www.coherentmarketinsights.com/industry-reports/customer-success-platform-market
- Strategic Market Research — https://www.strategicmarketresearch.com/market-report/revenue-intelligence-market
- Contrary — Rox — https://research.contrary.com/company/rox

Competitors
- Gong Mission Andromeda — https://www.prnewswire.com/news-releases/gong-launches-mission-andromeda-expanding-its-revenue-ai-os-to-enablement-and-account-management-302696470.html
- Clari review 2026 — https://marketbetter.ai/blog/clari-review-2026/
- Salesloft pricing — https://www.spotsaas.com/blog/salesloft-pricing
- Gainsight Staircase AI — https://www.gainsight.com/staircase-ai/
- Staircase Q2 2026 release notes — https://support.gainsight.com/Staircase_AI/Release_Notes/Current_Release_Notes_-_2026/Q2_2026_Release_Notes_for_Staircase_AI
- Gainsight Atlas — https://www.gainsight.com/press/gainsight-launches-atlas-ai-agents-for-customer-retention-and-growth/
- Gainsight AI-native services — https://www.gainsight.com/press/gainsight-announces-new-ai-native-services-business/
- Gainsight MCP — https://www.globenewswire.com/news-release/2026/04/02/3267679/0/en/gainsight-opens-its-platform-with-mcp-bringing-customer-retention-into-the-agentic-era.html
- Agentforce pricing — https://www.supered.io/blog/agentforce-pricing/
- Salesforce hosted MCP GA — https://developer.salesforce.com/blogs/2026/04/salesforce-hosted-mcp-servers-are-now-generally-available
- Salesforce acquires Momentum — https://www.salesforce.com/news/stories/salesforce-signs-definitive-agreement-to-acquire-momentum/
- HubSpot Breeze pricing change — https://resolve247.ai/blog/hubspot-breeze-pricing-change/
- HubSpot MCP vs API — https://www.scalekit.com/blog/hubspot-mcp-vs-api
- What HubSpot's official MCP misses — https://daeda.tech/blogs/hubspot-mcp-in-2026-what-the-official-one-misses/
- Oliv CRM Manager — https://www.oliv.ai/agents/crm-manager
- Zoho Zia LLM + agents — https://www.zoho.com/news/zoho-launches-zia-llm-and-deepens-ai-portfolio-with-prebuilt-agents-custom-agent-builder-mcp-and-marketplace.html
- Rocketlane Series C — https://www.rocketlane.com/press/rocketlane-raises-series-c
- ChurnAlert-AI-v2 — https://github.com/SaiShruthiSridhar/ChurnAlert-AI-v2

Technology & compliance
- LangChain human-in-the-loop — https://docs.langchain.com/oss/python/langchain/human-in-the-loop
- Composio (agent index) — https://theaiagentindex.com/agents/composio
- Qwen3.5-9B (VentureBeat) — https://venturebeat.com/technology/alibabas-small-open-source-qwen3-5-9b-beats-openais-gpt-oss-120b-and-can-run
- Model release tracker (Alibaba/Qwen) — https://www.llm-releases.com/labs/alibaba
- vLLM structured outputs (v0.8.5 source) — https://docs.vllm.ai/en/v0.8.5/_sources/features/structured_outputs.md
- Gmail API scopes — https://developers.google.com/workspace/gmail/api/auth/scopes
- Google verification & security assessment guide (Nylas) — https://developer.nylas.com/docs/dev-guide/provider-guides/google/google-verification-security-assessment-guide
