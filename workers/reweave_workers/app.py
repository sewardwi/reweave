"""Celery application.

Queues are separated by cost and latency profile from the start: a slow, expensive adjudication
job must never sit in front of a PR check that a developer is waiting on.
"""

from __future__ import annotations

import os

from celery import Celery

app = Celery(
    "reweave",
    broker=os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
)

app.conf.update(
    task_acks_late=True,  # redeliver if a worker dies mid-job; tasks are idempotent
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,  # long jobs; don't let one worker hoard the queue
    task_time_limit=30 * 60,
    task_soft_time_limit=25 * 60,
    task_default_queue="default",
    task_routes={
        "reweave.scan.*": {"queue": "scan"},
        "reweave.check.*": {"queue": "check"},  # latency-sensitive: a human is waiting
        "reweave.remediate.*": {"queue": "remediate"},
    },
)


@app.task(name="reweave.health.ping")
def ping() -> str:
    """Smoke test that the broker round-trips. Used by ``make dev`` verification."""
    return "pong"
