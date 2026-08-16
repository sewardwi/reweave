# ADR-0018: Corpus v1, and why the benchmark gates moved down

- **Status:** Accepted
- **Date:** 2026-08-16
- **Relates to:** [ADR-0012](ADR-0012-eval-first-engineering.md) (eval-first), [ADR-0005](ADR-0005-three-stage-detection.md) (baseline figures)

## Context

`CLAUDE.md` says benchmark gates are a ratchet: they rise, never fall, and lowering one requires
an ADR explaining why the gate was wrong in the first place. This is that ADR, written the first
time the rule bound.

Corpus v0 was 31 pairs, 23 of them in the train split. Gates were set at precision 0.65 / recall
0.55, just under the baseline's measured 0.667 / 0.571.

Corpus v1 grows this to **151 pairs** (110 train, 41 holdout) by adding:

- **41 pairs mined from four permissively-licensed repositories** — date-fns, axios, httpx, and
  click — stored as pointers per ADR-0012, each read in full before being labeled.
- **110 authored pairs**, weighted toward semantic reimplementations and hard negatives.

Re-measured on the larger train split, the same unchanged detector scores **precision 0.585,
recall 0.414**.

## Decision

Set the gates to `min_precision = 0.55`, `min_recall = 0.38`, and record the corpus version they
were calibrated against.

## Why this is not the failure mode the ratchet rule exists to prevent

The rule protects against a specific dishonesty: an engine change makes the number worse, and
instead of fixing the engine you move the goalposts. That is not what happened here. **The
detector did not change at all** — not one line. The measuring instrument changed.

The old gate was wrong because it was calibrated against a corpus too small and too easy to
estimate anything. Twenty-three pairs puts roughly a ±10 point confidence interval on precision,
and those pairs were entirely code we wrote ourselves, which is invariably cleaner and more
regular than real code. The mined pairs from real repositories are harder, and the baseline's
score against them is the more truthful number. A gate calibrated on a bad estimate is a bad
gate, and keeping it would have meant a permanently red build that everyone learns to ignore —
which is the actual end of eval discipline, faster than any single lowered threshold.

**Consequence, and the real lesson: a gate value is meaningless without a corpus version.** Gates
are a regression ratchet *on a fixed corpus*. When the corpus changes, prior numbers are not
comparable and the gate must be recalibrated in the same commit, with the recalibration
documented. `gates.toml` now records `corpus_version` for exactly this reason. Future corpus
growth follows the same procedure: grow, re-measure the unchanged detector, recalibrate, write it
down.

## What the new numbers say about the product

The baseline degraded most on recall (0.571 → 0.414), and the misclassifications say why:
semantic reimplementations at 28–47% structural similarity that no lexical method can reach —
`deepClone` written with `map` versus an index loop, `once` with a boolean flag versus a cache
sentinel, chunked file hashing with `while`-break versus `iter`-sentinel.

This *strengthens* the case for D5's embedding and adjudication stages rather than weakening it.
It also sharpens the Phase 1 bar: reaching precision ≥ 0.90 at recall ≥ 0.50 now means clearing a
baseline of 0.585 / 0.414 on a corpus with real mined code in it, not 0.667 / 0.571 on
thirty-one hand-written pairs.

## Note on the holdout

The holdout was **not** scored while making this change. There is nothing to learn from running
the Phase 0 baseline against it, and every unnecessary look is a small withdrawal from the only
unbiased estimate we will have when Phase 1 lands. It stays sealed until the Phase 1 gate.

## Corrections to earlier records

ADR-0005 cites the baseline as precision 0.667 / recall 0.571. Those figures were correct for
corpus v0 and are superseded here. ADRs are not edited in place, so this note is the correction.

---

*Superseding this ADR requires a new ADR that references it. Do not edit an accepted decision in
place — the record of what we believed and when is the point.*
