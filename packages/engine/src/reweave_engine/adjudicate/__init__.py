"""LLM adjudication: strict rubric, JSON schemas, injection-safe wrapping.

Phase 1. Implements D5 stage 3 under the D11 injection law.
"""

from reweave_engine.adjudicate.adjudicator import (
    DEFAULT_MODEL,
    DEFAULT_TOKEN_BUDGET,
    Adjudicator,
    AnthropicAdjudicator,
    BudgetExhausted,
    TokenBudget,
    to_finding,
)
from reweave_engine.adjudicate.prompt import (
    MAX_UNIT_CHARS,
    SYSTEM_PROMPT,
    build_user_message,
)
from reweave_engine.adjudicate.schema import (
    AdjudicatedVerdict,
    Adjudication,
    Confidence,
    json_schema,
)

__all__ = [
    "DEFAULT_MODEL",
    "DEFAULT_TOKEN_BUDGET",
    "MAX_UNIT_CHARS",
    "SYSTEM_PROMPT",
    "AdjudicatedVerdict",
    "Adjudication",
    "Adjudicator",
    "AnthropicAdjudicator",
    "BudgetExhausted",
    "Confidence",
    "TokenBudget",
    "build_user_message",
    "json_schema",
    "to_finding",
]
