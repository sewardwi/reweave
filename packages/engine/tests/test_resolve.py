"""Call-site resolution, and the property that matters more than coverage: never guess.

Several tests below assert that we *miss* a call site. That is the point. A construct we cannot
follow must mark its file unresolved so Phase 4 declines to rewrite it — the failure mode we are
protecting against is a confident wrong answer, not an incomplete one.
"""

from __future__ import annotations

from reweave_engine.resolve import (
    UnresolvedReason,
    build_symbol_graph,
    extract_imports,
    resolve_specifier,
)
from reweave_shared import Language

TS_FILES = {
    "src/money.ts": """
export function formatMoney(value: number): string {
  const rounded = Math.round(value * 100) / 100;
  return rounded.toFixed(2);
}
""",
    "src/cart.ts": """
import { formatMoney } from './money';
export function renderTotal(items: Item[]): string {
  const total = items.length;
  return formatMoney(total);
}
""",
    "src/invoice.ts": """
import { formatMoney as fmt } from './money';
export function renderInvoice(x: number): string {
  const label = fmt(x);
  return label;
}
""",
}

PY_FILES = {
    "pkg/money.py": """
def format_money(value):
    rounded = round(value * 100) / 100
    return f"{rounded:.2f}"
""",
    "pkg/cart.py": """
from .money import format_money

def render_total(items):
    total = len(items)
    return format_money(total)
""",
    "pkg/invoice.py": """
from pkg.money import format_money as fmt

def render_invoice(x):
    label = fmt(x)
    return label
""",
}


class TestSpecifierResolution:
    def test_relative_ts_resolves_through_extensions(self) -> None:
        known = frozenset({"src/money.ts"})
        path, reason = resolve_specifier("./money", "src/cart.ts", known, Language.TYPESCRIPT)
        assert path == "src/money.ts"
        assert reason is None

    def test_relative_ts_resolves_to_index_file(self) -> None:
        known = frozenset({"src/money/index.ts"})
        path, _ = resolve_specifier("./money", "src/cart.ts", known, Language.TYPESCRIPT)
        assert path == "src/money/index.ts"

    def test_parent_traversal(self) -> None:
        known = frozenset({"src/lib/money.ts"})
        path, _ = resolve_specifier("../lib/money", "src/ui/cart.ts", known, Language.TYPESCRIPT)
        assert path == "src/lib/money.ts"

    def test_bare_specifier_is_declined_not_guessed(self) -> None:
        """A tsconfig `paths` alias and an npm package look identical without build config."""
        path, reason = resolve_specifier(
            "@app/money", "src/cart.ts", frozenset(), Language.TYPESCRIPT
        )
        assert path is None
        assert reason is UnresolvedReason.PATH_ALIAS

    def test_missing_relative_target_is_reported(self) -> None:
        path, reason = resolve_specifier("./gone", "src/cart.ts", frozenset(), Language.TYPESCRIPT)
        assert path is None
        assert reason is UnresolvedReason.MISSING_TARGET

    def test_python_relative_import(self) -> None:
        known = frozenset({"pkg/money.py"})
        path, _ = resolve_specifier(".money", "pkg/cart.py", known, Language.PYTHON)
        assert path == "pkg/money.py"

    def test_python_package_init(self) -> None:
        known = frozenset({"pkg/money/__init__.py"})
        path, _ = resolve_specifier("pkg.money", "app/main.py", known, Language.PYTHON)
        assert path == "pkg/money/__init__.py"

    def test_python_third_party_is_external(self) -> None:
        path, reason = resolve_specifier("httpx", "pkg/cart.py", frozenset(), Language.PYTHON)
        assert path is None
        assert reason is UnresolvedReason.EXTERNAL_PACKAGE


class TestImportExtraction:
    def test_named_and_aliased_ts_imports(self) -> None:
        result = extract_imports(TS_FILES["src/invoice.ts"], "src/invoice.ts", Language.TYPESCRIPT)
        assert [(i.local_name, i.source_name) for i in result.imports] == [("fmt", "formatMoney")]

    def test_dynamic_import_is_recorded(self) -> None:
        source = "export async function lazy(n: string) {\n  return await import(n);\n}"
        result = extract_imports(source, "src/lazy.ts", Language.TYPESCRIPT)
        assert [u.reason for u in result.unresolved] == [UnresolvedReason.DYNAMIC_IMPORT]

    def test_static_import_call_is_not_flagged(self) -> None:
        source = "const m = require('./money');\nexport function f() { return m; }"
        result = extract_imports(source, "src/f.js", Language.JAVASCRIPT)
        assert result.unresolved == []

    def test_star_reexport_is_recorded(self) -> None:
        result = extract_imports("export * from './money';", "src/index.ts", Language.TYPESCRIPT)
        assert [u.reason for u in result.unresolved] == [UnresolvedReason.STAR_REEXPORT]

    def test_python_wildcard_is_recorded(self) -> None:
        result = extract_imports("from .money import *", "pkg/star.py", Language.PYTHON)
        assert [u.reason for u in result.unresolved] == [UnresolvedReason.WILDCARD_IMPORT]

    def test_unparseable_input_does_not_raise(self) -> None:
        assert extract_imports("import { from", "src/x.ts", Language.TYPESCRIPT) is not None


