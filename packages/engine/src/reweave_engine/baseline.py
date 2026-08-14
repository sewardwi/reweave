"""Phase 0 baseline detector: lexical, dependency-free, deliberately dumb.

This exists for two reasons. First, the CI bench gate needs a real detector to run against from
day one. Second, and more importantly, **it is the number Phase 1 has to beat.** A three-stage
pipeline with embeddings and an LLM adjudicator is only worth its cost and complexity if it
measurably outperforms token overlap — and the failure mode where it doesn't is common enough
that we should be able to detect it. If the D5 pipeline can't clear this baseline on the holdout,
that is a finding about D5, not about the baseline.

Its known limitation is exactly the thing the product claims to solve: it cannot see that two
functions with different identifiers and different control flow do the same thing. Expect it to
score poorly on the synthesized AI-reimplementation pairs. That gap is the product thesis,
quantified.
"""

from __future__ import annotations

import re
from typing import Final

from reweave_engine.detector import LoadedUnit
from reweave_shared import (
    ConsolidationAdvice,
    ExclusionRule,
    Finding,
    Measurement,
    PairMetrics,
    Verdict,
)

_TOKEN_RE: Final = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\d+\.?\d*|\"[^\"]*\"|'[^']*'|\S")

# Language keywords survive normalization; everything else identifier-shaped becomes a placeholder.
# A crude stand-in for the AST normalization that lands in Phase 1 (packages/engine/normalize).
_KEYWORDS: Final[frozenset[str]] = frozenset(
    {
        # shared control flow
        "if",
        "else",
        "for",
        "while",
        "return",
        "break",
        "continue",
        "try",
        "in",
        "not",
        "and",
        "or",
        "true",
        "false",
        "null",
        "none",
        "new",
        "await",
        "async",
        "yield",
        # js/ts
        "const",
        "let",
        "var",
        "function",
        "class",
        "export",
        "import",
        "typeof",
        "instanceof",
        "catch",
        "finally",
        "throw",
        "switch",
        "case",
        "default",
        "extends",
        "interface",
        "type",
        "enum",
        "of",
        "undefined",
        # python
        "def",
        "elif",
        "except",
        "raise",
        "with",
        "as",
        "lambda",
        "pass",
        "is",
        "from",
        "global",
        "nonlocal",
        "assert",
        "del",
    }
)

_IDENT_RE: Final = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_NUMBER_RE: Final = re.compile(r"^\d")
_STRING_RE: Final = re.compile(r"^[\"']")

#: Shingle width for structural comparison. 3 is the usual sweet spot for code n-grams: 2 matches
#: on noise, 4+ misses reordered-but-equivalent statements.
_SHINGLE: Final = 3

#: Thresholds are config, never hardcoded policy (Phase 1 failsafe). Defaults are tuned on the
#: training split only — never on the holdout.
DEFAULT_DUPLICATE_THRESHOLD: Final = 0.80
DEFAULT_UNCERTAIN_BAND: Final = 0.10


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text)


def normalize_tokens(tokens: list[str]) -> list[str]:
    """Strip identifiers and literals, keep structure. The lexical shadow of AST normalization."""
    out: list[str] = []
    for token in tokens:
        lowered = token.lower()
        if lowered in _KEYWORDS:
            out.append(lowered)
        elif _IDENT_RE.match(token):
            out.append("ID")
        elif _NUMBER_RE.match(token) or _STRING_RE.match(token):
            out.append("LIT")
        else:
            out.append(token)
    return out


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 1.0
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


def _shingles(tokens: list[str], width: int = _SHINGLE) -> set[str]:
    if len(tokens) < width:
        return {" ".join(tokens)} if tokens else set()
    return {" ".join(tokens[i : i + width]) for i in range(len(tokens) - width + 1)}


def textual_overlap(left: str, right: str) -> Measurement:
    """Raw token overlap — what jscpd-style tools see."""
    value = _jaccard(set(tokenize(left)), set(tokenize(right)))
    return Measurement(value=value, method="token_jaccard_v1")


def structural_similarity(left: str, right: str) -> Measurement:
    """Overlap after identifiers and literals are erased.

    Resistant to renaming; not resistant to redesign.
    """
    value = _jaccard(
        _shingles(normalize_tokens(tokenize(left))),
        _shingles(normalize_tokens(tokenize(right))),
    )
    return Measurement(value=value, method="normalized_token_shingle_jaccard_v1")


class TokenOverlapDetector:
    """Baseline ``PairDetector``. Structural similarity decides; textual is reported alongside."""

    def __init__(
        self,
        duplicate_threshold: float = DEFAULT_DUPLICATE_THRESHOLD,
        uncertain_band: float = DEFAULT_UNCERTAIN_BAND,
    ) -> None:
        self._duplicate_threshold = duplicate_threshold
        self._uncertain_band = uncertain_band

    @property
    def name(self) -> str:
        return "token_overlap_v1"

    def judge(self, left: LoadedUnit, right: LoadedUnit) -> Finding:
        metrics = PairMetrics(
            structural=structural_similarity(left.text, right.text),
            textual=textual_overlap(left.text, right.text),
        )
        score = metrics.structural.value
        lower_bound = self._duplicate_threshold - self._uncertain_band

        if score >= self._duplicate_threshold:
            verdict = Verdict.DUPLICATE
        elif score >= lower_bound:
            # Straddling the threshold is exactly where a lexical detector is least trustworthy.
            # Discard rather than guess (D6).
            verdict = Verdict.UNCERTAIN
        else:
            verdict = Verdict.NOT_DUPLICATE

        advice: ConsolidationAdvice | None = None
        if verdict is Verdict.DUPLICATE:
            # The baseline has no repository context — no ownership graph, no git history, no
            # resolved call sites — so it cannot evaluate the D16 exclusions at all. It therefore
            # never recommends consolidation. Advisability arrives with the Phase 1 adjudicator.
            advice = ConsolidationAdvice(
                recommended=False,
                exclusion=ExclusionRule.UNRESOLVED_CALL_SITES,
                rationale="baseline detector has no repository context to judge advisability (D16)",
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
