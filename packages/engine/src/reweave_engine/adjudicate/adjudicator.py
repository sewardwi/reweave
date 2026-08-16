"""Adjudicator interface and implementations (D5 stage 3, D11).

The API-calling surface here is deliberately thin. Everything that decides product behavior —
validating the response, applying the precision law, mapping to a `Finding` — is pure and tested
offline, so the untestable part is a few lines of transport rather than the logic that determines
whether we open a pull request.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Final, Protocol

from reweave_engine.adjudicate.prompt import SYSTEM_PROMPT, build_user_message
from reweave_engine.adjudicate.schema import AdjudicatedVerdict, Adjudication
from reweave_engine.detector import LoadedUnit
from reweave_shared import (
    ConsolidationAdvice,
    Finding,
    PairMetrics,
    Verdict,
)

if TYPE_CHECKING:
    from anthropic import Anthropic

#: Model IDs live in config, never in code (D11). This is the default, not a constant.
DEFAULT_MODEL: Final = "claude-opus-5"

#: Per-scan ceiling. A runaway scan that adjudicates ten thousand pairs is a billing incident,
#: so the budget is enforced here rather than trusted to a threshold upstream.
DEFAULT_TOKEN_BUDGET: Final = 2_000_000


class BudgetExhausted(RuntimeError):
    """The scan's token budget ran out. Not an error condition — a stop condition. The caller
    reports partial coverage rather than silently returning fewer findings."""


@dataclass
class TokenBudget:
    """Tracks spend across a scan so cost is a measured quantity, not a surprise."""

    limit: int = DEFAULT_TOKEN_BUDGET
    input_tokens: int = 0
    output_tokens: int = 0
    calls: int = 0

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def remaining(self) -> int:
        return max(0, self.limit - self.total)

    def check(self) -> None:
        if self.remaining <= 0:
            msg = f"token budget of {self.limit} exhausted after {self.calls} adjudications"
            raise BudgetExhausted(msg)

    def record(self, input_tokens: int, output_tokens: int) -> None:
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.calls += 1


class Adjudicator(Protocol):
    """Judges one candidate pair. Implementations must never raise for ordinary input."""

    def adjudicate(self, left: LoadedUnit, right: LoadedUnit) -> Adjudication | None:
        """Return a validated adjudication, or ``None`` when no usable answer was obtained.

        ``None`` covers every failure: a refusal, a malformed response, a transport error. The
        caller turns it into `UNCERTAIN`, which is discarded (D6). There is deliberately no way
        to distinguish "the model said something we could not parse" from "the model declined" at
        this boundary, because both must produce the same conservative outcome.
        """
        ...


def to_finding(
    left: LoadedUnit,
    right: LoadedUnit,
    metrics: PairMetrics,
    adjudication: Adjudication | None,
) -> Finding:
    """Map an adjudication onto a `Finding`, applying D6 and D16.

    This is where the precision law is actually enforced for stage 3: anything short of a
    confident `duplicate` becomes `UNCERTAIN`, and `UNCERTAIN` is not surfaceable.
    """
    if adjudication is None:
        return Finding(
            left=left.unit,
            right=right.unit,
            metrics=metrics,
            verdict=Verdict.UNCERTAIN,
            rationale="adjudication unavailable; discarded under the precision law (D6)",
        )

    if not adjudication.is_confident:
        return Finding(
            left=left.unit,
            right=right.unit,
            metrics=metrics,
            verdict=Verdict.UNCERTAIN,
            rationale=f"low confidence; discarded (D6). {adjudication.rationale}",
        )

    match adjudication.verdict:
        case AdjudicatedVerdict.DUPLICATE:
            verdict = Verdict.DUPLICATE
        case AdjudicatedVerdict.NOT_DUPLICATE:
            verdict = Verdict.NOT_DUPLICATE
        case AdjudicatedVerdict.UNCERTAIN:
            verdict = Verdict.UNCERTAIN

    advice: ConsolidationAdvice | None = None
    if verdict is Verdict.DUPLICATE:
        advice = ConsolidationAdvice(
            recommended=adjudication.consolidation_recommended,
            exclusion=adjudication.exclusion,
            rationale=adjudication.rationale,
        )

    return Finding(
        left=left.unit,
        right=right.unit,
        metrics=metrics,
        verdict=verdict,
        advice=advice,
        rationale=adjudication.behavior_summary,
    )


@dataclass
class AnthropicAdjudicator:
    """Adjudicates via the Anthropic API with schema-validated structured output (D11).

    Every failure path collapses to ``None``. That is not laziness about error handling — it is
    the precision law: when in doubt, we discard the pair and say nothing to the customer.
    """

    client: Anthropic
    model: str = field(default_factory=lambda: os.environ.get("ANTHROPIC_MODEL", DEFAULT_MODEL))
    budget: TokenBudget = field(default_factory=TokenBudget)
    max_tokens: int = 2048

    @property
    def name(self) -> str:
        return f"anthropic_adjudicator_v1:{self.model}"

    def adjudicate(self, left: LoadedUnit, right: LoadedUnit) -> Adjudication | None:
        self.budget.check()
        _nonce, message = build_user_message(
            left.unit.location, left.text, right.unit.location, right.text
        )

        try:
            response = self.client.messages.parse(
                model=self.model,
                max_tokens=self.max_tokens,
                system=SYSTEM_PROMPT,
                output_format=Adjudication,
                messages=[{"role": "user", "content": message}],
            )
        except Exception:
            return None

        usage = getattr(response, "usage", None)
        if usage is not None:
            self.budget.record(
                getattr(usage, "input_tokens", 0) or 0,
                getattr(usage, "output_tokens", 0) or 0,
            )

        # A safety refusal is a legitimate outcome, not an exception. Discard and move on.
        if getattr(response, "stop_reason", None) == "refusal":
            return None

        parsed = getattr(response, "parsed_output", None)
        if not isinstance(parsed, Adjudication):
            return None
        return parsed
