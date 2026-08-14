"""Core finding schema.

Two of the plan's product laws are enforced here rather than in prose, because a law that
lives only in a document gets violated by the third caller:

* **D6 (precision):** an ``UNCERTAIN`` verdict can never be surfaced to a customer.
* **D16 (restraint):** a consolidation can only be recommended for a confirmed duplicate with
  no exclusion rule firing.

Both are model validators, so constructing an illegal finding raises rather than shipping.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Language(StrEnum):
    TYPESCRIPT = "typescript"
    JAVASCRIPT = "javascript"
    PYTHON = "python"


class Span(BaseModel):
    """A region of a file. Lines are 1-indexed and inclusive on both ends."""

    model_config = ConfigDict(frozen=True)

    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.end_line < self.start_line:
            msg = f"end_line {self.end_line} precedes start_line {self.start_line}"
            raise ValueError(msg)
        return self

    @property
    def line_count(self) -> int:
        return self.end_line - self.start_line + 1


class CodeUnit(BaseModel):
    """A function or method extracted from a repository.

    Deliberately does not carry source text. Text is passed separately and transiently through
    the pipeline so that persistence of a ``CodeUnit`` can never accidentally persist code (D10).
    """

    model_config = ConfigDict(frozen=True)

    path: str
    span: Span
    language: Language
    name: str
    content_hash: str = Field(description="sha256 of the normalized unit text; the cache key")

    @property
    def location(self) -> str:
        return f"{self.path}:{self.span.start_line}"


class Measurement(BaseModel):
    """A number we display, tagged with how it was computed (D17).

    Every user-visible figure carries its method so we can recompute it in front of a skeptical
    customer. A ``Measurement`` without a method is not constructible.
    """

    model_config = ConfigDict(frozen=True)

    value: float = Field(ge=0.0, le=1.0)
    method: str = Field(min_length=1, description="e.g. 'normalized_ast_jaccard_v1'")

    @property
    def percent(self) -> int:
        return round(self.value * 100)


class PairMetrics(BaseModel):
    """Similarity measurements for a pair of code units.

    Note the absence of a combined score. That is intentional and load-bearing: D17 forbids
    blending these into one unexplained "94% match". Rankers may weight them internally, but no
    blended value is ever displayed or persisted as if it were a measurement.
    """

    model_config = ConfigDict(frozen=True)

    structural: Measurement
    textual: Measurement
    embedding: Measurement | None = None


class Verdict(StrEnum):
    DUPLICATE = "duplicate"
    NOT_DUPLICATE = "not_duplicate"
    UNCERTAIN = "uncertain"
    """Adjudicator disagreement or low confidence. Discarded, never surfaced (D6)."""


class ExclusionRule(StrEnum):
    """Why a true duplicate should nonetheless be left alone (D16)."""

    CROSS_BOUNDARY = "cross_boundary"
    """Different services, packages, bounded contexts, or CODEOWNERS."""

    GENERATED_OR_VENDORED = "generated_or_vendored"
    """Generated code, vendored deps, migrations, fixtures, test scaffolding."""

    DIVERGED_HISTORY = "diverged_history"
    """Both sides edited independently in the last 90 days — evolving apart on purpose."""

    REQUIRES_FLAG_PARAM = "requires_flag_param"
    """Unifying needs a boolean/flag to reconcile behavior: the wrong abstraction, mechanized."""

    BELOW_SIZE_FLOOR = "below_size_floor"
    """Too small for indirection to pay for itself."""

    UNRESOLVED_CALL_SITES = "unresolved_call_sites"
    """We could not fully resolve references; rewriting risks a silent break."""


class ConsolidationAdvice(BaseModel):
    """Whether consolidation is *advisable*, which is a separate question from whether the pair
    is a duplicate. See D16."""

    model_config = ConfigDict(frozen=True)

    recommended: bool
    exclusion: ExclusionRule | None = None
    rationale: str = Field(min_length=1)

    @model_validator(mode="after")
    def _exclusion_blocks_recommendation(self) -> Self:
        if self.recommended and self.exclusion is not None:
            msg = f"cannot recommend consolidation while exclusion {self.exclusion} applies (D16)"
            raise ValueError(msg)
        if not self.recommended and self.exclusion is None:
            msg = "declining to recommend consolidation requires naming the exclusion rule (D16)"
            raise ValueError(msg)
        return self


class Finding(BaseModel):
    """A duplicate pair, its measurements, and what we advise doing about it."""

    model_config = ConfigDict(frozen=True)

    left: CodeUnit
    right: CodeUnit
    metrics: PairMetrics
    verdict: Verdict
    advice: ConsolidationAdvice | None = None
    rationale: str = ""

    @model_validator(mode="after")
    def _advice_requires_duplicate_verdict(self) -> Self:
        if (
            self.advice is not None
            and self.advice.recommended
            and self.verdict is not Verdict.DUPLICATE
        ):
            msg = f"consolidation recommended on a {self.verdict} verdict (D16)"
            raise ValueError(msg)
        return self

    @property
    def is_surfaceable(self) -> bool:
        """May this be shown to a customer at all? Uncertainty is discarded (D6)."""
        return self.verdict is Verdict.DUPLICATE

    @property
    def is_remediable(self) -> bool:
        """May this become a consolidation PR? Surfaceable *and* advisable (D16)."""
        return self.is_surfaceable and self.advice is not None and self.advice.recommended
