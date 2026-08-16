# Reweave — Build Plan & Agent Brief

**Working codename:** "Reweave" (weaving duplicated threads back into one). Verify trademark + domain availability before any public launch; treat the name as a config value, not a constant.

**Document status:** Canonical. This file is the source of truth for what we are building, why, and in what order. If reality diverges from this plan, update this document in the same PR that diverges. Claude Code: read this file and `CLAUDE.md` at the start of every working session.

---

## 0. The one thing to never forget

**This is a commercial product that will be sold to paying customers.** It is not a research project, a portfolio piece, or an internal tool. Every decision — code quality, UX polish, security posture, documentation, error messages, billing — is made in service of a stranger pulling out a credit card and trusting us with their company's source code. When in doubt between "clever" and "trustworthy," choose trustworthy. When in doubt between "more features" and "more finished," choose finished.

Definition of a successful v1: **a self-serve SaaS with a working free funnel, a paid subscription via Stripe, at least one design-partner-to-paying-customer conversion, and zero incidents involving customer code.**

---

## 1. What we are building

**Reweave is a codebase-health platform for the AI era.** AI assistants now write ~half of all new code, and it ships with a specific, measurable disease: semantically duplicated logic, architectural drift, and "comprehension debt" — code that works but that no one on the team understands. Surveys of engineering leaders rank codebase comprehension as their single highest anxiety, refactoring has collapsed from ~25% of code changes to under 10%, and technical debt rises 30–41% within six months of AI tool adoption. Existing tools either *review the diff* (CodeRabbit, Greptile), *gate on generic rules* (SonarQube), or *chart the decay* (GitClear, CodeScene). **Nobody detects AI-specific debt precisely and then fixes it.** That is our position: **detect → measure → remediate → prevent.**

### 1.1 The four product pillars

1. **Detect** — Find semantic duplicates (same behavior, different text — invisible to token-based tools like jscpd/PMD), dead and orphaned code, and convention drift, using AST analysis + embeddings + LLM adjudication.
2. **Measure** — A dashboard and shareable reports: Debt Score, AI-code share, duplication clusters ranked by blast radius, trend lines an engineering lead can put in front of a VP.
3. **Remediate** — One-click, test-verified consolidation PRs. Small, single-purpose, evidence-attached. The report is marketing; **the fix is the product.** We only propose a fix where consolidation is *desirable*, not merely *possible* — see D16.
4. **Prevent** — A lightweight PR check ("the ratchet") that flags when a new PR re-implements logic that already exists, with a pointer to the existing implementation. This is the daily-touchpoint feature that keeps us visible in the workflow.

### 1.2 Who buys it and how we make money

- **Buyer:** Engineering leads / CTOs at teams of 5–100 developers using AI coding tools heavily. Secondary: agencies shipping AI-built client work; solo founders whose vibe-coded app got real users.
- **Model:** Free public-repo audit (top of funnel) → **Team plan ~$25/developer/month** (continuous scanning, dashboard, ratchet check, digests) → **metered remediation credits** for auto-generated consolidation PRs (aligns our LLM costs with revenue). Annual plans and an upmarket tier (SSO, policies) later.
- **Price anchors from the market:** GitClear from $9, CodeScene €18–27/author, CodeRabbit $24, Greptile $30, Graphite $40 per dev/month. We sit mid-band and justify it with the only metric that writes its own renewal email: **lines of code deleted.**
- **Distribution:** GitHub Marketplace listing + the free audit's shareable scorecard + original research content ("we scanned N repos"). This is the proven playbook in the adjacent code-review category (CodeRabbit became the most-downloaded Marketplace app).

### 1.3 Non-goals for v1

- No GitLab/Bitbucket. No languages beyond TypeScript/JavaScript and Python. No IDE plugin. No on-prem. No auto-merge, ever. No general-purpose code review (we do not compete with CodeRabbit; we complement it). No fine-tuning our own models.

---

## 2. How developers will use it (workflow integration)

This section defines the product experience end-to-end. Build every phase against this journey.

**Step 1 — Discover (no signup):** A developer pastes a public GitHub URL on our site (or runs `pipx run reweave-audit .` locally so private code never leaves their machine) and gets a **Debt Audit scorecard**: letter grade, estimated AI-code share, top duplication clusters with side-by-side evidence, refactor-ratio trend. The page has share-friendly OG images and a "scan yours" CTA. Email capture unlocks the full report.

**Step 2 — Install:** They install the **Reweave GitHub App** on their org, select repos, and we run a baseline index. A progress UI shows parsing → fingerprinting → clustering. Within ~15 minutes they see their dashboard.

**Step 3 — Daily (the ratchet):** On every PR, a GitHub Check runs. If new/changed code semantically duplicates existing code, we post **one** consolidated, informational comment: *"`formatCurrency` in this PR duplicates `lib/money.ts:formatMoney` (14 call sites) — **91% structural similarity, 46% textual overlap**. Consider reusing it — or open a consolidation PR after merge."* Non-blocking by default; teams can make it required once they trust it. Silence when there's nothing to say — no noise, ever.

> **Every displayed percentage names its own computation (D17).** We show two deterministic, reproducible numbers — normalized-AST structural similarity and raw textual overlap — never a single blended "94% match." Both are cheap by-products of D5 stage 1, both survive a developer opening the two files and checking, and neither claims to be a probability that the pair is a true duplicate. The semantic verdict itself stays categorical (duplicate / not), because that is what the adjudicator actually returns.

