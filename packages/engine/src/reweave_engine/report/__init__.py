"""JSON and static HTML renderers for the audit report (Phase 1/2)."""

from reweave_engine.report.html import render_html
from reweave_engine.report.model import (
    SCHEMA_VERSION,
    AuditReport,
    ClusterReport,
    Coverage,
    Evidence,
    UnitRef,
)

__all__ = [
    "SCHEMA_VERSION",
    "AuditReport",
    "ClusterReport",
    "Coverage",
    "Evidence",
    "UnitRef",
    "render_html",
]
