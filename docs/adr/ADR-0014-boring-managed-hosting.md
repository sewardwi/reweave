# ADR-0014: Boring managed hosting

- **Status:** Accepted
- **Date:** 2026-08-13
- **Plan reference:** `docs/PLAN.md` §3 (D14)

## Context

Solo operations. Every piece of infrastructure we run ourselves is infrastructure that can wake us
up.

## Decision

API and workers on Railway/Fly/Render. Postgres managed (Neon/RDS). Web on Vercel. Sentry for
errors. Plausible or PostHog for analytics.

**Kubernetes is explicitly banned in v1.**

## Consequences

- Higher unit hosting cost, lower operational surface. Correct trade at this stage.
- Vendor inventory is maintained for the SOC 2 runway.

---

*Superseding this ADR requires a new ADR that references it. Do not edit an accepted decision in
place — the record of what we believed and when is the point.*
