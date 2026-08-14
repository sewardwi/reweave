"""Baseline detector behavior, including the limitation it exists to quantify."""

from reweave_engine import LoadedUnit, TokenOverlapDetector
from reweave_engine.baseline import (
    normalize_tokens,
    structural_similarity,
    textual_overlap,
    tokenize,
)
from reweave_shared import Language, Verdict
from reweave_shared.findings import CodeUnit, Span

RENAMED_A = """
function formatCurrency(amount, currency) {
  const rounded = Math.round(amount * 100) / 100;
  return currency + rounded.toFixed(2);
}
"""

RENAMED_B = """
function formatMoney(value, symbol) {
  const cents = Math.round(value * 100) / 100;
  return symbol + cents.toFixed(2);
}
"""

# Same observable behavior, different construction: a loop instead of reduce. This is the
# AI-reimplementation shape the product is built to catch, and the baseline should miss it.
REIMPLEMENTED_A = """
function total(items) {
  return items.reduce((acc, item) => acc + item.price, 0);
}
"""

REIMPLEMENTED_B = """
function sumPrices(list) {
  let running = 0;
  for (const entry of list) {
    running = running + entry.price;
  }
  return running;
}
"""

UNRELATED = """
function slugify(title) {
  return title.toLowerCase().replace(/[^a-z0-9]+/g, '-');
}
"""


def load(name: str, text: str) -> LoadedUnit:
    line_count = max(1, text.count("\n"))
    return LoadedUnit(
        unit=CodeUnit(
            path=f"src/{name}.ts",
            span=Span(start_line=1, end_line=line_count),
            language=Language.TYPESCRIPT,
            name=name,
            content_hash=f"sha256:{name}",
        ),
        text=text,
    )


class TestNormalization:
    def test_erases_identifiers_and_literals_but_keeps_keywords(self) -> None:
        tokens = normalize_tokens(tokenize("const total = items.length + 1;"))
        assert "const" in tokens
        assert "ID" in tokens
        assert "LIT" in tokens
        assert "total" not in tokens

    def test_renaming_does_not_change_the_normalized_form(self) -> None:
        assert normalize_tokens(tokenize("const a = b.c;")) == normalize_tokens(
            tokenize("const x = y.z;")
        )


class TestMeasurements:
    def test_every_measurement_names_its_method(self) -> None:
        assert structural_similarity(RENAMED_A, RENAMED_B).method
        assert textual_overlap(RENAMED_A, RENAMED_B).method

    def test_structural_beats_textual_on_renamed_code(self) -> None:
        # The whole point of normalizing: renaming tanks textual overlap but not structure.
        structural = structural_similarity(RENAMED_A, RENAMED_B).value
        textual = textual_overlap(RENAMED_A, RENAMED_B).value
        assert structural > textual


class TestDetector:
    def test_catches_renamed_duplicates(self) -> None:
        finding = TokenOverlapDetector().judge(load("a", RENAMED_A), load("b", RENAMED_B))
        assert finding.verdict is Verdict.DUPLICATE
        assert finding.is_surfaceable

    def test_rejects_unrelated_code(self) -> None:
        finding = TokenOverlapDetector().judge(load("a", RENAMED_A), load("c", UNRELATED))
        assert finding.verdict is Verdict.NOT_DUPLICATE

    def test_misses_semantic_reimplementation(self) -> None:
        """Documents the baseline's ceiling — this is the gap Phase 1 must close.

        If this test ever starts failing because the baseline got smarter, that is fine; but if
        the D5 pipeline can't do better than this on the holdout, D5 is not earning its cost.
        """
        finding = TokenOverlapDetector().judge(
            load("total", REIMPLEMENTED_A), load("sumPrices", REIMPLEMENTED_B)
        )
        assert finding.verdict is not Verdict.DUPLICATE

    def test_never_recommends_consolidation_without_repo_context(self) -> None:
        finding = TokenOverlapDetector().judge(load("a", RENAMED_A), load("b", RENAMED_B))
        assert finding.advice is not None
        assert not finding.advice.recommended
        assert not finding.is_remediable

    def test_is_deterministic(self) -> None:
        detector = TokenOverlapDetector()
        first = detector.judge(load("a", RENAMED_A), load("b", RENAMED_B))
        second = detector.judge(load("a", RENAMED_A), load("b", RENAMED_B))
        assert first.metrics == second.metrics
        assert first.verdict == second.verdict