class TestSymbolGraph:
    def test_finds_call_sites_across_files(self) -> None:
        graph = build_symbol_graph(TS_FILES)
        assert graph.call_site_count("src/money.ts", "formatMoney") == 2

    def test_follows_import_aliases(self) -> None:
        """`import { formatMoney as fmt }` then `fmt(x)` is a call site of formatMoney."""
        graph = build_symbol_graph(TS_FILES)
        callers = {ref.from_path for ref in graph.call_sites("src/money.ts", "formatMoney")}
        assert callers == {"src/cart.ts", "src/invoice.ts"}

    def test_python_relative_and_absolute_imports(self) -> None:
        graph = build_symbol_graph(PY_FILES)
        callers = {ref.from_path for ref in graph.call_sites("pkg/money.py", "format_money")}
        assert callers == {"pkg/cart.py", "pkg/invoice.py"}

    def test_recursive_calls_are_not_call_sites(self) -> None:
        files = {
            "pkg/f.py": (
                "def fact(n):\n    if n <= 1:\n        return 1\n    return n * fact(n - 1)\n"
            )
        }
        graph = build_symbol_graph(files)
        assert graph.call_site_count("pkg/f.py", "fact") == 0

    def test_method_calls_are_out_of_scope_not_unresolved(self) -> None:
        """Counting every `self.x()` as unresolved would bury the genuine holes."""
        files = {
            "pkg/c.py": (
                "class Client:\n"
                "    def send(self, request):\n"
                "        prepared = self.prepare(request)\n"
                "        return prepared\n"
            )
        }
        graph = build_symbol_graph(files)
        assert graph.unresolved == []
        assert graph.is_fully_resolved("pkg/c.py")


class TestNeverGuess:
    """The load-bearing property: a hole we cannot see through marks the file unresolved."""

    def test_wildcard_import_hides_a_call_and_says_so(self) -> None:
        files = dict(PY_FILES)
        files["pkg/star.py"] = (
            "from .money import *\n\ndef render(x):\n    return format_money(x)\n"
        )
        graph = build_symbol_graph(files)

        # We genuinely miss this call site...
        assert "pkg/star.py" not in {
            ref.from_path for ref in graph.call_sites("pkg/money.py", "format_money")
        }
        # ...and we know it, so Phase 4 will not rewrite this file.
        assert not graph.is_fully_resolved("pkg/star.py")

    def test_namespace_import_hides_a_call_and_says_so(self) -> None:
        files = dict(PY_FILES)
        files["pkg/ns.py"] = (
            "import pkg.money\n\ndef render(x):\n    return pkg.money.format_money(x)\n"
        )
        graph = build_symbol_graph(files)
        assert not graph.is_fully_resolved("pkg/ns.py")

    def test_ts_namespace_import_is_unresolved(self) -> None:
        files = dict(TS_FILES)
        files["src/ns.ts"] = (
            "import * as money from './money';\n"
            "export function r(x: number) { return money.formatMoney(x); }"
        )
        graph = build_symbol_graph(files)
        assert not graph.is_fully_resolved("src/ns.ts")

    def test_clean_files_stay_fully_resolved(self) -> None:
        graph = build_symbol_graph(TS_FILES)
        assert all(graph.is_fully_resolved(path) for path in TS_FILES)

    def test_unresolved_records_carry_a_reason_and_location(self) -> None:
        files = {"src/lazy.ts": "export async function f(n: string) {\n  return import(n);\n}"}
        graph = build_symbol_graph(files)
        assert len(graph.unresolved) == 1
        item = graph.unresolved[0]
        assert item.reason is UnresolvedReason.DYNAMIC_IMPORT
        assert item.path == "src/lazy.ts"
        assert item.line > 0

    def test_graph_is_deterministic(self) -> None:
        first = build_symbol_graph(TS_FILES)
        second = build_symbol_graph(TS_FILES)
        assert first.references == second.references
        assert first.unresolved == second.unresolved
