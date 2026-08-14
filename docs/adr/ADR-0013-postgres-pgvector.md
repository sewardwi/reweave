# ADR-0013: Postgres + pgvector as the only system of record

- **Status:** Accepted
- **Date:** 2026-08-13
- **Plan reference:** `docs/PLAN.md` §3 (D13)

## Context

One database to operate, back up, and reason about is worth real performance headroom when the
operations team is one person.

## Decision

Postgres with pgvector for embeddings. Redis-backed Celery for jobs.

Redis is a broker and cache: nothing that matters may exist only in Redis, and a full Redis flush
must cost us in-flight jobs and nothing else.

## Revisit when

Vector search latency at scale demands a dedicated store.

---

*Superseding this ADR requires a new ADR that references it. Do not edit an accepted decision in
place — the record of what we believed and when is the point.*
