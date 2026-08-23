"""Grouping duplicate pairs into clusters, and ranking them by blast radius.

Pairs are what the detector produces; **clusters are what a customer acts on.** Three functions
that are all the same logic form one cluster with one fix, not three findings.

Ranking answers "which of these should I look at first?", and the honest answer combines three
things a developer would weigh anyway: how much code would actually disappear, how many callers
are involved, and how actively the code is being edited. The composite is published and
versioned (D17) rather than presented as an objective quantity.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Final

from reweave_engine.resolve.graph import SymbolGraph
from reweave_shared import CodeUnit, Finding

#: Version tag for the ranking formula. Any change to the weighting below bumps this, so a score
#: in a stored report can always be traced to the formula that produced it.
BLAST_RADIUS_METHOD: Final = "blast_radius_v1"

UnitKey = tuple[str, int, str]


def unit_key(unit: CodeUnit) -> UnitKey:
    return (unit.path, unit.span.start_line, unit.name)


@dataclass
class Cluster:
    """A set of code units that are mutually duplicates."""

    cluster_id: str
    units: list[CodeUnit]

    @property
    def paths(self) -> set[str]:
        return {unit.path for unit in self.units}

    @property
    def total_lines(self) -> int:
        return sum(unit.span.line_count for unit in self.units)

    @property
    def removable_lines(self) -> int:
        """Lines that would actually disappear if the cluster were consolidated.

        One implementation has to survive, so the honest figure is everything except the largest
        member. Reporting `total_lines` here would inflate every "lines deleted" claim we make —
        and that number is the headline value metric, so it is exactly the one not to inflate.
        """
        if len(self.units) < 2:
            return 0
        return self.total_lines - max(unit.span.line_count for unit in self.units)


@dataclass(frozen=True, slots=True)
class BlastRadius:
    """Ranking inputs, kept separate from the composite (D17).

    Each component is a measurement in its own right and is displayed as one. ``score`` is a
    deliberate roll-up, labeled with the formula version that produced it.
    """

    call_sites: int
    churn: int
    removable_lines: int
    unresolved_paths: int
    method: str = BLAST_RADIUS_METHOD

    @property
    def score(self) -> float:
        """``removable_lines * (1 + ln(1 + call_sites)) * (1 + ln(1 + churn))``

        Logarithms because the tenth caller matters less than the second, and because a single
        very hot file should not dominate the whole ranking. Lines lead because they are the one
        term a customer can verify at a glance.
        """
        return (
            self.removable_lines * (1 + math.log1p(self.call_sites)) * (1 + math.log1p(self.churn))
        )

    @property
    def is_safely_remediable(self) -> bool:
        """False when any member file has references we could not resolve (PLAN.md §4)."""
        return self.unresolved_paths == 0


@dataclass
class RankedCluster:
    cluster: Cluster
    blast_radius: BlastRadius
    findings: list[Finding] = field(default_factory=list[Finding])


class _UnionFind:
    def __init__(self) -> None:
        self._parent: dict[UnitKey, UnitKey] = {}

    def add(self, key: UnitKey) -> None:
        self._parent.setdefault(key, key)

    def find(self, key: UnitKey) -> UnitKey:
        root = key
        while self._parent[root] != root:
            root = self._parent[root]
        while self._parent[key] != root:
            self._parent[key], key = root, self._parent[key]
        return root

    def union(self, left: UnitKey, right: UnitKey) -> None:
        left_root, right_root = self.find(left), self.find(right)
        if left_root != right_root:
            self._parent[right_root] = left_root


def build_clusters(findings: Iterable[Finding]) -> list[Cluster]:
    """Group surfaceable duplicate findings into clusters via connected components.

    Only findings that pass the precision law contribute: an `UNCERTAIN` verdict must not be
    able to merge two clusters that a customer would consider unrelated (D6).
    """
    union = _UnionFind()
    units: dict[UnitKey, CodeUnit] = {}
    edges: list[Finding] = []

    for finding in findings:
        if not finding.is_surfaceable:
            continue
        left_key, right_key = unit_key(finding.left), unit_key(finding.right)
        units.setdefault(left_key, finding.left)
        units.setdefault(right_key, finding.right)
        union.add(left_key)
        union.add(right_key)
        union.union(left_key, right_key)
        edges.append(finding)

    grouped: dict[UnitKey, list[UnitKey]] = {}
    for key in units:
        grouped.setdefault(union.find(key), []).append(key)

    clusters: list[Cluster] = []
    for root in sorted(grouped):
        members = sorted(grouped[root])
        clusters.append(
            Cluster(
                cluster_id=f"{members[0][0]}:{members[0][1]}:{members[0][2]}",
                units=[units[key] for key in members],
            )
        )
    return clusters


def measure_blast_radius(
    cluster: Cluster,
    graph: SymbolGraph | None = None,
    churn: Mapping[str, int] | None = None,
) -> BlastRadius:
    """Measure a cluster's blast radius from resolved call sites and recent churn."""
    call_sites = 0
    unresolved_paths = 0

    if graph is not None:
        for unit in cluster.units:
            bare = unit.name.rsplit(".", 1)[-1]
            call_sites += graph.call_site_count(unit.path, bare)
        unresolved_paths = sum(
            1 for path in sorted(cluster.paths) if not graph.is_fully_resolved(path)
        )

    churn_total = sum((churn or {}).get(path, 0) for path in sorted(cluster.paths))

    return BlastRadius(
        call_sites=call_sites,
        churn=churn_total,
        removable_lines=cluster.removable_lines,
        unresolved_paths=unresolved_paths,
    )


def rank_clusters(
    findings: Iterable[Finding],
    graph: SymbolGraph | None = None,
    churn: Mapping[str, int] | None = None,
) -> list[RankedCluster]:
    """Cluster findings and order them by blast radius, highest first.

    Ties break on cluster id so the ordering is deterministic — a report that reshuffles between
    identical runs is one nobody trusts.
    """
    findings = list(findings)
    clusters = build_clusters(findings)

    ranked: list[RankedCluster] = []
    for cluster in clusters:
        members = {unit_key(unit) for unit in cluster.units}
        related = [
            finding
            for finding in findings
            if finding.is_surfaceable
            and unit_key(finding.left) in members
            and unit_key(finding.right) in members
        ]
        ranked.append(
            RankedCluster(
                cluster=cluster,
                blast_radius=measure_blast_radius(cluster, graph, churn),
                findings=related,
            )
        )

    ranked.sort(key=lambda item: (-item.blast_radius.score, item.cluster.cluster_id))
    return ranked