**Step 4 — Weekly:** A Slack/email digest: debt trend, newly formed clusters, top three suggested remediations with estimated lines removed.

**Step 5 — Remediate:** From the dashboard (or the digest), one click opens a **consolidation PR**: the cluster's functions unified into one implementation, all call sites updated, the repo's test suite executed in our sandbox before the PR is opened, and an evidence block in the PR body (similarity analysis, tests run, revert instructions). The team reviews and merges it like a teammate's PR.

**Step 6 — Monthly:** An exportable leadership report (HTML/PDF) — the artifact the budget holder forwards to justify the subscription.

**Positioning next to their existing tools:** CodeRabbit/Greptile review the diff in front of you; Sonar gates on rule violations; GitClear charts metrics. **Reweave watches the whole codebase across time and cleans it.** We should never fight for the same PR comment space — max one comment, only when we have something they don't.

---

## 3. Key design decisions (ADR summaries)

Each decision below is binding until superseded by a written ADR in `docs/adr/`. Claude Code: if you believe a decision should change, write the ADR (context, options, trade-offs, consequences) and stop for review — do not silently deviate.

**D1. Monorepo.** Everything in one repository. *Why:* a solo founder + an AI agent both benefit from total visibility and atomic cross-cutting changes; no version skew between engine, API, and web. *Revisit when:* the engine needs an independent open-source release.

**D2. Python engine + Django API.** The analysis engine is a pure-Python package; the API/backend is Django (with DRF). *Why:* the owner operates this alone and knows Django deeply — boring tech he can debug at 2 a.m. beats fashionable tech he can't; Django's batteries (auth, admin, ORM, migrations) shrink the solo surface area; the parsing/ML ecosystem (tree-sitter bindings, numpy, model clients) is Python-native. *Alternatives rejected:* FastAPI (more assembly required for auth/admin), full TypeScript backend (splits the engine from its ecosystem). *Revisit when:* p95 API latency or team size demands it.

**D3. Next.js + TypeScript for web (marketing site + dashboard).** *Why:* the dashboard's polish is part of the sales pitch; the React ecosystem gives us production-grade charts and components; deploys cleanly to Vercel. *Consequence:* two deploy targets — accepted cost.

**D4. tree-sitter for parsing.** *Why:* one uniform, fast, incremental parsing API across languages; adding a language later is additive, not an architecture change. Start with TS/JS + Python because that's where AI codegen concentrates.

**D5. Three-stage duplicate detection: structural candidates → embedding rerank → LLM adjudication.** (1) Normalize ASTs (strip identifiers/literals), fingerprint, and generate candidate pairs cheaply via MinHash/LSH; (2) rerank candidates with code embeddings (cosine similarity), cached by content hash; (3) send only the shortlist to an LLM adjudicator with a strict rubric ("same observable behavior? consolidation feasible? consolidation *advisable*?" — D16) that must return a verdict + rationale. *Why:* precision economics — LLM spend only on a shortlist; every stage independently cacheable and testable; thresholds tunable in config. *Rejected:* pure-embedding decisions (too noisy), pure-LLM over all pairs (cost explodes quadratically).

**D6. Precision over recall, as explicit product law.** False positives are the documented graveyard of this category (30–35% FP rates are the top cited restraint for static analysis; noisy AI reviewers are the top complaint in the adjacent market). A missed duplicate costs us nothing today; a wrong comment costs us the customer. *Mechanism:* adjudicator disagreement → discard; the ratchet check ships in informational mode until measured FP < 5% with design partners; engine changes are gated by the benchmark (D12).

**D7. Read-only core; pull requests are the only write path.** The app never pushes to any protected/default branch, never force-pushes, never auto-merges. All writes are: create branch → commit → open PR. Enforced in code (a single `GitWriter` module owns all write operations and refuses anything else) and in tests. *Why:* trust is the product; blast radius must be structurally bounded.

**D8. Test-verified remediation in an egress-blocked sandbox.** Running a customer's test suite is remote-code-execution by design, so it happens only inside an isolated container: no network egress, no secrets mounted, CPU/memory/time caps, workspace destroyed after the job. A consolidation PR opens only if the suite passes before and after the change and the diff touches only planned files. If the target code lacks tests: generate characterization tests first, or downgrade to a suggestion (no PR). *Why:* an auto-refactorer that breaks builds is dead on arrival; the sandbox rule is also our security story.

**D9. GitHub App with least-privilege scopes.** Permissions: `contents: read`, `pull_requests: write`, `checks: write`, `metadata: read` — nothing more. *Why:* per-repo installs, revocability, Marketplace distribution, and a permissions screen a security reviewer can approve without a meeting. *Rejected:* user OAuth tokens (over-scoped, tied to individuals).

**D10. We store derived data, never whole source code.** Clones are shallow, ephemeral, and deleted at job end. We persist only: fingerprints, embeddings, metrics, findings, and minimal evidence snippets (the specific matched regions, size-capped, encrypted at rest, deletable on request). Code content is never written to logs. Uninstalling the GitHub App purges all repo-derived rows (snippets, embeddings, findings) within 30 days, and immediately on request. *Why:* "where does our code live?" is the first sales objection, and a short honest answer wins deals and shortens our SOC 2 path.

