"""The scan pipeline: a directory in, an `AuditReport` out.

One orchestration used by every caller — the `reweave-audit` CLI today, the Celery worker in
Phase 2, the repo-level eval harness in `benchmarks/`. Keeping it in the engine rather than in
the CLI is what stops the API and the CLI from drifting into two subtly different products.

The pipeline is D5 stage 1 end to end: parse → normalize → fingerprint → candidates → judge,
then resolve → cluster → rank. Stages 2 and 3 slot in at the judging step without changing the
shape of anything around them.
"""

from __future__ import annotations

import time
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from reweave_engine.cluster import file_churn, rank_clusters
from reweave_engine.detector import LoadedUnit, PairDetector
from reweave_engine.fingerprint import DEFAULT_CANDIDATE_BUDGET, generate_candidates, signature
from reweave_engine.normalize import normalize_source, shingles
from reweave_engine.parsing import DEFAULT_MIN_LINES, ExtractedUnit, extract_file, language_for_path
from reweave_engine.report.model import (
    SCHEMA_VERSION,
    AuditReport,
    ClusterReport,
    Coverage,
    Evidence,
    UnitRef,
)
from reweave_engine.resolve import build_symbol_graph
from reweave_engine.structural import AstStructuralDetector
from reweave_shared import Finding

#: Directories never worth scanning. Vendored and generated trees produce enormous numbers of
#: real-but-useless duplicates (D16's `generated_or_vendored`), so skipping them up front is
#: cheaper than excluding them at the adjudication stage.
SKIP_DIRS: Final[frozenset[str]] = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        "node_modules",
        "dist",
        "build",
        "out",
        "vendor",
        "__pycache__",
        ".venv",
        "venv",
        ".tox",
        ".mypy_cache",
        ".pytest_cache",
        ".next",
        ".nuxt",
        "coverage",
        "site-packages",
        ".terraform",
    }
)

#: Cap on how much source travels into a report's evidence block. Local-only today, but the
#: same renderer serves the hosted scorecard in Phase 2, where D10 caps evidence snippets.
MAX_EVIDENCE_CHARS: Final = 1_400


def discover_files(root: Path, *, skip_dirs: frozenset[str] = SKIP_DIRS) -> dict[str, str]:
    """Read every supported source file under ``root``, keyed by repo-relative path."""
    files: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in skip_dirs for part in path.relative_to(root).parts[:-1]):
            continue
        if language_for_path(path) is None:
            continue
        try:
            files[str(path.relative_to(root))] = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            # An unreadable file is a coverage gap, not a crash.
            continue
    return files


def _to_ref(unit: object) -> UnitRef:
    # Accepts a shared CodeUnit; kept structural so the report layer never imports the engine's
    # internal types into its own signature.
    return UnitRef(
        path=unit.path,  # type: ignore[attr-defined]
        start_line=unit.span.start_line,  # type: ignore[attr-defined]
        end_line=unit.span.end_line,  # type: ignore[attr-defined]
        name=unit.name,  # type: ignore[attr-defined]
        language=unit.language.value,  # type: ignore[attr-defined]
    )


def detect_duplicates(
    units: list[ExtractedUnit],
    *,
    detector: PairDetector | None = None,
    budget: int = DEFAULT_CANDIDATE_BUDGET,
) -> tuple[list[Finding], int, int, bool]:
    """Run candidate generation and judging.

    Returns ``(surfaceable findings, candidates considered, total possible pairs, truncated)``.
    """
    active = detector or AstStructuralDetector()
    signatures = [
        signature(shingles(normalize_source(unit.text, unit.unit.language), 4)) for unit in units
    ]
    candidates = generate_candidates(signatures, budget=budget)

    findings: list[Finding] = []
    for left_index, right_index in candidates.pairs:
        left, right = units[left_index], units[right_index]
        finding = active.judge(LoadedUnit(left.unit, left.text), LoadedUnit(right.unit, right.text))
        if finding.is_surfaceable:
            findings.append(finding)

    total_pairs = len(units) * (len(units) - 1) // 2
    return findings, candidates.considered, total_pairs, candidates.truncated


