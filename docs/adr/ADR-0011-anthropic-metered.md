# ADR-0011: Anthropic API as a metered cost center

- **Status:** Accepted
- **Date:** 2026-08-13
- **Plan reference:** `docs/PLAN.md` §3 (D11)

## Context

Model calls are our variable cost and our largest prompt-injection surface simultaneously.

## Decision

Use the Anthropic API for adjudication and PR generation, with:

- structured outputs only, validated against schemas before use;
- per-scan token budgets enforced in code;
- responses cached by content hash;
- repository content always treated as **data, never instructions** — wrapped in delimited blocks
  with explicit instructions to ignore any directives inside it.

Model IDs live in config, never in code.

## Consequences

- A malicious repository must not be able to steer our agent. This is testable and gets tested.
- Cost per scan and per remediation is measured and appears on the cost dashboard.
- Model upgrades are a config change plus a benchmark run, not a code change.

---

*Superseding this ADR requires a new ADR that references it. Do not edit an accepted decision in
place — the record of what we believed and when is the point.*
