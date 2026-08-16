"""AST-structural detector behavior at the pair level."""

from reweave_engine.detector import LoadedUnit
from reweave_engine.structural import AstStructuralDetector
from reweave_shared import Language, Verdict
from reweave_shared.findings import CodeUnit, Span


def load(name: str, text: str, language: Language = Language.PYTHON) -> LoadedUnit:
    suffix = "py" if language is Language.PYTHON else "ts"
    return LoadedUnit(
        unit=CodeUnit(
            path=f"src/{name}.{suffix}",
            span=Span(start_line=1, end_line=max(1, text.count("\n"))),
            language=language,
            name=name,
            content_hash=f"sha256:{name}",
        ),
        text=text,
    )


CLAMP_A = "def clamp(value, low, high):\n    if value < low:\n        return low\n    return value"
CLAMP_B = (
    "def bound(n, minimum, maximum):\n    if n < minimum:\n        return minimum\n    return n"
)
RANGE_INCLUSIVE = "def in_range(v, lo, hi):\n    return lo <= v <= hi\n"
RANGE_EXCLUSIVE = "def within(v, lo, hi):\n    return lo < v < hi\n"
UNRELATED = "def slugify(title):\n    return title.lower().replace(' ', '-')\n"


class TestVerdicts:
    def test_renamed_duplicate_is_found(self) -> None:
        finding = AstStructuralDetector().judge(load("a", CLAMP_A), load("b", CLAMP_B))
        assert finding.verdict is Verdict.DUPLICATE
        assert finding.metrics.structural.value == 1.0

    def test_unrelated_code_is_rejected(self) -> None:
        finding = AstStructuralDetector().judge(load("a", CLAMP_A), load("c", UNRELATED))
        assert finding.verdict is Verdict.NOT_DUPLICATE

    def test_bounds_difference_is_not_a_duplicate(self) -> None:
        finding = AstStructuralDetector().judge(
            load("a", RANGE_INCLUSIVE), load("b", RANGE_EXCLUSIVE)
        )
        assert finding.verdict is not Verdict.DUPLICATE


class TestContracts:
    def test_metrics_name_their_methods(self) -> None:
        finding = AstStructuralDetector().judge(load("a", CLAMP_A), load("b", CLAMP_B))
        assert finding.metrics.structural.method == "normalized_ast_shingle_jaccard_v1"
        assert finding.metrics.textual.method
        assert finding.metrics.embedding is None

    def test_never_recommends_consolidation(self) -> None:
        """Stage 1 has no repository context, so it cannot evaluate any D16 exclusion."""
        finding = AstStructuralDetector().judge(load("a", CLAMP_A), load("b", CLAMP_B))
        assert finding.advice is not None
        assert not finding.advice.recommended
        assert not finding.is_remediable

    def test_uncertain_band_discards_rather_than_guesses(self) -> None:
        detector = AstStructuralDetector(duplicate_threshold=0.99, uncertain_band=0.99)
        finding = detector.judge(load("a", CLAMP_A), load("c", UNRELATED))
        assert finding.verdict is Verdict.UNCERTAIN
        assert not finding.is_surfaceable

    def test_is_deterministic(self) -> None:
        detector = AstStructuralDetector()
        first = detector.judge(load("a", CLAMP_A), load("b", CLAMP_B))
        second = detector.judge(load("a", CLAMP_A), load("b", CLAMP_B))
        assert first.metrics == second.metrics
        assert first.verdict == second.verdict
