# ADR-0009: GitHub App with least-privilege scopes

- **Status:** Accepted
- **Date:** 2026-08-13
- **Plan reference:** `docs/PLAN.md` §3 (D9)

## Context

The permissions screen is a sales document. A security reviewer should be able to approve it
without scheduling a meeting.

## Decision

A GitHub App requesting exactly: `contents: read`, `pull_requests: write`, `checks: write`,
`metadata: read`. Nothing more.

## Alternatives considered

*User OAuth tokens* — over-scoped and tied to individuals who leave. Rejected.

## Consequences

- Per-repo installs, revocable by the customer, and eligible for Marketplace distribution.
- Widening scopes requires a new ADR and customer notice.
- Permissions are re-audited against this ADR before Marketplace submission.

---

*Superseding this ADR requires a new ADR that references it. Do not edit an accepted decision in
place — the record of what we believed and when is the point.*