*Say it precisely, because a security reviewer will check:* we do retain evidence snippets (small verbatim excerpts), and embeddings are derived from code but are **not** a privacy guarantee — embedding-inversion research can recover approximate content from vectors. The defensible claim is "we don't keep your repository; we keep capped, encrypted excerpts of the specific matched regions plus derived vectors and metrics." Never ship the line "we keep math about it, not the code" — it overstates by exactly the amount that destroys trust when someone reads the schema.

**D11. Anthropic API for adjudication and PR generation, treated as a metered cost center.** Structured outputs only; per-scan token budgets enforced in code; responses cached by content hash; repository content is always **data, never instructions** — wrap it in delimited blocks, instruct the model to ignore any directives inside it, and validate outputs against schemas (prompt-injection defense: a malicious repo must not be able to steer our agent). Model IDs live in config.

**D12. Eval-first engineering, at two levels.** Detection quality is an ML product. We maintain a labeled benchmark corpus (`benchmarks/`) of duplicate and hard-negative pairs with a held-out split. CI computes precision/recall on every engine change; merges that drop precision below the gate are blocked. Never tune on the holdout. *Why:* without this, "improvements" are vibes.

**The pair benchmark alone will lie to us, so it is not sufficient.** A curated corpus is roughly balanced; production is not. A 300k-LOC repo has ~10⁹ candidate pairs of which maybe a few hundred are true duplicates — a class imbalance of six-plus orders of magnitude. A detector at 0.95 precision on balanced pairs can easily land under 0.30 precision in production, and *that* is the number the customer experiences. So we run **two** evals: (a) the pair benchmark as the fast CI gate, and (b) a **repo-level eval** — full scans of a fixed set of real repositories where we hand-label 100% of what the pipeline surfaces, reported as precision@k and findings-per-KLOC. The repo eval is the one that governs shipping decisions and the D6 informational-mode gate; the pair benchmark only governs merges. Corpus stored as **pointers** (repo URL + commit SHA + span + label), never vendored code — this keeps us clean on OSS licensing and consistent with D10.

**D13. Postgres (+pgvector) as the only system of record.** Embeddings live in pgvector; jobs in Redis-backed Celery queues. Redis is a broker and cache — nothing that matters may exist only in Redis, and a full Redis flush must cost us in-flight jobs and nothing else. *Why:* one database to operate, back up, and reason about. *Revisit when:* vector search latency at scale demands a dedicated store.

**D14. Boring managed hosting.** API + workers on Railway/Fly/Render; Postgres managed (Neon/RDS); web on Vercel; Sentry for errors; Plausible/PostHog for analytics. *Why:* solo ops. Kubernetes is explicitly banned in v1.

**D15. Billing is architecture, not an afterthought.** Plans, quotas, and usage metering are modeled in the schema from Phase 2 even though Stripe goes live in Phase 5. *Why:* the goal is selling; metering shapes the job system, and free-tier abuse limits must exist before the free tier does.

**D16. Not every duplicate should be consolidated — "desirable" is a separate test from "correct."** This is the decision most likely to sink the product if we get it wrong, because it is invisible in the benchmark. Our precision law (D6) protects us from *"these aren't the same"*; nothing yet protects us from *"they are the same, and they should stay that way."* Duplication is often a deliberate, correct engineering choice — the wrong abstraction costs more than the duplication it removes, and a senior reviewer who receives a PR coupling two modules that were kept apart on purpose will uninstall us and tell their friends why.

So the adjudicator returns a **consolidation recommendation** distinct from its duplicate verdict, and we **never surface a remediation** (though we may still count the pair in metrics) when any of these hold:

- The units sit on opposite sides of a deliberate boundary — different services, packages, bounded contexts, or ownership (CODEOWNERS) — where consolidation would create a new cross-boundary dependency.
- The code is generated, vendored, migrations, fixtures, or test scaffolding.
- The duplicates have **diverged in git history** — both edited independently in the last 90 days is strong evidence they are evolving apart on purpose.
- Unifying requires a parameter, flag, or branch to reconcile behavioral differences (the "add a boolean argument" smell — that is the wrong abstraction, mechanized).
- The shared logic is small and stable enough that the indirection costs more than it saves (config-driven floor, default ~10 lines).

*Why:* our stated value metric is lines deleted, which is precisely the incentive that produces over-abstraction. This decision is the counterweight, and it is why the remediation exit gate is *merged without human correction*, not *opened*. Design-partner feedback on rejected suggestions is the primary tuning signal for these rules.

**D17. Every number we display names its computation.** User-facing similarity is reported as named, deterministic measures — normalized-AST structural similarity and textual overlap — not a single blended score and not a confidence probability. Semantic verdicts stay categorical. Estimates (AI-code share) are labeled as estimates and shown as ranges. *Why:* every displayed number is a claim we may have to defend to a skeptical staff engineer in a PR thread; a number we can recompute in front of them survives that, an invented one does not. *Consequence:* the engine's finding schema carries each metric separately with its method tagged. Composite indices are allowed where they're honest about being one — the Debt Score and letter grade are deliberate roll-ups, so their formula is **published on the site and versioned**, and the dashboard always lets a user drill from the score to the findings underneath it. What's banned is blending distinct measurements into a single unexplained number at the point of a specific claim about specific code.

---

## 4. Architecture overview

