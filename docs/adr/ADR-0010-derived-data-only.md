# ADR-0010: Store derived data, not source code

- **Status:** Accepted
- **Date:** 2026-08-13
- **Plan reference:** `docs/PLAN.md` §3 (D10)

## Context

"Where does our code live?" is the first sales objection. A short, honest answer wins deals and
shortens the SOC 2 path.

## Decision

Clones are shallow, ephemeral, and deleted at job end. We persist fingerprints, embeddings,
metrics, findings, and minimal evidence snippets — the specific matched regions, size-capped,
encrypted at rest, deletable on request. Code content is never written to logs.

Uninstall purges repo-derived rows within 30 days; deletion on request is immediate.

## Consequences — state these precisely, because a reviewer will check

We *do* retain small verbatim excerpts, and embeddings are derived from code but are **not** a
privacy guarantee: embedding-inversion research can partially reconstruct content from vectors.

The defensible claim is: *we do not keep your repository; we keep capped encrypted excerpts of the
matched regions plus derived vectors and metrics, and we delete all of it on request.*

Do not ship the line "we keep math about it, not the code." It overstates by exactly the amount
that destroys trust when someone reads the schema.

---

*Superseding this ADR requires a new ADR that references it. Do not edit an accepted decision in
place — the record of what we believed and when is the point.*
