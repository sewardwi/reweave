"""The adjudicator's output contract (D5 stage 3, D11).

Model output is **never** trusted as control flow. It arrives as JSON, is validated against this
schema, and only then is mapped onto a `Finding`. A response that does not validate is discarded
as `UNCERTAIN` rather than salvaged — a malformed answer from a model that just read attacker-
controlled code is exactly the input we least want to be creative about.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from reweave_shared import ExclusionRule


class AdjudicatedVerdict(StrEnum):
    """Deliberately mirrors `Verdict` rather than reusing it: this is the wire contract with an
    external model, and it must be free to diverge from our internal type without silently
    changing product behavior."""

    DUPLICATE = "duplicate"
    NOT_DUPLICATE = "not_duplicate"
    UNCERTAIN = "uncertain"


class Confidence(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Adjudication(BaseModel):
    """One pair, judged.

    Note the two independent questions (D16): whether the pair *is* a duplicate, and whether it
    *should* be consolidated. The rubric asks for both and the schema requires both, because an
    adjudicator that can only answer the first cannot protect us from the failure mode that
    matters most.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    verdict: AdjudicatedVerdict
    confidence: Confidence
    behavior_summary: str = Field(
        min_length=1,
        max_length=600,
        description="What both units do, in one sentence, in the adjudicator's own words.",
    )
    consolidation_recommended: bool
    exclusion: ExclusionRule | None = None
    rationale: str = Field(min_length=1, max_length=1200)

    @model_validator(mode="after")
    def _coherent(self) -> Self:
        if self.consolidation_recommended:
            if self.verdict is not AdjudicatedVerdict.DUPLICATE:
                msg = "consolidation recommended on a non-duplicate verdict"
                raise ValueError(msg)
            if self.exclusion is not None:
                msg = "consolidation recommended while an exclusion rule applies (D16)"
                raise ValueError(msg)
        elif self.verdict is AdjudicatedVerdict.DUPLICATE and self.exclusion is None:
            msg = "declining consolidation on a duplicate requires naming the D16 rule"
            raise ValueError(msg)
        return self

    @property
    def is_confident(self) -> bool:
        """Low confidence is treated as uncertainty and discarded (D6)."""
        return self.confidence is not Confidence.LOW


#: JSON Schema handed to the API via `output_config.format`. Generated from the model above so
#: the two cannot drift — a hand-maintained copy would be wrong within a month.
def json_schema() -> dict[str, object]:
    schema = Adjudication.model_json_schema()
    schema["additionalProperties"] = False
    return schema