```
                        ┌────────────────────────────┐
                        │  Web (Next.js on Vercel)   │
                        │  marketing · audit · app   │
                        └─────────────┬──────────────┘
                                      │ HTTPS/JSON
┌───────────────┐   webhooks   ┌──────┴───────┐    enqueue    ┌───────────────┐
│    GitHub     │─────────────▶│  API (Django)│──────────────▶│ Redis / Celery│
│  (App install,│◀─────────────│  auth·orgs·  │               └──────┬────────┘
│  PRs, checks) │  Checks, PRs │  billing·API │                      │ jobs
└───────────────┘              └──────┬───────┘               ┌──────┴────────┐
                                      │                       │   Workers     │
                               ┌──────┴───────┐               │ scan · embed  │
                               │  Postgres    │◀──────────────│ adjudicate ·  │
                               │  (+pgvector) │  derived data │ remediate     │
                               └──────────────┘               └──────┬────────┘
                                                             ┌───────┴────────┐
                                                             │ Sandbox runner │
                                                             │ (Docker, no    │
                                                             │  egress) tests │
                                                             └────────────────┘
```

**Scan data flow:** webhook/API → enqueue scan → worker shallow-clones to tmpfs → tree-sitter extracts functions/methods ("code units") → normalize → fingerprint → MinHash candidates → embed (cache by SHA) → rerank → LLM adjudicate shortlist → cluster → persist findings/metrics → delete clone → notify (dashboard, check, digest).

**Core data model (initial):** `users`, `orgs`, `installations`, `repos`, `scans`, `code_units` (path, span, hash, fingerprint), `symbol_refs` (resolved call sites — powers blast radius and call-site rewrites), `embeddings` (pgvector, keyed by content hash), `clusters`, `findings` (type, evidence, per-metric scores with method tags per D17, status), `feedback` (thumbs + design-partner labels on findings — the FP measurement substrate), `checks`, `remediations` (plan, sandbox log, PR url, outcome), `plans`, `subscriptions`, `usage_events`, `audit_log` (every external write we ever perform).

**Call-site resolution is a subproject, not a bullet.** Blast-radius ranking and every call-site rewrite in Phase 4 depend on knowing who calls a function — and resolving that in real TS/JS is genuinely hard: path aliases, barrel re-exports, monorepo workspaces, dynamic imports, re-assignment, `export *`. Budget for it explicitly. **v1 resolves conservatively and admits its limits:** static imports plus same-package references only, with unresolvable references counted and displayed ("14 known call sites, 3 unresolved"). Remediation refuses to rewrite call sites in any file whose references we could not fully resolve — an unresolved reference is a silent breakage waiting to happen, and D8's test gate will not always catch it.

**Error posture:** every job idempotent and retry-safe; queue backpressure with depth alarms; our failures must be invisible to customers' workflows — a broken Reweave never blocks a merge (checks fail *neutral*, never *failure*, on our internal errors).

---

## 5. Repository layout

```
reweave/
├── CLAUDE.md                  # Agent operating manual (commands, conventions, guardrails)
├── README.md                  # What this is, quickstart for the owner
├── SECURITY.md                # Data handling promises; vuln disclosure contact
├── LICENSE                    # Proprietary — all rights reserved (this is a product)
├── Makefile                   # make dev / test / bench / lint / deploy
├── docs/
│   ├── PLAN.md                # ← this document
│   ├── adr/                   # ADR-0001..n (D1–D17 seeded here in Phase 0)
│   ├── runbooks/              # deploy, incident, restore-from-backup, rotate-secrets
│   └── product/               # pricing copy, positioning, launch checklist
├── apps/
│   ├── api/                   # Django project
│   │   ├── config/            # settings (12-factor, env-driven), urls, asgi
│   │   ├── accounts/          # users, orgs, teams, roles
│   │   ├── github/            # App auth, webhooks, GitWriter (sole write path)
│   │   ├── scans/             # scan lifecycle, findings, clusters
│   │   ├── remediation/       # remediation orchestration endpoints
│   │   ├── billing/           # plans, quotas, usage metering, Stripe (Phase 5)
│   │   └── notifications/     # digests: email + Slack
│   └── web/                   # Next.js (TypeScript, strict)
│       ├── app/(marketing)/   # landing, pricing, blog, audit entry
│       ├── app/(product)/     # dashboard, clusters, remediations, settings
│       └── components/
├── packages/
│   ├── engine/                # pure-Python analysis library — no Django imports
│   │   ├── parsing/           # tree-sitter loaders, code-unit extraction
│   │   ├── normalize/         # AST normalization
│   │   ├── fingerprint/       # structural hashing, MinHash/LSH
│   │   ├── resolve/           # imports → symbol refs → call graph (conservative)
│   │   ├── embed/             # embedding client + content-hash cache
│   │   ├── adjudicate/        # LLM rubric, schemas, injection-safe wrapping
│   │   ├── cluster/           # grouping, blast-radius ranking
│   │   ├── metrics/           # AI-share estimation, refactor ratio, debt score
│   │   ├── report/            # JSON + static HTML renderers
│   │   └── cli.py             # `reweave-audit` (also published via pipx)
│   ├── remediation/           # PR planner, constrained codemods, verification harness
│   └── shared/                # pydantic schemas, event types, config
├── workers/                   # Celery app: scan, embed, adjudicate, remediate tasks
├── sandbox/                   # sandbox runner image + policy (no-egress, caps)
├── benchmarks/
│   ├── corpus/                # pointers + labels only (repo·SHA·span); holdout split
│   ├── repos/                 # fixed repo set for the repo-level eval (D12b)
│   ├── run_bench.py           # pair precision/recall; wired into CI gate
│   └── run_repo_eval.py       # full-scan precision@k + findings/KLOC (ship gate)
├── infra/                     # Dockerfiles, docker-compose.dev.yml, deploy configs
├── ops/                       # seed scripts, cost dashboards, admin utilities
└── .github/workflows/         # ci.yml (lint, typecheck, tests, bench-gate), deploy.yml
```

