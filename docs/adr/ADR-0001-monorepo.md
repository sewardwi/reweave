# ADR-0001: Monorepo for everything

- **Status:** Accepted
- **Date:** 2026-08-13
- **Plan reference:** `docs/PLAN.md` §3 (D1)

## Context

A solo founder working with an AI agent needs total visibility and the ability to make atomic
cross-cutting changes. Split repositories introduce version skew between the engine, the API, and
the web app, and every skew event costs a debugging session we cannot afford.

## Decision

One repository holds the engine, API, workers, web, benchmarks, sandbox, and infra.

## Alternatives considered

*Polyrepo* — better isolation for independent release cadences, at the cost of coordinated
releases and cross-cutting refactors. Wrong trade for a one-person team.

## Consequences

- CI runs everything on every PR. Acceptable while the suite is fast; revisit if it stops being.
- The engine must stay importable standalone, which is enforced by a layout rule rather than by
  repository boundaries: `packages/engine` never imports from `apps/`.

## Revisit when

The engine needs an independent open-source release.

---

*Superseding this ADR requires a new ADR that references it. Do not edit an accepted decision in
place — the record of what we believed and when is the point.*
