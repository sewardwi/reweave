# ADR-0007: Read-only core; PRs are the only write path

- **Status:** Accepted
- **Date:** 2026-08-13
- **Plan reference:** `docs/PLAN.md` §3 (D7)

## Context

Trust is the product. The blast radius of a bug must be structurally bounded, not
policy-bounded — a customer's security reviewer should be able to see the bound in the code.

## Decision

The app never pushes to a protected or default branch, never force-pushes, never auto-merges. All
writes are: create branch → commit → open PR. A single `GitWriter` module owns every write
operation and refuses anything else.

## Consequences

- `apps/api/github/GitWriter` is the only module permitted to call the GitHub write API, and tests
  assert that no other code path does.
- Auto-merge is not a feature that can be enabled later without reopening this ADR.
- Every external write is recorded in `audit_log` before it is performed.

---

*Superseding this ADR requires a new ADR that references it. Do not edit an accepted decision in
place — the record of what we believed and when is the point.*
