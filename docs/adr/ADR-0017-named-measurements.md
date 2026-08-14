# ADR-0017: Every number we display names its computation

- **Status:** Accepted
- **Date:** 2026-08-13
- **Plan reference:** `docs/PLAN.md` §3 (D17)

## Context

Every displayed number is a claim we may have to defend to a skeptical staff engineer in a PR
thread. A number we can recompute in front of them survives that; an invented one does not.

## Decision

User-facing similarity is reported as named, deterministic measures — normalized-AST structural
similarity and raw textual overlap — not as a single blended score and not as a confidence
probability. Semantic verdicts stay categorical. Estimates are labeled as estimates and shown as
ranges.

A ratchet comment reads *"91% structural similarity, 46% textual overlap"*, not *"94% match."*

## Consequences

- `PairMetrics` carries each measurement separately with its method tagged, and deliberately
  exposes no combined score — the UI cannot display one because it cannot construct one.
- Composite indices are permitted where they are honest about being composites: the Debt Score and
  letter grade are deliberate roll-ups, so their formula is published and versioned, and the
  dashboard always allows drilling from the score to the findings beneath it. What is banned is
  blending distinct measurements into one unexplained number at the point of a specific claim about
  specific code.
- The AI-share estimate is shown as a range with its method disclosed and a floor framing, and is
  never the scorecard headline: trailer-based detection misses most Copilot- and Cursor-authored
  code, and it is the first figure a visitor checks against their own knowledge of their repo.

---

*Superseding this ADR requires a new ADR that references it. Do not edit an accepted decision in
place — the record of what we believed and when is the point.*
