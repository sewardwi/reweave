"""Normalization must be blind to renaming and sensitive to behavior.

Each test here corresponds to a real false positive or false negative from the corpus. If one
starts failing, a specific customer-visible mistake has come back.
"""

from reweave_engine.normalize import (
    IDENTIFIER_PLACEHOLDER,
    normalize_source,
    shingles,
    structural_hash,
)
from reweave_shared import Language

PY = Language.PYTHON
TS = Language.TYPESCRIPT


def h(source: str, language: Language = PY, *, indexed: bool = True) -> str:
    return structural_hash(normalize_source(source, language, indexed=indexed))


class TestRenameInvariance:
    def test_python_parameter_renames_collapse(self) -> None:
        a = (
            "def clamp(value, low, high):\n"
            "    if value < low:\n        return low\n    return value"
        )
        b = (
            "def bound(n, minimum, maximum):\n"
            "    if n < minimum:\n        return minimum\n    return n"
        )
        assert h(a) == h(b)

    def test_typescript_renames_collapse(self) -> None:
        a = "function formatCurrency(amount: number){ const r = Math.round(amount); return r; }"
        b = "function formatMoney(value: number){ const c = Math.round(value); return c; }"
        assert h(a, TS) == h(b, TS)

    def test_comments_and_docstrings_are_ignored(self) -> None:
        a = "def f(a):\n    # add one\n    return a + 1"
        b = "def f(a):\n    return a + 1"
        assert h(a) == h(b)


class TestBehaviorSensitivity:
    """Every case below was a false positive for the lexical baseline."""

    def test_inclusive_vs_exclusive_bounds(self) -> None:
        assert h("def f(v,lo,hi):\n    return lo <= v <= hi") != h(
            "def f(v,lo,hi):\n    return lo < v < hi"
        )

    def test_argument_order_in_comparators(self) -> None:
        """Ascending vs descending sort. Flat placeholders cannot see this at all."""
        asc = "function s(i){ return [...i].sort((a,b)=>a-b); }"
        desc = "function s(i){ return [...i].sort((a,b)=>b-a); }"
        assert h(asc, TS) != h(desc, TS)

    def test_flat_placeholders_would_miss_argument_order(self) -> None:
        """The ablation, pinned as a test so the design decision cannot silently regress."""
        asc = "function s(i){ return [...i].sort((a,b)=>a-b); }"
        desc = "function s(i){ return [...i].sort((a,b)=>b-a); }"
        assert h(asc, TS, indexed=False) == h(desc, TS, indexed=False)

    def test_nullish_vs_logical_or(self) -> None:
        assert h("function f(v,d){ return v ?? d; }", TS) != h(
            "function f(v,d){ return v || d; }", TS
        )

    def test_strict_vs_loose_equality(self) -> None:
        assert h("function f(a,b){ return a === b; }", TS) != h(
            "function f(a,b){ return a == b; }", TS
        )

    def test_boolean_literals_survive(self) -> None:
        assert h("def t(a):\n    return True") != h("def t(a):\n    return False")


class TestTokenStream:
    def test_identifiers_are_numbered_by_first_occurrence(self) -> None:
        tokens = normalize_source("def f(alpha, beta):\n    return alpha", PY)
        assert f"{IDENTIFIER_PLACEHOLDER}0" in tokens
        assert f"{IDENTIFIER_PLACEHOLDER}1" in tokens
        assert "alpha" not in tokens
        assert "beta" not in tokens

    def test_operators_are_preserved_verbatim(self) -> None:
        tokens = normalize_source("def f(a,b):\n    return a <= b", PY)
        assert "<=" in tokens

    def test_normalization_is_deterministic(self) -> None:
        source = "def f(a,b):\n    return a + b"
        assert normalize_source(source, PY) == normalize_source(source, PY)


class TestShingles:
    def test_short_streams_yield_one_shingle(self) -> None:
        assert shingles(["a", "b"], width=4) == {"a b"}

    def test_empty_stream_yields_nothing(self) -> None:
        assert shingles([], width=4) == set()

    def test_window_count_is_correct(self) -> None:
        assert len(shingles(["a", "b", "c", "d", "e"], width=4)) == 2
