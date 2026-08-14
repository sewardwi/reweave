"""Celery workers: scan, embed, adjudicate, remediate.

Every task must be idempotent and retry-safe. The invisibility law (PLAN.md §7) means a failed
job degrades to a neutral check, never to a blocked merge — so tasks fail loudly into our
telemetry and quietly toward the customer.
"""

from reweave_workers.app import app

__all__ = ["app"]
