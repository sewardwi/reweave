# ADR-0006: Precision over recall, as product law

- **Status:** Accepted
- **Date:** 2026-08-13
- **Plan reference:** `docs/PLAN.md` §3 (D6)

## Context

False positives are the documented graveyard of this category. Static analysis tools cite 30–35%
false-positive rates as the top adoption restraint, and noise is the top complaint about AI code
reviewers in the adjacent market. A missed duplicate costs us nothing today. A wrong comment costs
us the customer.

## Decision

Precision beats recall in every ambiguous case.

Mechanisms:

- Adjudicator disagreement or low confidence → discard the pair. Not "flag with low confidence."
- The ratchet ships informational-only until a measured false-positive rate under 5%.
- Engine changes are gated by the benchmark (ADR-0012).

## Consequences

- `Verdict.UNCERTAIN` exists in the schema and `Finding.is_surfaceable` returns `False` for it, so
  the law is enforced by a validator rather than by discipline.
- We will ship with visibly incomplete recall. That is the intended trade.

---

*Superseding this ADR requires a new ADR that references it. Do not edit an accepted decision in
place — the record of what we believed and when is the point.*
