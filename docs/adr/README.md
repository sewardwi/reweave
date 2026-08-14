# Architecture decision records

Decisions D1–D17 from `docs/PLAN.md` §3, seeded in Phase 0.

| ADR | Decision |
|---|---|
| [ADR-0001](ADR-0001-monorepo.md) | Monorepo for everything |
| [ADR-0002](ADR-0002-python-engine-django-api.md) | Python engine, Django API |
| [ADR-0003](ADR-0003-nextjs-web.md) | Next.js + TypeScript for web |
| [ADR-0004](ADR-0004-tree-sitter-parsing.md) | tree-sitter for parsing |
| [ADR-0005](ADR-0005-three-stage-detection.md) | Three-stage duplicate detection |
| [ADR-0006](ADR-0006-precision-over-recall.md) | Precision over recall, as product law |
| [ADR-0007](ADR-0007-read-only-core.md) | Read-only core; PRs are the only write path |
| [ADR-0008](ADR-0008-sandboxed-verification.md) | Test-verified remediation in an egress-blocked sandbox |
| [ADR-0009](ADR-0009-github-app-least-privilege.md) | GitHub App with least-privilege scopes |
| [ADR-0010](ADR-0010-derived-data-only.md) | Store derived data, not source code |
| [ADR-0011](ADR-0011-anthropic-metered.md) | Anthropic API as a metered cost center |
| [ADR-0012](ADR-0012-eval-first-engineering.md) | Eval-first engineering, at two levels |
| [ADR-0013](ADR-0013-postgres-pgvector.md) | Postgres + pgvector as the only system of record |
| [ADR-0014](ADR-0014-boring-managed-hosting.md) | Boring managed hosting |
| [ADR-0015](ADR-0015-billing-is-architecture.md) | Billing is architecture, not an afterthought |
| [ADR-0016](ADR-0016-consolidation-advisability.md) | Not every duplicate should be consolidated |
| [ADR-0017](ADR-0017-named-measurements.md) | Every number we display names its computation |

To change a decision: write a new ADR with context, options, trade-offs, and
consequences, reference the one it supersedes, and stop for review. Never deviate silently.
