# ADR-0005: Three-stage duplicate detection

- **Status:** Accepted
- **Date:** 2026-08-13
- **Plan reference:** `docs/PLAN.md` §3 (D5)

## Context

Comparing every pair of functions in a repository with an LLM is quadratic and financially
impossible. Deciding on embeddings alone is too noisy to meet our precision law.

## Decision

Three stages:

1. Normalize ASTs (strip identifiers and literals), fingerprint, and generate candidate pairs
   cheaply via MinHash/LSH under a hard candidate budget.
2. Rerank candidates with code embeddings, cached by content hash.
3. Send only the shortlist to an LLM adjudicator with a strict rubric — same observable behavior?
   consolidation feasible? consolidation advisable? — returning a verdict plus rationale.

## Alternatives considered

*Pure embedding decisions* — too noisy; fails ADR-0006.
*LLM over all pairs* — cost explodes quadratically.

## Consequences

- LLM spend is confined to a shortlist, which is what makes the unit economics work.
- Every stage is independently cacheable and independently testable.
- Thresholds live in config, never hardcoded.

## Baseline

Phase 0 measured a lexical baseline (`token_overlap_v1`) at precision 0.667 / recall 0.571 on the
corpus v0 train split. **This pipeline must beat that measurably or it is not earning its cost.**
Its five false negatives were all semantic reimplementations (structural similarity 20–38%) and its
four false positives were all near-identical code with divergent behavior (85–100%) — precisely the
two failure modes stages 2 and 3 exist to fix.

---

*Superseding this ADR requires a new ADR that references it. Do not edit an accepted decision in
place — the record of what we believed and when is the point.*
