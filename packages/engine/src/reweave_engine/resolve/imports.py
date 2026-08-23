"""Import extraction and module resolution.

This is the layer that decides what "who calls this function?" can even mean. Everything
downstream — blast-radius ranking, and in Phase 4 the decision to rewrite a call site — rests on
it being right, and more importantly on it being **honest about what it could not work out**.

The governing rule is in PLAN.md §4: *unresolved references are counted, never guessed.* Every
construct we cannot follow — a dynamic `import()`, a path alias, a star re-export — produces an
`Unresolved` record with a reason, not a silent omission and not a plausible guess. A missing
call site that we know is missing costs us a slightly wrong blast-radius number. A missing call
site we don't know about costs a customer a broken build.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Final

from tree_sitter import Node

from reweave_engine.parsing.languages import get_parser
from reweave_shared import Language


class UnresolvedReason(StrEnum):
    """Why we could not follow a reference. Each of these is a known hole in the call graph."""

    DYNAMIC_IMPORT = "dynamic_import"
    """`import(expr)` or `require(expr)` with a non-literal specifier."""

    PATH_ALIAS = "path_alias"
    """A bare specifier that is neither relative nor an obvious package: a tsconfig `paths`
    alias, a workspace root, or a monorepo shortcut. Resolving these needs build config we
    deliberately do not parse in v1."""

    STAR_REEXPORT = "star_reexport"
    """`export * from './x'` — the exported names are not visible without following the chain."""

    WILDCARD_IMPORT = "wildcard_import"
    """Python `from x import *`. Same problem."""

    NAMESPACE_IMPORT = "namespace_import"
    """`import * as m from './x'` or Python `import pkg.mod`, where the target is **inside the
    repository**. Calls arrive as `m.foo()`, which v1 does not follow, so a symbol we track may
    have callers we cannot see."""

    EXTERNAL_PACKAGE = "external_package"
    """Resolves outside the repository. Recorded for the counts, but **not** a hole in our graph:
    a third-party package cannot define or call the repo-local symbols we track, so it never
    blocks remediation."""

    MISSING_TARGET = "missing_target"
    """A relative specifier that points at no file we can find."""


@dataclass(frozen=True, slots=True)
class ImportedName:
    """A name brought into a file, and where it came from."""

    local_name: str
    """The name as used in this file (after `as` aliasing)."""

    source_name: str
    """The name as exported by the target module. Equal to ``local_name`` when not aliased."""

    specifier: str
    """The raw module specifier, e.g. ``./money`` or ``httpx._client``."""

    line: int


@dataclass(frozen=True, slots=True)
class Unresolved:
    """Something we declined to follow, recorded rather than dropped."""

    reason: UnresolvedReason
    specifier: str
    path: str
    line: int


@dataclass(frozen=True, slots=True)
class NamespaceImport:
    """A whole-module import (`import * as m`, `import pkg.mod`), pending classification.

    Whether this is a hole depends on where the specifier points, and that needs the file list —
    which the extractor does not have. The graph pass decides: inside the repo it becomes a
    `NAMESPACE_IMPORT` hole, outside it is merely an external package.
    """

    specifier: str
    line: int


@dataclass(frozen=True, slots=True)
class FileImports:
    imports: list[ImportedName]
    unresolved: list[Unresolved]
    namespace_imports: list[NamespaceImport] = field(default_factory=list[NamespaceImport])


#: Extensions tried, in order, when resolving a relative TS/JS specifier. Mirrors the resolution
#: order bundlers use; getting the order wrong resolves `./x` to `x.js` when `x.ts` exists.
_TS_EXTENSIONS: Final[tuple[str, ...]] = (
    ".ts",
    ".tsx",
    ".mts",
    ".cts",
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
)
_INDEX_STEMS: Final[tuple[str, ...]] = ("index",)


def _text(node: Node, source: bytes) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _walk(node: Node) -> list[Node]:
    out: list[Node] = []
    stack = [node]
    while stack:
        current = stack.pop()
        out.append(current)
        stack.extend(current.children)
    return out


def _strip_quotes(raw: str) -> str:
    if len(raw) >= 2 and raw[0] in "\"'`" and raw[-1] == raw[0]:
        return raw[1:-1]
    return raw


def _js_imports(root: Node, source: bytes, path: str) -> FileImports:
    imports: list[ImportedName] = []
    unresolved: list[Unresolved] = []
    namespaces: list[NamespaceImport] = []

    for node in _walk(root):
        line = node.start_point[0] + 1

        # `import(...)` and `require(...)` with a computed argument.
        if node.type == "call_expression":
            callee = node.child_by_field_name("function")
            if callee is None:
                continue
            callee_text = _text(callee, source)
            if callee_text in {"require", "import"}:
                args = node.child_by_field_name("arguments")
                literal = args is not None and any(
                    child.type == "string" for child in args.children
                )
                if not literal:
                    unresolved.append(
                        Unresolved(UnresolvedReason.DYNAMIC_IMPORT, callee_text, path, line)
                    )
            continue

        if node.type != "import_statement" and node.type != "export_statement":
            continue

        source_node = node.child_by_field_name("source")
        if source_node is None:
            continue
        specifier = _strip_quotes(_text(source_node, source))

        # `export * from './x'` — we cannot know which names cross the boundary.
        if node.type == "export_statement" and any(c.type == "*" for c in node.children):
            unresolved.append(Unresolved(UnresolvedReason.STAR_REEXPORT, specifier, path, line))
            continue

        clause_found = False
        for child in _walk(node):
            if child.type == "namespace_import":
                # `import * as ns from 'x'` — usage is `ns.foo`, which we do not track. Whether
                # that hides one of our symbols depends on where 'x' points; the graph decides.
                clause_found = True
                namespaces.append(NamespaceImport(specifier, line))
            elif child.type == "import_specifier" or child.type == "export_specifier":
                clause_found = True
                name_node = child.child_by_field_name("name")
                alias_node = child.child_by_field_name("alias")
                if name_node is None:
                    continue
                source_name = _text(name_node, source)
                local_name = _text(alias_node, source) if alias_node else source_name
                imports.append(ImportedName(local_name, source_name, specifier, line))

        if not clause_found and node.type == "import_statement":
            # Default import: `import money from './money'`. The exported name is the module's
            # default, so the local name is all we have to match on.
            for child in node.children:
                if child.type == "identifier":
                    name = _text(child, source)
                    imports.append(ImportedName(name, "default", specifier, line))

    return FileImports(imports, unresolved, namespaces)


def _python_imports(root: Node, source: bytes, path: str) -> FileImports:
    imports: list[ImportedName] = []
    unresolved: list[Unresolved] = []
    namespaces: list[NamespaceImport] = []

    for node in _walk(root):
        line = node.start_point[0] + 1

        if node.type == "import_from_statement":
            module_node = node.child_by_field_name("module_name")
            specifier = _text(module_node, source) if module_node else ""

            if any(child.type == "wildcard_import" for child in node.children):
                unresolved.append(
                    Unresolved(UnresolvedReason.WILDCARD_IMPORT, specifier, path, line)
                )
                continue

            for child in node.children:
                if child is module_node:
                    continue
                if child.type == "dotted_name":
                    name = _text(child, source)
                    imports.append(ImportedName(name, name, specifier, line))
                elif child.type == "aliased_import":
                    name_node = child.child_by_field_name("name")
                    alias_node = child.child_by_field_name("alias")
                    if name_node is None or alias_node is None:
                        continue
                    source_name = _text(name_node, source)
                    imports.append(
                        ImportedName(_text(alias_node, source), source_name, specifier, line)
                    )

        elif node.type == "import_statement":
            # `import a.b.c` / `import a.b as c` — usage is attribute access (`c.func()`), which
            # v1 does not follow. Only a hole when a.b.c is a repo file; `import ssl` is not.
            for child in node.children:
                if child.type in {"dotted_name", "aliased_import"}:
                    namespaces.append(NamespaceImport(_text(child, source), line))

    return FileImports(imports, unresolved, namespaces)


def extract_imports(source: str, path: str, language: Language) -> FileImports:
    """Parse a file's imports. Never raises: an unparseable file yields nothing."""
    tsx = path.endswith(".tsx")
    parser = get_parser(language, tsx=tsx)
    data = source.encode("utf-8")
    root = parser.parse(data).root_node

    if language is Language.PYTHON:
        return _python_imports(root, data, path)
    return _js_imports(root, data, path)