**Layout rules:** `packages/engine` never imports from `apps/` (it must run standalone as the CLI and in tests). `packages/remediation` may depend on `engine`; never the reverse. All GitHub writes go through `apps/api/github/GitWriter`. Unit tests live beside the code they test; only cross-service e2e lives in a top-level `tests/`.

---

## 6. Phased milestones

Each phase has **action points**, **exit criteria** (gates — do not proceed until met), and **failsafes**. Timeboxes assume focused solo + agent work; quality gates outrank dates.

**Three notes on the shape of this schedule, before the phases:**

1. **Treat 14 weeks as the optimistic arm of a 14–26 week range.** Phase 4 in particular — constrained codemods, a hardened sandbox, and call-site rewriting that reaches a 90% clean-merge rate — is a quarter of work on its own for one person. The phase *order* is what matters and is well-chosen; the dates are a forecast, not a commitment, and no gate gets lowered to hit one.
2. **Revenue is not gated on remediation.** Phases 4 and 5 are deliberately swappable. After Phase 3 we have continuous scanning, a dashboard, and the ratchet — that is a sellable product at a lower price, and design partners will tell us whether prevention alone clears their bar. If Phase 4 runs long, turn on Stripe first and sell what works. Shipping the hardest technical component before the first dollar is the single most common way a plan like this dies with runway spent and zero market feedback.
3. **Customer contact starts in week 1, not week 5.** Design-partner recruitment moves to Phase 0 so that every subsequent gate is measured against real repositories and real reactions.

### Phase 0 — Foundations (days 1–4)
**Actions:**
- [x] Scaffold the monorepo exactly as §5; Python 3.12 + `uv`, Node 24 LTS + `pnpm` (Node 20 reached EOL April 2026 — ADR-0003).
- [x] Tooling: ruff + pyright (strict), pytest; eslint + prettier + `tsc --strict`; pre-commit hooks; conventional commits.
- [x] CI: lint → typecheck → tests → benchmark gate (dummy detector initially), on every PR.
- [x] Write `CLAUDE.md` (see §8) and seed `docs/adr/` with D1–D17.
- [x] Build the benchmark harness + corpus v0 (≥150 labeled pairs, **stored as pointers** per D12): mine real intra-repo clones from permissively-licensed OSS as candidates, hand-label; synthesize AI-style duplicates (prompt a model to re-implement existing functions); include **hard negatives** (similar-looking, semantically different). Create the holdout split now and never touch it for tuning.
- [x] Label a D16 dimension on every corpus pair while you're already reading it: *should* these be consolidated? It costs almost nothing now and is the only way to measure the desirability rubric later.
- [ ] **Start design-partner recruitment now** (owner task, runs in the background for weeks). Target 5 teams of 5–100 devs using AI tooling heavily. The ask at this stage is small and honest: "can I run an early detector over your repo and walk you through what it found?" Their reaction to raw Phase 1 output is the cheapest product feedback we will ever get.

**Exit criteria:** CI green end-to-end; `make bench` emits a precision/recall report; docker-compose brings up api+db+redis+worker locally in one command; ≥ 2 design-partner conversations booked.
**Failsafes:** if corpus labeling stalls, ship the 150 minimum and grow weekly — never launch detection features that outrun the corpus's ability to measure them. Partner recruitment never blocks engineering; it runs in parallel.

### Phase 1 — Engine v1: semantic duplicate detection (weeks 1–3)
**Actions:**
- [x] tree-sitter parsing for TS/JS + Python; extract function/method code units with spans + content hashes.
- [x] AST normalization → structural fingerprints; MinHash/LSH candidate generation with a hard candidate budget.
- [ ] Embedding rerank (model choice behind an interface; cache by content hash in Postgres).
- [x] LLM adjudication with a strict rubric and JSON schema (verdict, consolidation-feasibility, **consolidation-advisability + which D16 rule fired**, rationale). *(built and unit-tested offline; not yet exercised against the live API — no key configured)*
- [ ] Conservative import/symbol resolution (`engine/resolve/`) → `symbol_refs`, with unresolved references counted, never guessed.
- [ ] Clustering + blast-radius ranking (call sites × recent churn).
- [ ] `reweave-audit` CLI producing JSON + a polished static HTML report.
- [ ] **Show raw output to design partners** — no UI, just findings on their repo, walked through live. Record every "that's wrong" and every "that one's intentional"; the latter are D16 rules we haven't written yet.

**Exit criteria (pair benchmark, holdout):** precision ≥ 0.90 at recall ≥ 0.50; full scan of a 300k-LOC repo ≤ 10 min on a dev machine; deterministic re-runs given warm caches; per-scan LLM cost measured and logged.
**Exit criteria (repo-level eval, D12):** on the fixed repo set, ≥ 0.70 precision@20 with hand-labeling of everything surfaced, and findings-per-KLOC low enough that a human can review a whole repo's top findings in one sitting. *This gate, not the pair benchmark, is what predicts what a customer will see.* Expect the first repo-eval run to be humbling relative to the pair number — that gap is the point of running it.
**Failsafes:** if embeddings underperform, fall back to AST-similarity + adjudication-only (interface makes this a config change); if runtime blows up, tighten the candidate budget and prioritize high-churn files; all thresholds in config, none hardcoded; adjudicator uncertainty → discard the pair (precision law, D6).

