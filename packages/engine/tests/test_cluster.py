"""Clustering and blast-radius ranking."""

from __future__ import annotations

from typing import ClassVar

from reweave_engine.cluster import (
    BLAST_RADIUS_METHOD,
    build_clusters,
    measure_blast_radius,
    rank_clusters,
)
from reweave_engine.resolve import build_symbol_graph
from reweave_shared import (
    ConsolidationAdvice,
    ExclusionRule,
    Finding,
    Language,
    Measurement,
    PairMetrics,
    Verdict,
)
from reweave_shared.findings import CodeUnit, Span


def unit(path: str, name: str, start: int = 1, lines: int = 10) -> CodeUnit:
    return CodeUnit(
        path=path,
        span=Span(start_line=start, end_line=start + lines - 1),
        language=Language.PYTHON,
        name=name,
        content_hash=f"sha256:{path}:{name}",
    )


def metrics() -> PairMetrics:
    return PairMetrics(
        structural=Measurement(value=0.95, method="normalized_ast_shingle_jaccard_v1"),
        textual=Measurement(value=0.5, method="token_jaccard_v1"),
    )


def dup(left: CodeUnit, right: CodeUnit) -> Finding:
    return Finding(
        left=left,
        right=right,
        metrics=metrics(),
        verdict=Verdict.DUPLICATE,
        advice=ConsolidationAdvice(recommended=True, rationale="same package"),
    )


def uncertain(left: CodeUnit, right: CodeUnit) -> Finding:
    return Finding(left=left, right=right, metrics=metrics(), verdict=Verdict.UNCERTAIN)


class TestClustering:
    def test_transitive_pairs_form_one_cluster(self) -> None:
        a, b, c = unit("a.py", "f"), unit("b.py", "g"), unit("c.py", "h")
        clusters = build_clusters([dup(a, b), dup(b, c)])
        assert len(clusters) == 1
        assert len(clusters[0].units) == 3

    def test_unrelated_pairs_stay_separate(self) -> None:
        a, b = unit("a.py", "f"), unit("b.py", "g")
        c, d = unit("c.py", "h"), unit("d.py", "i")
        assert len(build_clusters([dup(a, b), dup(c, d)])) == 2

    def test_uncertain_findings_never_merge_clusters(self) -> None:
        """An UNCERTAIN verdict must not be able to join two unrelated clusters (D6)."""
        a, b, c = unit("a.py", "f"), unit("b.py", "g"), unit("c.py", "h")
        clusters = build_clusters([dup(a, b), uncertain(b, c)])
        assert len(clusters) == 1
        assert len(clusters[0].units) == 2

    def test_clustering_is_deterministic(self) -> None:
        a, b, c = unit("a.py", "f"), unit("b.py", "g"), unit("c.py", "h")
        findings = [dup(a, b), dup(b, c)]
        first = [cl.cluster_id for cl in build_clusters(findings)]
        second = [cl.cluster_id for cl in build_clusters(findings)]
        assert first == second


class TestRemovableLines:
    def test_keeps_one_implementation(self) -> None:
        """Three 10-line copies free 20 lines, not 30 — one has to survive."""
        a, b, c = (unit(f"{n}.py", "f", lines=10) for n in "abc")
        cluster = build_clusters([dup(a, b), dup(b, c)])[0]
        assert cluster.total_lines == 30
        assert cluster.removable_lines == 20

    def test_largest_member_is_the_survivor(self) -> None:
        a = unit("a.py", "f", lines=30)
        b = unit("b.py", "g", lines=10)
        cluster = build_clusters([dup(a, b)])[0]
        assert cluster.removable_lines == 10


