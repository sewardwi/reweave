# ADR-0015: Billing is architecture, not an afterthought

- **Status:** Accepted
- **Date:** 2026-08-13
- **Plan reference:** `docs/PLAN.md` §3 (D15)

## Context

The goal is selling. Metering shapes the job system, and free-tier abuse limits must exist before
the free tier does.

## Decision

Plans, quotas, and usage metering are modeled in the schema from Phase 2, even though Stripe goes
live in Phase 5.

## Consequences

- Every job records a usage event whether or not anyone is billed for it yet.
- Quota enforcement is middleware, so turning billing on is a configuration change rather than a
  rewrite.
- Monetization does not depend on remediation: after Phase 3 we can sell prevention and measurement
  alone if the remediation engine runs long.

---

*Superseding this ADR requires a new ADR that references it. Do not edit an accepted decision in
place — the record of what we believed and when is the point.*
