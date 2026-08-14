# ADR-0012: Eval-first engineering, at two levels

- **Status:** Accepted
- **Date:** 2026-08-13
- **Plan reference:** `docs/PLAN.md` §3 (D12)

## Context

Detection quality is an ML product. Without measurement, "improvements" are vibes.

## Decision

Maintain a labeled benchmark corpus with a held-out split, and gate engine changes on it.

**Two levels, because one is not enough.** A curated pair corpus is roughly balanced; production is
not. A 300k-LOC repository holds on the order of 10⁹ candidate pairs of which perhaps a few hundred
are true duplicates — six-plus orders of magnitude of class imbalance. A detector at 0.95 precision
on balanced pairs can land under 0.30 in production, and production precision is what the customer
experiences.

- **Pair benchmark** (`run_bench.py`) — fast, hermetic, scores the **train** split, gates merges.
- **Repo-level eval** (`run_repo_eval.py`) — full scans of a fixed repo set with 100% hand-labeling
  of everything surfaced; reports precision@k and findings-per-KLOC; gates shipping.

**Split discipline.** A CI gate that scores the holdout on every PR *is* tuning on the holdout: you
iterate until it goes green and the number stops meaning anything. CI scores train. The holdout is
scored at phase gates, recorded, and not iterated against.

**Corpus storage.** Pointers (repo URL + commit SHA + span + label) for third-party code, never
vendored. Inline text only for pairs we authored. This keeps us clean on OSS licensing and matches
ADR-0010's discipline.

**Two labels per pair.** Detection (`same behavior?`) and advisability (`should they be merged?` —
ADR-0016). Labeling both while already reading the code is nearly free and impossible to
reconstruct later.

## Consequences

- Gates are a ratchet: they may rise, never fall. Lowering one requires an ADR.
- Corpus v0 is a seed of 31 pairs against a planned floor of 150; a strict-xfail test in
  `benchmarks/tests/test_corpus.py` will not let that gap be forgotten.

---

*Superseding this ADR requires a new ADR that references it. Do not edit an accepted decision in
place — the record of what we believed and when is the point.*