### Phase 2 — Free Audit funnel + marketing site (weeks 3–5)
**Actions:**
- [ ] Django API + Celery pipeline running the engine on shallow clones of **public repos only** (size caps: 500 MB / 500k LOC).
- [ ] Scorecard page: grade, top clusters with side-by-side evidence, refactor-ratio trend; OG share images; email capture for the full report.
- [ ] AI-share estimate, handled carefully: `Co-authored-by` trailers + churn heuristics catch a minority of AI-authored code, because the dominant tools (Copilot, Cursor, inline completions) leave no trailer at all. Show it as a **labeled range with its method disclosed and a floor framing** ("at least ~20% of commits show AI-assistance markers"), never a single confident number, and never as the scorecard's headline. Rationale: it is the first figure a visitor checks against their own knowledge of their repo, so an obviously-low number discredits everything else on the page. Duplication findings — which we can *show* them — carry the scorecard.
- [ ] Publish the CLI (`pipx run reweave-audit`) so private-code users can audit locally — code never leaves their machine; report upload optional.
- [ ] Marketing site: landing, how-it-works, **published pricing page** (even pre-billing), security page describing D10 honestly, blog scaffold.
- [ ] Sentry + analytics + a cost dashboard (per-audit unit cost).
- [ ] ToS + privacy policy from a reputable template service; form the business entity; open the business bank account. *(Owner tasks — the agent scaffolds the pages and flags the blanks.)*

**Exit criteria:** a stranger completes an audit unaided; p95 audit time < 15 min; unit cost per audit < $0.50; legal pages live; the scorecard is something a developer would actually screenshot.
**Failsafes:** aggressive rate limits + repo size caps + content-hash dedupe (repeat scans are free); queue-depth alarms with a graceful "we'll email you when it's done" overflow path; kill switch that pauses public intake without touching the rest of the system.

### Phase 3 — GitHub App, dashboard, and the ratchet (weeks 5–8)
**Actions:**
- [ ] GitHub App with D9's minimal scopes; install/onboarding flow; private-repo scan pipeline; incremental re-index on push. Webhook signature verification and short-lived installation tokens from day one; **size tiers for installed repos** (the 500k-LOC cap can't just be a public-audit rule — a 5M-LOC monorepo installing us on day one must degrade to prioritized partial indexing, not melt the queue).
- [ ] Uninstall handling: revoke, stop scanning, purge repo-derived rows per D10. Test it; an uninstall that leaks data is the incident that ends the company.
- [ ] Org/repo dashboard: Debt Score trend, cluster explorer with evidence viewer, AI-share, scan history.
- [ ] The ratchet: on PR webhooks, compare changed code units against the index; post at most **one** informational comment + a neutral check with details, with per-comment 👍/👎 capture.
- [ ] Weekly Slack/email digest; team seats + roles; audit log of all external actions.
- [ ] Onboard the 5 design partners recruited in Phase 0 (agent builds the invite/allowlist system).

**Measure false positives properly — thumbs alone will not do it.** Thumbs telemetry is response-biased (most developers click nothing; the ones who click are disproportionately annoyed) and at 5-partner scale the sample is far too small to establish "< 5%" at any useful confidence. So while partner count is small, **manually review 100% of ratchet comments** — every comment we post gets owner-labeled correct/incorrect against the actual code, weekly, in a spreadsheet if necessary. Thumbs are a supplementary signal and a UI affordance, not the measurement. Switch to sampling only once volume makes full review impossible, and state the confidence interval alongside the rate whenever it's quoted.

**Exit criteria:** 5 design partners installed and receiving checks; **≥ 100 ratchet comments manually adjudicated** with FP rate < 5%; ≥ 2 partners say unprompted that they'd pay for prevention alone (this is the signal that decides the Phase 4/5 order); check p95 latency < 90 s; zero writes outside `GitWriter`; uninstall purge verified end-to-end.
**Failsafes:** ratchet is informational-only until the FP gate is met (then opt-in enforce per repo); per-org and global kill switches; comment budget = 1 per PR, silence on any internal error (our outage must never block their merge); permissions re-audited against D9 before Marketplace submission.

### Phase 4 — Remediation engine (weeks 8–12, or after Phase 5 — see §6 note 2)
**Actions:**
- [ ] Planner: select safest clusters first (intra-package, exact/near-exact, low fan-out, fully-resolved call sites, no D16 exclusion); expand scope only after merge-rate data supports it.
- [ ] Executor: LLM-constrained edits (unified diffs validated against the AST — reject any edit outside planned spans); call-site rewrites.
- [ ] Sandbox runner per D8: detect or accept a configured test command; run suite pre/post in the egress-blocked container; capture logs.
- [ ] PR composer: branch + PR with evidence block (similarity analysis, tests-run log, files touched, revert instructions); dashboard + digest entry points; weekly per-repo caps.
- [ ] Metering: every remediation consumes credits (recorded now, billed in Phase 5).