def resolve_specifier(
    specifier: str,
    importing_path: str,
    known_files: frozenset[str],
    language: Language,
) -> tuple[str | None, UnresolvedReason | None]:
    """Map a module specifier to a repo-relative file path.

    Returns ``(path, None)`` on success or ``(None, reason)`` on a decline. **There is no third
    outcome** — in particular there is no "best guess" — because a wrong edge in the call graph
    is worse than a missing one we can count.
    """
    if language is Language.PYTHON:
        return _resolve_python(specifier, importing_path, known_files)
    return _resolve_js(specifier, importing_path, known_files)


def _candidates_js(base: PurePosixPath) -> list[str]:
    out = [str(base)]
    out += [f"{base}{ext}" for ext in _TS_EXTENSIONS]
    out += [f"{base}/{stem}{ext}" for stem in _INDEX_STEMS for ext in _TS_EXTENSIONS]
    return out


def _resolve_js(
    specifier: str, importing_path: str, known_files: frozenset[str]
) -> tuple[str | None, UnresolvedReason | None]:
    if not specifier.startswith("."):
        # Bare specifier. Could be an npm package or a tsconfig `paths` alias — telling them
        # apart requires build config we do not parse, so we decline rather than guess.
        reason = (
            UnresolvedReason.PATH_ALIAS
            if specifier.startswith("@") or "/" not in specifier
            else UnresolvedReason.EXTERNAL_PACKAGE
        )
        return None, reason

    base = (PurePosixPath(importing_path).parent / specifier).as_posix()
    normalized = PurePosixPath(_normalize(base))
    for candidate in _candidates_js(normalized):
        if candidate in known_files:
            return candidate, None
    return None, UnresolvedReason.MISSING_TARGET


def _resolve_python(
    specifier: str, importing_path: str, known_files: frozenset[str]
) -> tuple[str | None, UnresolvedReason | None]:
    if specifier.startswith("."):
        # Relative: each leading dot is one package level up.
        dots = len(specifier) - len(specifier.lstrip("."))
        remainder = specifier[dots:]
        base = PurePosixPath(importing_path).parent
        for _ in range(dots - 1):
            base = base.parent
        target = base / remainder.replace(".", "/") if remainder else base
    else:
        target = PurePosixPath(specifier.replace(".", "/"))

    normalized = _normalize(target.as_posix())
    for candidate in (f"{normalized}.py", f"{normalized}/__init__.py"):
        if candidate in known_files:
            return candidate, None

    # An absolute specifier that matches no file is almost always a third-party package.
    if specifier.startswith("."):
        return None, UnresolvedReason.MISSING_TARGET
    return None, UnresolvedReason.EXTERNAL_PACKAGE


def _normalize(path: str) -> str:
    """Collapse `.` and `..` segments without touching the filesystem."""
    parts: list[str] = []
    for part in path.split("/"):
        if part in {"", "."}:
            continue
        if part == "..":
            if parts:
                parts.pop()
            continue
        parts.append(part)
    return "/".join(parts)