class TestBlastRadius:
    FILES: ClassVar[dict[str, str]] = {
        "pkg/money.py": "def fmt(v):\n    x = v * 2\n    return x\n",
        "pkg/a.py": "from .money import fmt\n\ndef ra(v):\n    y = 1\n    return fmt(v)\n",
        "pkg/b.py": "from .money import fmt\n\ndef rb(v):\n    y = 2\n    return fmt(v)\n",
    }

    def test_counts_resolved_call_sites(self) -> None:
        graph = build_symbol_graph(self.FILES)
        cluster = build_clusters([dup(unit("pkg/money.py", "fmt"), unit("pkg/other.py", "fmt2"))])[
            0
        ]
        radius = measure_blast_radius(cluster, graph)
        assert radius.call_sites == 2

    def test_churn_is_summed_across_member_files(self) -> None:
        cluster = build_clusters([dup(unit("a.py", "f"), unit("b.py", "g"))])[0]
        radius = measure_blast_radius(cluster, None, {"a.py": 3, "b.py": 4})
        assert radius.churn == 7

    def test_unresolved_member_blocks_safe_remediation(self) -> None:
        files = dict(self.FILES)
        files["pkg/dyn.py"] = (
            "import pkg.money\n\ndef rc(v):\n    z = 1\n    return pkg.money.fmt(v)\n"
        )
        graph = build_symbol_graph(files)
        cluster = build_clusters([dup(unit("pkg/dyn.py", "rc"), unit("pkg/a.py", "ra"))])[0]
        radius = measure_blast_radius(cluster, graph)
        assert radius.unresolved_paths == 1
        assert not radius.is_safely_remediable

    def test_clean_cluster_is_safely_remediable(self) -> None:
        graph = build_symbol_graph(self.FILES)
        cluster = build_clusters([dup(unit("pkg/a.py", "ra"), unit("pkg/b.py", "rb"))])[0]
        assert measure_blast_radius(cluster, graph).is_safely_remediable

    def test_score_names_its_formula(self) -> None:
        radius = measure_blast_radius(
            build_clusters([dup(unit("a.py", "f"), unit("b.py", "g"))])[0]
        )
        assert radius.method == BLAST_RADIUS_METHOD

    def test_components_are_reported_separately(self) -> None:
        """D17: the roll-up never replaces the numbers it rolls up."""
        radius = measure_blast_radius(
            build_clusters([dup(unit("a.py", "f"), unit("b.py", "g"))])[0], None, {"a.py": 5}
        )
        assert radius.churn == 5
        assert radius.removable_lines == 10
        assert radius.call_sites == 0


class TestRanking:
    def test_more_removable_lines_ranks_higher(self) -> None:
        big = dup(unit("big1.py", "f", lines=100), unit("big2.py", "g", lines=100))
        small = dup(unit("s1.py", "h", lines=4), unit("s2.py", "i", lines=4))
        ranked = rank_clusters([big, small])
        assert ranked[0].cluster.removable_lines == 100

    def test_churn_breaks_a_tie_between_equal_sizes(self) -> None:
        quiet = dup(unit("q1.py", "f", lines=20), unit("q2.py", "g", lines=20))
        hot = dup(unit("h1.py", "x", lines=20), unit("h2.py", "y", lines=20))
        ranked = rank_clusters([quiet, hot], None, {"h1.py": 12, "h2.py": 9})
        assert ranked[0].cluster.paths == {"h1.py", "h2.py"}

    def test_ranking_is_deterministic(self) -> None:
        findings = [
            dup(unit("a1.py", "f", lines=10), unit("a2.py", "g", lines=10)),
            dup(unit("b1.py", "h", lines=10), unit("b2.py", "i", lines=10)),
        ]
        first = [r.cluster.cluster_id for r in rank_clusters(findings)]
        second = [r.cluster.cluster_id for r in rank_clusters(findings)]
        assert first == second

    def test_findings_travel_with_their_cluster(self) -> None:
        a, b = unit("a.py", "f"), unit("b.py", "g")
        ranked = rank_clusters([dup(a, b)])
        assert len(ranked[0].findings) == 1

    def test_excluded_duplicates_still_cluster(self) -> None:
        """A D16 exclusion blocks the fix, not the finding — it still belongs on the dashboard."""
        finding = Finding(
            left=unit("svc_a/x.py", "f"),
            right=unit("svc_b/y.py", "g"),
            metrics=metrics(),
            verdict=Verdict.DUPLICATE,
            advice=ConsolidationAdvice(
                recommended=False,
                exclusion=ExclusionRule.CROSS_BOUNDARY,
                rationale="separate services",
            ),
        )
        assert len(rank_clusters([finding])) == 1
