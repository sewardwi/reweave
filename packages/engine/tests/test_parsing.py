"""Code-unit extraction: names, spans, and the things we deliberately skip."""

from reweave_engine.parsing import (
    content_hash,
    extract_units,
    language_for_path,
)
from reweave_shared import Language

PY_SOURCE = """
class Client:
    def send(self, request):
        prepared = self.prepare(request)
        return self.transport.handle(prepared)

    async def asend(self, request):
        prepared = self.prepare(request)
        return await self.transport.ahandle(prepared)


def module_level(a, b):
    total = a + b
    return total


def one_liner(x): return x
"""

TS_SOURCE = """
export function formatMoney(value: number): string {
  const rounded = Math.round(value * 100) / 100;
  return rounded.toFixed(2);
}

export const toSlug = (title: string): string => {
  const lowered = title.toLowerCase();
  return lowered.replace(/[^a-z0-9]+/g, '-');
};

items.forEach(function (item) {
  console.log(item);
  console.log(item.id);
});
"""


class TestLanguageDetection:
    def test_maps_known_extensions(self) -> None:
        assert language_for_path("a/b.py") is Language.PYTHON
        assert language_for_path("a/b.tsx") is Language.TYPESCRIPT
        assert language_for_path("a/b.mjs") is Language.JAVASCRIPT

    def test_returns_none_for_unsupported(self) -> None:
        # A wrong grammar yields a plausible-looking wrong parse, so we decline instead.
        assert language_for_path("a/b.rs") is None
        assert language_for_path("README.md") is None


class TestPythonExtraction:
    def test_qualifies_methods_with_their_class(self) -> None:
        names = {u.unit.name for u in extract_units(PY_SOURCE, "httpx/_client.py")}
        assert "Client.send" in names
        assert "Client.asend" in names
        assert "module_level" in names

    def test_skips_units_below_the_line_floor(self) -> None:
        names = {u.unit.name for u in extract_units(PY_SOURCE, "x.py")}
        assert "one_liner" not in names

    def test_spans_are_one_indexed_and_inclusive(self) -> None:
        units = {u.unit.name: u for u in extract_units(PY_SOURCE, "x.py")}
        send = units["Client.send"]
        assert send.unit.span.start_line == 3
        assert send.unit.span.end_line == 5
        assert send.text.startswith("def send")


class TestTypeScriptExtraction:
    def test_extracts_declarations_and_named_arrow_functions(self) -> None:
        names = {u.unit.name for u in extract_units(TS_SOURCE, "src/money.ts")}
        assert "formatMoney" in names
        assert "toSlug" in names

    def test_skips_anonymous_callbacks(self) -> None:
        """We cannot write a useful finding about a nameless callback."""
        units = extract_units(TS_SOURCE, "src/money.ts")
        assert all(u.unit.name for u in units)
        assert len(units) == 2

    def test_tsx_uses_the_tsx_grammar(self) -> None:
        """JSX only parses under the TSX grammar; the plain TypeScript one chokes on it."""
        source = """
export function Badge({ label }: Props) {
  const cls = label ? 'on' : 'off';
  return <span className={cls}>{label}</span>;
}
"""
        units = extract_units(source, "src/Badge.tsx")
        assert [u.unit.name for u in units] == ["Badge"]


class TestRobustness:
    def test_unsupported_extension_yields_nothing(self) -> None:
        assert extract_units("fn main() {}", "src/main.rs") == []

    def test_unparseable_input_does_not_raise(self) -> None:
        # A scan that dies on one malformed file in a 300k-line repo is useless.
        assert extract_units("def broken(:\n  ???", "x.py") is not None

    def test_extraction_is_deterministic(self) -> None:
        first = [(u.unit.name, u.unit.content_hash) for u in extract_units(PY_SOURCE, "x.py")]
        second = [(u.unit.name, u.unit.content_hash) for u in extract_units(PY_SOURCE, "x.py")]
        assert first == second

    def test_content_hash_is_over_raw_text(self) -> None:
        """Raw, not normalized: this is an embedding cache key, and two units that normalize
        alike must not share an embedding."""
        units = {u.unit.name: u for u in extract_units(PY_SOURCE, "x.py")}
        assert units["Client.send"].unit.content_hash == content_hash(units["Client.send"].text)
        assert units["Client.send"].unit.content_hash != units["Client.asend"].unit.content_hash
