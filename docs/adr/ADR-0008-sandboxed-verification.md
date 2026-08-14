# ADR-0008: Test-verified remediation in an egress-blocked sandbox

- **Status:** Accepted
- **Date:** 2026-08-13
- **Plan reference:** `docs/PLAN.md` §3 (D8)

## Context

Running a customer's test suite is remote code execution by design. An auto-refactorer that breaks
builds is dead on arrival, and the sandbox is simultaneously our correctness mechanism and our
security story.

## Decision

Customer code executes only inside an isolated container: no network egress, no secrets mounted,
CPU/memory/time caps, workspace destroyed at job end.

A consolidation PR opens only if the suite passes both before and after the change and the diff
touches only planned files. If the target code lacks tests: generate characterization tests first,
or downgrade to a suggestion with no PR.

## Consequences

- Repositories without runnable tests get suggestions, not PRs. This will cover a meaningful share
  of the market, and that is acceptable.
- A passing suite is weaker evidence than it feels: it proves we did not break what was covered.
  Coverage of the touched spans is part of the go/no-go decision, not a footnote.

---

*Superseding this ADR requires a new ADR that references it. Do not edit an accepted decision in
place — the record of what we believed and when is the point.*
