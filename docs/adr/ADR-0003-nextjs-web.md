# ADR-0003: Next.js + TypeScript for web

- **Status:** Accepted
- **Date:** 2026-08-13
- **Plan reference:** `docs/PLAN.md` §3 (D3)

## Context

The dashboard's polish is part of the sales pitch: the buyer is an engineering lead who will judge
our competence by our UI before they judge our detection.

## Decision

Next.js with strict TypeScript for both the marketing site and the product dashboard, deployed to
Vercel.

## Consequences

- Two deploy targets (Vercel for web, a container host for API/workers). Accepted cost.
- We get production-grade charts and components from the React ecosystem rather than building them.

## Notes

Node 20 was named in the original plan; it reached end-of-life in April 2026, so we pin Node 24 LTS
(`.nvmrc`). Next 16 is used because `eslint-config-next` 15 depends on a patch shim that breaks on
current Node.

---

*Superseding this ADR requires a new ADR that references it. Do not edit an accepted decision in
place — the record of what we believed and when is the point.*
