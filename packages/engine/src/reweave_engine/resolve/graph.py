"""The conservative call graph (PLAN.md §4).

**What v1 resolves, stated exactly, because the boundary is the product decision:** a reference
is a call to a *bare identifier* — `formatMoney(x)` — where that identifier is either defined at
module level in the same file or imported into it by name. That is it.

**What it does not resolve**, and how each is handled:

* Method and attribute calls (`self.prepare()`, `money.format()`) are **out of scope**, not
  unresolved. The symbols we track are reachable by bare name in our model, so a method call is
  not a hole in the graph — it is a different graph.
* Namespace imports (`import * as m`, Python's `import a.b`) *can* hide a call to a symbol we
  track — but only when the specifier points **inside the repository**. `import ssl` cannot hide
  a caller of our code; `import pkg.money` can. Only the latter is recorded as unresolved.
  Wildcard imports, star re-exports, dynamic `import()`, path aliases, and specifiers that point
  nowhere are always recorded.

The consequence is the load-bearing part: `is_fully_resolved(path)` is `False` for any file
carrying an unresolved record, and Phase 4 may not rewrite call sites in such a file. We would
rather decline to fix a real duplicate than rewrite a file where we can't see every caller.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field

from tree_sitter import Node

from reweave_engine.parsing.extract import extract_units
from reweave_engine.parsing.languages import get_parser, language_for_path
from reweave_engine.resolve.imports import (
    Unresolved,
    UnresolvedReason,
    extract_imports,
    resolve_specifier,
)
from reweave_shared import CodeUnit, Language


@dataclass(frozen=True, slots=True)
class Definition:
    """A named symbol we can talk about, and the unit that defines it."""

    name: str
    path: str
    unit: CodeUnit

    @property
    def key(self) -> tuple[str, str]:
        return (self.path, self.name)


@dataclass(frozen=True, slots=True)
class Reference:
    """A resolved call site: someone calling a definition we know about."""

    name: str
    target_path: str
    from_path: str
    line: int


@dataclass
class SymbolGraph:
    definitions: dict[tuple[str, str], Definition] = field(
        default_factory=dict[tuple[str, str], Definition]
    )
    references: list[Reference] = field(default_factory=list[Reference])
    unresolved: list[Unresolved] = field(default_factory=list[Unresolved])

    def call_sites(self, path: str, name: str) -> list[Reference]:
        """Every resolved call site of a definition, excluding its own recursive calls."""
        return [ref for ref in self.references if ref.target_path == path and ref.name == name]

    def call_site_count(self, path: str, name: str) -> int:
        return len(self.call_sites(path, name))

    def unresolved_for(self, path: str) -> list[Unresolved]:
        return [item for item in self.unresolved if item.path == path]

    def is_fully_resolved(self, path: str) -> bool:
        """May Phase 4 rewrite call sites in this file?

        A single construct that could hide a caller makes the answer no. Deliberately strict: the
        cost of a false ``True`` is a silent break in a customer's build that our test gate may
        not catch.

        External packages are excluded, and that exclusion is load-bearing rather than a
        loosening. A third-party import cannot define or call a repo-local symbol, so counting it
        as a hole blocks essentially every file — measured on httpx, treating `import ssl` as a
        hole left 4 of 60 files remediable, which would make the gate useless and Phase 4 inert.
        """
        return not any(
            item.path == path and item.reason is not UnresolvedReason.EXTERNAL_PACKAGE
            for item in self.unresolved
        )

    @property
    def unresolved_by_reason(self) -> dict[UnresolvedReason, int]:
        counts: dict[UnresolvedReason, int] = defaultdict(int)
        for item in self.unresolved:
            counts[item.reason] += 1
        return dict(counts)


def _walk(node: Node) -> list[Node]:
    out: list[Node] = []
    stack = [node]
    while stack:
        current = stack.pop()
        out.append(current)
        stack.extend(current.children)
    return out


def _called_names(source: str, path: str, language: Language) -> list[tuple[str, int]]:
    """Bare-identifier call sites in a file, as ``(name, line)``.

    Member calls are skipped rather than counted: they belong to a graph we do not build, and
    treating them as unresolved would bury the genuine holes under thousands of `self.x()` calls.
    """
    parser = get_parser(language, tsx=path.endswith(".tsx"))
    data = source.encode("utf-8")
    root = parser.parse(data).root_node

    call_types = {"call"} if language is Language.PYTHON else {"call_expression"}
    found: list[tuple[str, int]] = []
    for node in _walk(root):
        if node.type not in call_types:
            continue
        callee = node.child_by_field_name("function")
        if callee is None or callee.type != "identifier":
            continue
        name = data[callee.start_byte : callee.end_byte].decode("utf-8", errors="replace")
        found.append((name, callee.start_point[0] + 1))
    return found


def build_symbol_graph(files: Mapping[str, str]) -> SymbolGraph:
    """Build the call graph for a set of repo-relative ``path -> source`` files."""
    graph = SymbolGraph()
    known_files = frozenset(files)

    languages: dict[str, Language] = {}
    for path in files:
        language = language_for_path(path)
        if language is not None:
            languages[path] = language

    # Pass 1: definitions.
    for path in languages:
        for extracted in extract_units(files[path], path):
            # The qualified name (`Client.send`) is for humans; resolution matches on the bare
            # name, since that is what a caller writes.
            bare = extracted.unit.name.rsplit(".", 1)[-1]
            graph.definitions.setdefault((path, bare), Definition(bare, path, extracted.unit))

    # Pass 2: imports, with every decline recorded.
    imported: dict[str, dict[str, tuple[str, str]]] = {}
    for path, language in languages.items():
        file_imports = extract_imports(files[path], path, language)
        graph.unresolved.extend(file_imports.unresolved)

        for namespace in file_imports.namespace_imports:
            target, reason = resolve_specifier(namespace.specifier, path, known_files, language)
            if target is not None:
                # Points inside the repo: it really can hide a caller of a symbol we track.
                graph.unresolved.append(
                    Unresolved(
                        UnresolvedReason.NAMESPACE_IMPORT, namespace.specifier, path, namespace.line
                    )
                )
            elif reason is not None and reason is not UnresolvedReason.EXTERNAL_PACKAGE:
                graph.unresolved.append(
                    Unresolved(reason, namespace.specifier, path, namespace.line)
                )

        local: dict[str, tuple[str, str]] = {}
        for item in file_imports.imports:
            target, reason = resolve_specifier(item.specifier, path, known_files, language)
            if target is None:
                if reason is not None:
                    graph.unresolved.append(Unresolved(reason, item.specifier, path, item.line))
                continue
            local[item.local_name] = (target, item.source_name)
        imported[path] = local

    # Pass 3: references.
    for path, language in languages.items():
        local_imports = imported.get(path, {})
        for name, line in _called_names(files[path], path, language):
            target_path: str | None = None
            target_name = name

            if (path, name) in graph.definitions:
                target_path = path
            elif name in local_imports:
                candidate_path, source_name = local_imports[name]
                resolved_name = name if source_name == "default" else source_name
                if (candidate_path, resolved_name) in graph.definitions:
                    target_path = candidate_path
                    target_name = resolved_name

            if target_path is None:
                continue

            definition = graph.definitions[(target_path, target_name)]
            span = definition.unit.span
            if target_path == path and span.start_line <= line <= span.end_line:
                # A recursive call. Real, but not a caller — counting it would inflate blast
                # radius for every recursive helper in the repository.
                continue

            graph.references.append(Reference(target_name, target_path, path, line))

    return graph
