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

### Changed
- Corpus grown to v1: **151 pairs** (110 train / 41 holdout), of which 41 are mined from
  date-fns, axios, httpx, and click and stored as pointers. All six D16 exclusion rules are now
  exercised; labels split 81 duplicate / 70 not-duplicate across Python, TypeScript, and JavaScript.
- `mine_candidates.py` gained diversity caps and test-file exclusion. The first run returned 23 of
  60 candidates from a single date-fns locale file and 26 of 60 from one httpx module; axios and
  click candidates were almost entirely test files. Candidates are now capped per chunk, per file,
  and per file-pair, and drawn round-robin from similarity bands.
- Benchmark gates recalibrated to 0.55 / 0.38 against corpus v1, with `corpus_version` recorded in
  `gates.toml`. See ADR-0018 — the detector did not change, the measuring instrument did.

### Measured
- Baseline `token_overlap_v1`, corpus v0 train split (23 pairs): precision 0.667, recall 0.571.
- Baseline `token_overlap_v1`, **corpus v1 train split (110 pairs): precision 0.585, recall
  0.414**, same detector, unchanged. The larger corpus with real mined code is the more truthful
  measurement; the drop is concentrated in recall, on semantic reimplementations sitting at
  28–47% structural similarity that no lexical method can reach.
- Holdout deliberately not scored. It stays sealed until the Phase 1 gate.
