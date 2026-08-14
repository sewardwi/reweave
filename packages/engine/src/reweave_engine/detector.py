"""The detector interface every stage of the pipeline is measured against.

The benchmark (D12) talks to this protocol and nothing else, so the Phase 0 baseline, the Phase 1
three-stage pipeline (D5), and any future variant are all scored on identical terms. Keeping this
narrow is what makes "did that change help?" answerable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from reweave_shared import CodeUnit, Finding


@dataclass(frozen=True, slots=True)
class LoadedUnit:
    """A code unit together with its source text.

    Text travels with the unit only while in memory. ``CodeUnit`` alone is what gets persisted,
    which is how D10 stays true by construction rather than by remembering.
    """

    unit: CodeUnit
    text: str


@runtime_checkable
class PairDetector(Protocol):
    """Judges whether two code units are duplicates.

    Implementations must be deterministic given identical inputs and warm caches — the Phase 1
    exit criteria require reproducible re-runs, and a benchmark over a nondeterministic detector
    measures nothing.
    """

    @property
    def name(self) -> str:
        """Stable identifier recorded in benchmark reports, e.g. 'token_overlap_v1'."""
        ...

    def judge(self, left: LoadedUnit, right: LoadedUnit) -> Finding:
        """Return a finding for this pair. Never raises for ordinary input.

        Uncertainty is expressed as ``Verdict.UNCERTAIN``, not as an exception and not as a
        low-confidence duplicate — discard-on-uncertainty is the precision law (D6).
        """
        ...