**Exit criteria:** on design-partner repos, ≥ 90% of opened PRs merge without human correction; **PRs closed-unmerged are categorized** — "wrong" vs. "correct but we don't want it" (D16 miss) vs. "not now" — because those three failures need different fixes and an undifferentiated merge rate hides which one is killing us; 0 writes to protected branches (verified by tests against `GitWriter` and by audit log review); documented rollback path in every PR body.
**Failsafes:** no/weak tests → generate characterization tests first or emit suggestion-only (no PR); unresolved call sites in scope → suggestion-only; hard caps: ≤ 300 changed lines/PR, ≤ 3 PRs/repo/week; any verification ambiguity → abort silently and log for review; never chain PRs on unmerged PRs; never auto-merge (D7). **Note that a passing test suite is weaker evidence than it feels** — it proves we didn't break what was covered, not that consolidation was right; coverage of the touched spans is part of the go/no-go, not a footnote.

### Phase 5 — Monetization & public launch (weeks 12–14; may precede Phase 4)
**Actions:**
- [ ] Stripe: checkout, customer portal, webhooks (incl. failed payments + dunning), plan enforcement + quota middleware, credit metering. If remediation isn't ready, launch the prevention-and-measurement product at a lower price with remediation credits sold as an add-on when it ships; grandfather early customers.
- [ ] GitHub Marketplace listing (recommend: free listing + direct Stripe billing to keep margin; document the trade-off in an ADR).
- [ ] Onboarding email sequence; docs site (install, ratchet, remediation, data handling, FAQ); support channel + response-time promise.
- [ ] SOC 2 runway checklist: access control, secrets rotation runbook, logging review, vendor inventory (compliance platform later, controls now).
- [ ] Launch assets: original research report ("The state of AI code debt: what we found scanning N repositories"), Show HN + Product Hunt drafts, honest comparison pages (vs Sonar / GitClear / CodeRabbit — respectful, factual).