def scan(
    root: Path,
    *,
    detector: PairDetector | None = None,
    min_lines: int = DEFAULT_MIN_LINES,
    budget: int = DEFAULT_CANDIDATE_BUDGET,
    use_git: bool = True,
    max_clusters: int | None = None,
    tool_version: str = "0.0.0",
) -> AuditReport:
    """Scan a directory and produce an audit report."""
    started = time.perf_counter()
    root = root.resolve()

    files = discover_files(root)
    units: list[ExtractedUnit] = []
    for path in files:
        units.extend(extract_file(root / path, min_lines=min_lines, root=root))

    active = detector or AstStructuralDetector()
    findings, considered, total_pairs, truncated = detect_duplicates(
        units, detector=active, budget=budget
    )

    graph = build_symbol_graph(files)

    # Churn is optional and its absence is reported, never silently rendered as zero.
    churn: dict[str, int] = {}
    churn_available = False
    if use_git:
        churn = file_churn(root)
        churn_available = bool(churn)

    ranked = rank_clusters(findings, graph, churn)
    if max_clusters is not None:
        ranked = ranked[:max_clusters]

    clusters: list[ClusterReport] = []
    for item in ranked:
        blocked = sorted(
            {
                unresolved.reason.value
                for path in item.cluster.paths
                for unresolved in graph.unresolved_for(path)
                if not graph.is_fully_resolved(path)
            }
        )
        clusters.append(
            ClusterReport(
                cluster_id=item.cluster.cluster_id,
                units=[_to_ref(unit) for unit in item.cluster.units],
                removable_lines=item.blast_radius.removable_lines,
                call_sites=item.blast_radius.call_sites,
                churn=item.blast_radius.churn if churn_available else None,
                score=round(item.blast_radius.score, 2),
                score_method=item.blast_radius.method,
                safely_remediable=item.blast_radius.is_safely_remediable,
                blocked_reasons=blocked,
                evidence=[_evidence(finding) for finding in item.findings[:3]],
            )
        )

    coverage = Coverage(
        files_scanned=len(files),
        units_extracted=len(units),
        lines_in_units=sum(unit.line_count for unit in units),
        candidate_pairs=considered,
        total_possible_pairs=total_pairs,
        candidates_truncated=truncated,
        files_fully_resolved=sum(1 for path in files if graph.is_fully_resolved(path)),
        unresolved_by_reason={
            reason.value: count
            for reason, count in sorted(
                graph.unresolved_by_reason.items(), key=lambda item: item[0].value
            )
        },
        churn_available=churn_available,
    )

    return AuditReport(
        schema_version=SCHEMA_VERSION,
        tool_version=tool_version,
        generated_at=datetime.now(UTC).isoformat(timespec="seconds"),
        root=str(root),
        detector=active.name,
        duration_seconds=round(time.perf_counter() - started, 2),
        coverage=coverage,
        clusters=clusters,
    )


def _evidence(finding: Finding) -> Evidence:
    return Evidence(
        left=_to_ref(finding.left),
        right=_to_ref(finding.right),
        structural_percent=finding.metrics.structural.percent,
        structural_method=finding.metrics.structural.method,
        textual_percent=finding.metrics.textual.percent,
        textual_method=finding.metrics.textual.method,
        rationale=finding.rationale,
    )


def read_snippet(root: Path, ref: UnitRef, *, max_chars: int = MAX_EVIDENCE_CHARS) -> str:
    """Read a unit's source for the report's side-by-side evidence."""
    try:
        lines = (root / ref.path).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    body = "\n".join(lines[ref.start_line - 1 : ref.end_line])
    if len(body) > max_chars:
        return body[:max_chars] + "\n…"
    return body


def iter_snippets(root: Path, refs: Iterable[UnitRef]) -> dict[str, str]:
    return {ref.location: read_snippet(root, ref) for ref in refs}
