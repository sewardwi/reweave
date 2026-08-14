# Security & data handling

**Status: pre-production.** Reweave is not yet deployed and processes no customer data. This document
states the commitments the system is being built to meet. Every claim here must match the actual
schema and code — when they diverge, this file is wrong and gets fixed in the same PR as the change.
The public security page must never claim more than this file.

## Reporting a vulnerability

Email **security@reweave.dev** (placeholder — configure before any public exposure). Include steps to
reproduce and the affected component. We aim to acknowledge within 2 business days.

Please do not open a public issue for a security report, and please do not run automated scans
against production infrastructure without contacting us first.

## What we access

The Reweave GitHub App requests only:

| Scope | Why |
|---|---|
| `contents: read` | Shallow-clone repositories to analyze them |
| `pull_requests: write` | Post a single informational comment; open consolidation PRs |
| `checks: write` | Report a neutral check with findings |
| `metadata: read` | Required by GitHub for all apps |

We never request write access to repository contents outside the pull-request flow. We do not use
user OAuth tokens. Widening these scopes requires a written ADR and customer notice.

## What we store

We do **not** retain your repository. Clones are shallow, written to ephemeral storage, and deleted
when the job ends.

We do retain, per analyzed repository:

- **Derived structure** — content hashes, normalized-AST fingerprints, symbol references.
- **Embeddings** — numeric vectors derived from code, keyed by content hash.
- **Metrics and findings** — scores, cluster membership, verdicts, rationale.
- **Evidence snippets** — small verbatim excerpts of the *specific matched regions* only, size-capped
  and encrypted at rest. These exist so a finding can be reviewed without re-cloning.

**Stated precisely, because it matters:** embeddings are derived data, not an anonymization
guarantee — published research shows text can be partially reconstructed from embedding vectors. Our
claim is not "we hold nothing derived from your code." It is: we do not keep your repository, we keep
capped encrypted excerpts of matched regions plus derived vectors and metrics, and we can delete all
of it on request.

Source code is never written to application logs, error reports, or analytics.

## Executing your code

Running a customer's test suite is remote code execution by design. It happens only inside an
isolated container with:

- no network egress,
- no secrets or credentials mounted,
- CPU, memory, and wall-clock caps,
- a workspace destroyed at job end.

## Writes to your repository

All repository writes flow through a single `GitWriter` module and are structurally limited to:
create a branch, commit to it, open a pull request. Reweave never pushes to a default or protected
branch, never force-pushes, and never merges. Auto-merge is not a feature that can be enabled.

Every external write is recorded in an append-only audit log before it is performed.

## Model providers

We send code excerpts to the Anthropic API for duplicate adjudication and PR generation. Repository
content is always passed as delimited data with instructions to ignore any directives it contains,
and all model output is validated against a schema before use. A malicious repository must not be
able to influence our behavior.

## Deletion

Uninstalling the GitHub App stops all scanning immediately and purges repo-derived rows (evidence
snippets, embeddings, findings) within 30 days. Deletion on request is immediate. The purge path is
covered by tests.

## Incidents

Any incident involving customer code is disclosed to affected customers directly. Our target for such
incidents is zero, permanently.
