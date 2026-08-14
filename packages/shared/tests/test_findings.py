"""The product laws in findings.py are only real if they're tested."""

import pytest
from pydantic import ValidationError

from reweave_shared import (
    CodeUnit,
    ConsolidationAdvice,
    ExclusionRule,
    Finding,
    Measurement,
    PairMetrics,
    Span,
    Verdict,
)
from reweave_shared.findings import Language


def unit(name: str, path: str = "src/a.ts") -> CodeUnit:
    return CodeUnit(
        path=path,
        span=Span(start_line=1, end_line=20),
        language=Language.TYPESCRIPT,
        name=name,
        content_hash=f"sha256:{name}",
    )


def metrics() -> PairMetrics:
    return PairMetrics(
        structural=Measurement(value=0.91, method="normalized_ast_jaccard_v1"),
        textual=Measurement(value=0.46, method="token_overlap_v1"),
    )


class TestSpan:
    def test_rejects_inverted_span(self) -> None:
        with pytest.raises(ValidationError):
            Span(start_line=40, end_line=12)

    def test_line_count_is_inclusive(self) -> None:
        assert Span(start_line=10, end_line=12).line_count == 3


class TestMeasurement:
    def test_requires_a_method_tag(self) -> None:
        with pytest.raises(ValidationError):
            Measurement(value=0.9, method="")

    def test_rejects_out_of_range(self) -> None:
        with pytest.raises(ValidationError):
            Measurement(value=1.4, method="whatever_v1")

    def test_percent_rounds_for_display(self) -> None:
        assert Measurement(value=0.914, method="m_v1").percent == 91


class TestPairMetrics:
    def test_exposes_no_blended_score(self) -> None:
        # D17: a combined score is not constructible, so the UI cannot display one.
        assert not hasattr(metrics(), "score")
        assert not hasattr(metrics(), "combined")


class TestConsolidationAdvice:
    def test_cannot_recommend_while_excluded(self) -> None:
        with pytest.raises(ValidationError):
            ConsolidationAdvice(
                recommended=True,
                exclusion=ExclusionRule.DIVERGED_HISTORY,
                rationale="both edited last month",
            )

    def test_declining_must_name_a_rule(self) -> None:
        with pytest.raises(ValidationError):
            ConsolidationAdvice(recommended=False, rationale="felt wrong")

    def test_valid_recommendation(self) -> None:
        advice = ConsolidationAdvice(recommended=True, rationale="same package, 3 call sites")
        assert advice.exclusion is None


class TestFinding:
    def test_uncertain_is_never_surfaceable(self) -> None:
        finding = Finding(
            left=unit("formatCurrency"),
            right=unit("formatMoney", path="lib/money.ts"),
            metrics=metrics(),
            verdict=Verdict.UNCERTAIN,
        )
        assert not finding.is_surfaceable
        assert not finding.is_remediable

    def test_cannot_recommend_consolidation_without_duplicate_verdict(self) -> None:
        with pytest.raises(ValidationError):
            Finding(
                left=unit("a"),
                right=unit("b"),
                metrics=metrics(),
                verdict=Verdict.NOT_DUPLICATE,
                advice=ConsolidationAdvice(recommended=True, rationale="looks close enough"),
            )

    def test_duplicate_but_excluded_is_surfaceable_not_remediable(self) -> None:
        finding = Finding(
            left=unit("parse", path="services/billing/parse.py"),
            right=unit("parse", path="services/search/parse.py"),
            metrics=metrics(),
            verdict=Verdict.DUPLICATE,
            advice=ConsolidationAdvice(
                recommended=False,
                exclusion=ExclusionRule.CROSS_BOUNDARY,
                rationale="separate services; unifying would couple them",
            ),
        )
        assert finding.is_surfaceable
        assert not finding.is_remediable

    def test_remediable_requires_both_gates(self) -> None:
        finding = Finding(
            left=unit("formatCurrency"),
            right=unit("formatMoney", path="lib/money.ts"),
            metrics=metrics(),
            verdict=Verdict.DUPLICATE,
            advice=ConsolidationAdvice(recommended=True, rationale="same package, low fan-out"),
        )
        assert finding.is_remediable