**Exit criteria:** **first paying customer**; billing e2e-tested including failure paths; deploy/incident/restore runbooks exist and have each been rehearsed once; pricing page ↔ Stripe ↔ quota enforcement fully consistent.
**Failsafes:** feature flags + grandfathering for any pricing change; usage alerts to customers *before* hard caps engage; documented refund policy; launch traffic rate-limited at the audit intake (Phase 2's kill switch already exists).

### Phase 6 — Expansion (post-launch, sequenced by revenue signal)
Comprehension-debt map (churn × complexity × ownership × review coverage of AI-authored code) → provenance ingestion (agent trailers; compatibility with emerging attribution formats) → Java/Go → GitLab → policy engine ("new code may not duplicate; AI code requires review") → SSO/SAML + annual invoicing for upmarket.

---

## 7. Quality, security, and trust requirements (non-negotiable)

1. **Sandbox law (D8):** customer code executes only in egress-blocked, secret-free, resource-capped, ephemeral containers.
2. **Write-path law (D7):** all repo writes flow through `GitWriter`; branch-and-PR only; auto-merge is structurally impossible.
3. **Data law (D10):** no source code at rest beyond capped, encrypted evidence snippets; no code content in logs — ever; deletion on request actually deletes.
4. **Injection law (D11):** repository content is data, never instructions; all LLM I/O schema-validated; a hostile repo must not be able to alter our behavior.
5. **Precision law (D6):** benchmark gate on every engine merge; informational mode until FP < 5% is measured on manually-adjudicated comments, not assumed and not inferred from thumbs alone.
6. **Restraint law (D16):** we never propose a change we can't defend as *desirable* to a senior engineer on that team; "technically a duplicate" is not sufficient grounds to touch someone's code.
7. **Invisibility law:** our failures never block customer workflows — checks conclude neutral on internal errors; jobs are idempotent; retries are bounded.
8. **Platform integrity:** every webhook signature verified before processing; installation tokens short-lived, never logged, never persisted beyond their TTL; every external write recorded in `audit_log` before it happens.
9. **Offboarding:** uninstall or deletion request purges repo-derived data on a stated schedule, and the purge path is tested like a feature, because it is one.
10. **Secrets:** env-only, never committed; rotation runbook from Phase 2.
11. **Dependencies:** pinned lockfiles; `pip-audit`/`npm audit` in CI; no new dependency without a one-line justification in the PR.

---

## 8. Operating instructions for Claude Code

Maintain these in `CLAUDE.md`; treat them as standing orders.

- **Session start:** read `docs/PLAN.md` + `CLAUDE.md`; state which phase and action point you're advancing; work the plan in order unless the owner redirects.
- **Commercial bar:** every user-visible surface ships finished — designed empty/loading/error states, humanized copy, mobile-checked, no placeholders. If a screen isn't good enough to screenshot in marketing, it isn't done.
- **Definition of done per task:** code + tests + docs + telemetry + (if user-visible) copy review flagged for the owner.
- **Engine discipline:** any change to detection logic runs `make bench` and reports the delta in the PR description; holdout is sacred. Before any release that changes what customers see, run the repo-level eval too — the pair benchmark is the merge gate, the repo eval is the ship gate.
- **Small steps:** PRs < 400 lines where possible; conventional commits; one concern per PR.
- **Stop and ask before:** changing pricing/plans, changing data retention, widening GitHub permission scopes, anything touching `GitWriter` or the sandbox policy, publishing any public copy, adding a paid third-party service.
- **Cost consciousness:** every LLM/API call is budgeted, cached (content-hash), and visible on the cost dashboard; report per-feature unit economics when adding model calls.
- **Prefer boring; delete aggressively.** No speculative abstractions, no Kubernetes, no microservices, no rewrites. When a library does the job, use it.
- **Honesty in artifacts (D17):** every displayed number names its computation; estimates are labeled and ranged (AI-share); comparison pages factual; the security page matches the schema exactly. If you cannot recompute a number in front of a skeptical customer, don't display it.
- **Keep the record:** update ADRs, `CHANGELOG.md`, and runbooks in the same PR as the change they describe.

---

## 9. Instrumentation & success metrics

- **Funnel:** audits run → email captures → app installs → activated repos (≥1 completed scan) → trials → paid. Track weekly.
- **Product health:** ratchet FP rate (manual adjudication, thumbs as supplement), remediation PR merge rate **split by close reason** (wrong / unwanted / not-now), **total lines of code deleted per customer** (the headline value metric — surface it on the dashboard and in digests), scan latency p50/p95, unit cost per scan and per remediation.
- **Guardrail metrics — track these beside lines-deleted, always.** A headline metric of "lines removed" rewards exactly the behavior D16 forbids: consolidating things that should have stayed apart. So we also watch **reverts of our PRs within 30 days**, **suggestions dismissed as "intentional duplication"**, and **abstraction churn** (a unified function that grows parameters or branches after our merge — the strongest available evidence that we created the wrong abstraction). If lines-deleted climbs while these climb too, we are destroying value and reporting it as success.
- **Business:** MRR, conversion audit→paid, logo churn, credit consumption vs. plan.
- **Trust:** incidents involving customer code (target: zero, forever), check-blocked-merge complaints (target: zero while informational).

---

## 10. Risk register (watch actively)

| Risk | Mitigation |
|---|---|
| **Teams don't want their duplicates consolidated** — correct findings, unwanted fixes. The category-defining risk, and invisible to the benchmark | D16 exclusion rules; measure "unwanted" separately from "wrong" in PR close reasons; validate with design partners in Phase 1 on raw output, before building the machinery. **If this is where we're wrong, prevention (the ratchet) is the product and remediation is a feature — pivot rather than push** |
| **Benchmark precision ≫ production precision** (class imbalance) | Repo-level eval as the ship gate (D12); never quote pair-benchmark numbers externally |
| Sonar/GitClear deepen into AI-debt | Out-execute on **remediation** (they measure/gate; we fix) and on PLG for 5–100-dev teams their sales motions ignore |
| False-positive trust collapse | D6 + D12; informational-first; manual adjudication of every comment at low volume; discard-on-uncertainty |
| Call-site resolution gaps break customer builds | Conservative resolver; unresolved refs counted not guessed; suggestion-only when scope isn't fully resolved; sandbox test gate |
| AI-share estimate is visibly wrong to the customer | Range + disclosed method + floor framing (D17); never the scorecard headline |
| Runway spent before first revenue | Phases 4/5 swappable; sell prevention if remediation runs long (§6 note 2) |
| LLM cost spikes | Content-hash caching, candidate budgets, model tiering in config, per-plan quotas |
| Malicious repo attacks our pipeline | D8 sandbox + D11 injection law + least-privilege D9 |
| Solo-founder bus factor | Managed services (D14), rehearsed runbooks, boring stack (D2) |
| Name/trademark conflict | "Reweave" is a codename; clearance search before launch; name lives in config |
| GitHub platform/API changes | `GitWriter` + webhook layer isolate the dependency; Marketplace terms reviewed at listing time |

---

## 11. Falsifiable bets and pivot triggers

This plan rests on four assumptions that could each be wrong. Failsafes elsewhere in this document protect against *technical* failure; these protect against *building the wrong thing well*. Write the decision down now, while it's cheap and unemotional — the whole purpose is to pre-commit before sunk cost makes the call for us. Review them at every phase gate.

| # | The bet | How we'd know it's wrong | What we do about it |
|---|---|---|---|
| B1 | **Semantic duplication is common enough to matter.** | Repo-level eval and design-partner scans surface only a handful of real clusters per 100k LOC, and partners shrug at them. | The detector is fine but the problem is small. Broaden the debt definition (dead code, drift, comprehension mapping — Phase 6 items move forward) or stop. |
| B2 | **Teams want duplicates consolidated.** | Consolidation PRs are correct but closed as unwanted; partners say "we know, that's deliberate" more than "great catch." | Prevention is the product. Ship the ratchet + dashboard as the paid core; demote remediation to opt-in. This is a pivot, not a failure — the ratchet is defensible on its own. |
| B3 | **This is worth ~$25/dev/month.** | Design partners engage happily but won't convert; the free audit converts below ~2% to install. | Reprice or re-target before adding features. Cheaper self-serve, or move upmarket where a compliance/policy story carries the price. Do not respond by building more. |
| B4 | **A solo founder + agent can hold the quality bar.** | Trust incidents, gates repeatedly slipping, or gate-lowering to hit dates. | Cut scope hard: one language, no remediation, no Marketplace. Finished-and-narrow beats broad-and-shaky (§0). |

**Standing rule:** if a gate is missed twice in a row, the response is to cut scope, never to lower the gate. The gates *are* the product.

---

*End of plan. Build it like someone's about to pay for it — because that's the whole point.*
