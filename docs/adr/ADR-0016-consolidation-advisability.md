# ADR-0016: Not every duplicate should be consolidated

- **Status:** Accepted
- **Date:** 2026-08-13
- **Plan reference:** `docs/PLAN.md` §3 (D16)

## Context

This is the decision most likely to sink the product, and it is invisible to the benchmark.

ADR-0006 protects us from *"these aren't the same."* Nothing protected us from *"they are the same,
and they should stay that way."* Duplication is frequently a deliberate, correct engineering
choice — the wrong abstraction costs more than the duplication it removes. A senior reviewer who
receives a PR coupling two modules that were kept apart on purpose will uninstall us and tell their
colleagues why.

Our stated value metric is lines deleted, which is precisely the incentive that produces
over-abstraction. This ADR is the counterweight.

## Decision

The adjudicator returns a **consolidation recommendation** distinct from its duplicate verdict. We
never surface a remediation — though we may still count the pair in metrics — when any of these
hold:

- **cross_boundary** — opposite sides of a deliberate boundary (services, packages, bounded
  contexts, CODEOWNERS) where consolidation creates a new cross-boundary dependency.
- **generated_or_vendored** — generated code, vendored dependencies, migrations, fixtures, test
  scaffolding.
- **diverged_history** — both sides edited independently in the last 90 days; strong evidence they
  are evolving apart on purpose.
- **requires_flag_param** — unifying needs a parameter, flag, or branch to reconcile behavioral
  differences. The wrong abstraction, mechanized.
- **below_size_floor** — the shared logic is small and stable enough that indirection costs more
  than it saves (default ~10 lines, config-driven).
- **unresolved_call_sites** — we could not fully resolve references, so rewriting risks a silent
  break.

## Consequences

- `ConsolidationAdvice` requires naming the exclusion rule when declining, and a model validator
  forbids recommending consolidation while an exclusion applies.
- The remediation exit gate is *merged without human correction*, not *opened*.
- Closed-unmerged PRs are categorized as wrong / unwanted / not-now, because those three failures
  need different fixes and an undifferentiated merge rate hides which one is hurting.
- Design-partner feedback on rejected suggestions is the primary tuning signal for these rules.

---

*Superseding this ADR requires a new ADR that references it. Do not edit an accepted decision in
place — the record of what we believed and when is the point.*
