# ADR-0002: Python engine, Django API

- **Status:** Accepted
- **Date:** 2026-08-13
- **Plan reference:** `docs/PLAN.md` §3 (D2)

## Context

The owner operates this alone. Boring technology he can debug at 2 a.m. beats fashionable
technology he cannot. The parsing and ML ecosystem we depend on — tree-sitter bindings, numpy,
model clients — is Python-native.

## Decision

The analysis engine is a pure-Python package. The API is Django with DRF.

## Alternatives considered

*FastAPI* — lighter, but auth, admin, ORM, and migrations become assembly work. Django's batteries
directly shrink the solo surface area.

*Full TypeScript backend* — would split the engine from its ecosystem. Rejected.

## Consequences

- Two languages in the repo (Python, TypeScript), with a clean seam at the HTTP boundary.
- Django's admin gives us an operations console for free, which matters at 3 a.m.

## Revisit when

p95 API latency or team size demands it.

---

*Superseding this ADR requires a new ADR that references it. Do not edit an accepted decision in
place — the record of what we believed and when is the point.*
