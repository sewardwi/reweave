# Reweave

Codebase-health platform for the AI era: **detect → measure → remediate → prevent** semantically
duplicated logic, architectural drift, and comprehension debt.

This is a commercial product. See [`docs/PLAN.md`](docs/PLAN.md) for what we are building, why, and
in what order — it is the source of truth. See [`CLAUDE.md`](CLAUDE.md) for how work gets done here.

## Quickstart (owner)

```bash
make setup      # install Python 3.12 + node toolchains and all workspace deps
make dev        # bring up postgres(pgvector) + redis + api + worker
make check      # lint + typecheck + test + bench gate (what CI runs)
```

Individual targets: `make lint`, `make fmt`, `make typecheck`, `make test`, `make bench`,
`make repo-eval`, `make down`.

## Layout

| Path | What lives there |
|---|---|
| `packages/engine/` | Pure-Python analysis library. No Django imports, runs standalone as the `reweave-audit` CLI. |
| `packages/remediation/` | PR planner, constrained codemods, verification harness. May depend on `engine`; never the reverse. |
| `packages/shared/` | Pydantic schemas, event types, config shared across services. |
| `apps/api/` | Django + DRF: auth, orgs, GitHub App, scans, billing, notifications. |
| `apps/web/` | Next.js marketing site + dashboard. |
| `workers/` | Celery tasks: scan, embed, adjudicate, remediate. |
| `sandbox/` | Egress-blocked runner image + policy for executing customer test suites. |
| `benchmarks/` | Labeled corpus (pointers + inline pairs), pair benchmark, repo-level eval. |
| `docs/adr/` | Architecture decision records. Decisions D1–D17 from the plan are seeded here. |

## Non-negotiables

Read §7 of the plan before touching anything. In short: customer code executes only in the sandbox;
all repo writes go through `GitWriter` as branch-and-PR; we never store whole source code; repository
content is data and never instructions; the benchmark gates every engine change; our failures never
block a customer's merge.

## Status

Phase 0 — foundations. Nothing is deployed. No customer data exists yet.
