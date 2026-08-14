# Changelog

Notable changes, newest first. Updated in the same PR as the change it describes.

## Unreleased — Phase 0 (foundations)

### Added
- Monorepo scaffold per `docs/PLAN.md` §5: engine, remediation, shared, API, workers, web,
  benchmarks, sandbox, infra, ops.
- `packages/shared` finding schema that enforces two product laws as model validators: an
  `UNCERTAIN` verdict cannot be surfaced (D6), and consolidation cannot be recommended while a
  D16 exclusion applies.
- `packages/engine` baseline detector (`token_overlap_v1`) and the `PairDetector` protocol the
  benchmark scores everything against.
- Benchmark harness: corpus schema (pointer + inline sources), pair benchmark with train/holdout
  split discipline, repo-level eval scaffold, gates ratchet, corpus integrity tests, and mining
  and labeling CLIs.
- Corpus v0: 31 hand-authored labeled pairs including semantic reimplementations, hard negatives,
  and duplicates that should be left alone.
- Toolchain: uv + ruff + pyright strict + pytest; pnpm + eslint + prettier + `tsc --strict`;
  pre-commit with conventional commits; CI running lint, typecheck, tests, and the bench gate.
- Docker Compose dev stack: Postgres/pgvector, Redis, Django API, Celery worker.
- `CLAUDE.md`, `SECURITY.md`, and ADR-0001..0017 seeding decisions D1–D17.

### Measured
- Baseline `token_overlap_v1` on corpus v0 train split: **precision 0.667, recall 0.571**.
  All 5 false negatives were semantic reimplementations (20–38% structural similarity); all 4
  false positives were near-identical code with divergent behavior (85–100%). Gates set at
  0.65 / 0.55 as a regression ratchet.
