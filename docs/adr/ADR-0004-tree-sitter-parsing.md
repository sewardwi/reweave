# ADR-0004: tree-sitter for parsing

- **Status:** Accepted
- **Date:** 2026-08-13
- **Plan reference:** `docs/PLAN.md` §3 (D4)

## Context

We need one uniform, fast parsing API across languages, and adding a language later should be
additive rather than an architecture change.

## Decision

tree-sitter for all parsing. Start with TypeScript/JavaScript and Python, because that is where AI
code generation concentrates.

## Consequences

- Incremental parsing gives us cheap re-indexing on push (Phase 3).
- Grammar quality varies by language; each new language needs its own extraction rules and its own
  corpus coverage before it ships.

## Status note

Phase 0 ships a regex-based extractor in `benchmarks/mine_candidates.py` for *candidate generation
only*. It is not used for anything a customer sees and is replaced in Phase 1.

---

*Superseding this ADR requires a new ADR that references it. Do not edit an accepted decision in
place — the record of what we believed and when is the point.*
