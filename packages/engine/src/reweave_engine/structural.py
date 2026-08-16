"""AST-structural detector — D5 stage 1 as a standalone `PairDetector`.

Replaces the lexical baseline's notion of "structure" with a real one. Stage 1's job in the
three-stage design is *not* to find everything: it is to be cheap, deterministic, and precise
enough that the expensive stages only ever see a shortlist. Semantic reimplementations — a
`reduce` against a `for` loop — are out of reach here by construction and belong to stages 2 and
3.

What this stage must do well is the other half: never confuse two behaviorally different
functions that happen to look alike. That is where the lexical baseline lost, and where the
normalizer's operator- and order-sensitivity pays off.
"""

from __future__ import annotations

from typing import Final

from reweave_engine.baseline import textual_overlap
from reweave_engine.detector import LoadedUnit
from reweave_engine.normalize import normalize_source, shingles, structural_hash
from reweave_shared import (
    ConsolidationAdvice,
    ExclusionRule,
    Finding,
    Measurement,
    PairMetrics,
    Verdict,
)

#: Thresholds are config, never hardcoded policy (Phase 1 failsafe). Tuned on the train split
#: only; the holdout stays sealed.
#:
#: Swept on corpus v1 train (precision / recall): 0.60 → .554/.534, 0.65 → .585/.534,
#: 0.70 → .600/.517, 0.80 → .658/.431, 0.90 → .719/.397, 0.95 → .759/.379. Precision can be
#: bought here, but only with recall, and 0.95 still falls far short of the 0.90 precision Phase 1
#: requires. That is the D5 thesis restated as a measurement: **stage 1 cannot reach the product's
#: precision bar alone, and it is not supposed to.**
#:
#: 0.70 is chosen as the best precision available before recall starts falling away. When the
#: adjudicator lands and precision becomes stage 3's job, this threshold should come *down*
#: toward 0.55-0.60 to widen the shortlist — a true pair dropped here can never be recovered
#: later, which is the one error a candidate generator must not make.
DEFAULT_DUPLICATE_THRESHOLD: Final = 0.70
DEFAULT_UNCERTAIN_BAND: Final = 0.10
DEFAULT_SHINGLE_WIDTH: Final = 4


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 1.0
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


class AstStructuralDetector:
    """Structural similarity over alpha-renamed AST token streams."""

    def __init__(
        self,
        duplicate_threshold: float = DEFAULT_DUPLICATE_THRESHOLD,
        uncertain_band: float = DEFAULT_UNCERTAIN_BAND,
        shingle_width: int = DEFAULT_SHINGLE_WIDTH,
        *,
        indexed_identifiers: bool = True,
    ) -> None:
        self._duplicate_threshold = duplicate_threshold
        self._uncertain_band = uncertain_band
        self._shingle_width = shingle_width
        self._indexed = indexed_identifiers

    @property
    def name(self) -> str:
        suffix = "" if self._indexed else "_flat"
        return f"ast_structural_v1{suffix}"

    def _tokens(self, unit: LoadedUnit) -> list[str]:
        return normalize_source(unit.text, unit.unit.language, indexed=self._indexed)

    def judge(self, left: LoadedUnit, right: LoadedUnit) -> Finding:
        left_tokens = self._tokens(left)
        right_tokens = self._tokens(right)

        if structural_hash(left_tokens) == structural_hash(right_tokens):
            # Identical modulo names, literals, comments, and whitespace.
            similarity = 1.0
        else:
            similarity = _jaccard(
                shingles(left_tokens, self._shingle_width),
                shingles(right_tokens, self._shingle_width),
            )

        metrics = PairMetrics(
            structural=Measurement(value=similarity, method="normalized_ast_shingle_jaccard_v1"),
            textual=textual_overlap(left.text, right.text),
        )

        lower_bound = self._duplicate_threshold - self._uncertain_band
        if similarity >= self._duplicate_threshold:
            verdict = Verdict.DUPLICATE
        elif similarity >= lower_bound:
            verdict = Verdict.UNCERTAIN
        else:
            verdict = Verdict.NOT_DUPLICATE

        advice: ConsolidationAdvice | None = None
        if verdict is Verdict.DUPLICATE:
            # Stage 1 sees two snippets and nothing else — no ownership graph, no git history,
            # no resolved call sites. It cannot evaluate a single D16 exclusion, so it never
            # recommends consolidation. Advisability is the adjudicator's job.
            advice = ConsolidationAdvice(
                recommended=False,
                exclusion=ExclusionRule.UNRESOLVED_CALL_SITES,
                rationale="structural stage has no repository context to judge advisability (D16)",
            )

        rationale = f"structural={metrics.structural.percent}% textual={metrics.textual.percent}%"
        return Finding(
            left=left.unit,
            right=right.unit,
            metrics=metrics,
            verdict=verdict,
            advice=advice,
            rationale=rationale,
        )
