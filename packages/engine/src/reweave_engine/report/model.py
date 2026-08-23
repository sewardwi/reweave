"""The audit report: what a scan produces, as data.

Rendered forms (JSON, HTML) are projections of this. Two rules shape it:

* **Every number names its computation (D17).** Similarity measurements carry their method
  string; the blast-radius roll-up carries its formula version. There is no field for a
  letter grade or a Debt Score — those are Phase 2 composites and inventing one here, before
  the formula is published, is exactly what D17 forbids.
* **Unavailable is not zero.** ``churn`` is ``None`` when git history could not be read, not
  ``0``. A report that shows "0 commits" for a repository it never managed to inspect is
  telling the reader something false.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

SCHEMA_VERSION = "reweave.audit/v1"


@dataclass(frozen=True, slots=True)
class UnitRef:
    """A code unit, located precisely enough to open in an editor."""

    path: str
    start_line: int
    end_line: int
    name: str
    language: str

    @property
    def location(self) -> str:
        return f"{self.path}:{self.start_line}"

    @property
    def line_count(self) -> int:
        return self.end_line - self.start_line + 1


@dataclass(frozen=True, slots=True)
class Evidence:
    """One adjudicated pair inside a cluster, with the measurements that produced it."""

    left: UnitRef
    right: UnitRef
    structural_percent: int
    structural_method: str
    textual_percent: int
    textual_method: str
    rationale: str


@dataclass(frozen=True, slots=True)
class ClusterReport:
    cluster_id: str
    units: list[UnitRef]
    removable_lines: int
    call_sites: int
    churn: int | None
    score: float
    score_method: str
    safely_remediable: bool
    blocked_reasons: list[str]
    evidence: list[Evidence]

    @property
    def unit_count(self) -> int:
        return len(self.units)


@dataclass(frozen=True, slots=True)
class Coverage:
    """What the scan actually looked at — the honesty section of the report."""

    files_scanned: int
    units_extracted: int
    lines_in_units: int
    candidate_pairs: int
    total_possible_pairs: int
    candidates_truncated: bool
    files_fully_resolved: int
    unresolved_by_reason: dict[str, int] = field(default_factory=dict[str, int])
    churn_available: bool = True

    @property
    def resolution_percent(self) -> int:
        if self.files_scanned == 0:
            return 0
        return round(100 * self.files_fully_resolved / self.files_scanned)


@dataclass(frozen=True, slots=True)
class AuditReport:
    schema_version: str
    tool_version: str
    generated_at: str
    root: str
    detector: str
    duration_seconds: float
    coverage: Coverage
    clusters: list[ClusterReport]

    @property
    def total_removable_lines(self) -> int:
        return sum(cluster.removable_lines for cluster in self.clusters)

    @property
    def remediable_clusters(self) -> int:
        return sum(1 for cluster in self.clusters if cluster.safely_remediable)

    @property
    def duplicated_line_percent(self) -> float:
        if self.coverage.lines_in_units == 0:
            return 0.0
        return 100 * self.total_removable_lines / self.coverage.lines_in_units

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, *, indent: int = 2) -> str:
        """Stable JSON: sorted keys so two runs of the same scan diff cleanly."""
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True) + "\n"
