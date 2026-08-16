"""Extract function and method code units from source files (D4).

A "code unit" is the smallest thing we are willing to talk to a customer about: a named function
or method, with a span precise enough to quote back at them. Anonymous callbacks are deliberately
excluded — we cannot write a useful finding about a lambda buried three levels into a chain, and
including them multiplies the candidate space for no product value.

Names are qualified with their enclosing class (``Client.send``) so that a finding reads the way
a developer would say it out loud.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from tree_sitter import Node

from reweave_engine.parsing.languages import parser_for_path
from reweave_shared import CodeUnit, Language, Span

#: Node types whose body constitutes a code unit, per grammar.
_FUNCTION_NODES: dict[Language, frozenset[str]] = {
    Language.PYTHON: frozenset({"function_definition"}),
    Language.TYPESCRIPT: frozenset(
        {
            "function_declaration",
            "generator_function_declaration",
            "method_definition",
            "function_expression",
            "arrow_function",
        }
    ),
    Language.JAVASCRIPT: frozenset(
        {
            "function_declaration",
            "generator_function_declaration",
            "method_definition",
            "function_expression",
            "arrow_function",
        }
    ),
}

_CLASS_NODES: frozenset[str] = frozenset(
    {"class_definition", "class_declaration", "class", "class_body"}
)

#: Arrow functions and function expressions only become units when bound to a name, e.g.
#: ``const formatMoney = (x) => ...``. These are the parents that supply that name.
_NAMED_BINDING_PARENTS: frozenset[str] = frozenset(
    {"variable_declarator", "public_field_definition", "pair", "assignment"}
)

#: Units shorter than this are noise: one-line getters and re-exports generate enormous numbers
#: of trivially-similar pairs. Config, not policy — the CLI and scan config can override it.
DEFAULT_MIN_LINES = 3


@dataclass(frozen=True, slots=True)
class ExtractedUnit:
    """A parsed code unit plus the source text it came from."""

    unit: CodeUnit
    text: str

    @property
    def line_count(self) -> int:
        return self.unit.span.line_count


def _node_text(node: Node, source: bytes) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _identifier_of(node: Node, source: bytes) -> str | None:
    name_node = node.child_by_field_name("name")
    if name_node is not None:
        return _node_text(name_node, source)
    return None


def _binding_name(node: Node, source: bytes) -> str | None:
    """For arrow functions and function expressions, recover the name they are bound to."""
    parent = node.parent
    if parent is None or parent.type not in _NAMED_BINDING_PARENTS:
        return None
    for field in ("name", "left", "key"):
        target = parent.child_by_field_name(field)
        if target is not None:
            return _node_text(target, source)
    return None


def _enclosing_class(node: Node, source: bytes) -> str | None:
    current = node.parent
    while current is not None:
        if current.type in _CLASS_NODES:
            name = _identifier_of(current, source)
            if name:
                return name
        current = current.parent
    return None


def content_hash(text: str) -> str:
    """Content-addressed key for a unit's *raw* text.

    Raw, not normalized: this is the key an embedding cache is keyed by (D5 stage 2), and two
    units that normalize identically but read differently must not share an embedding. Structural
    identity is a separate concern and lives in ``reweave_engine.fingerprint``.
    """
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _walk(node: Node) -> list[Node]:
    out: list[Node] = []
    stack = [node]
    while stack:
        current = stack.pop()
        out.append(current)
        stack.extend(current.children)
    return out


def extract_units(
    source: str,
    path: str,
    *,
    min_lines: int = DEFAULT_MIN_LINES,
) -> list[ExtractedUnit]:
    """Parse ``source`` and return its named function and method units.

    Returns an empty list for unsupported extensions or unparseable input. A file we cannot
    parse is skipped silently at this layer and counted by the caller: a scan that dies on one
    malformed file in a 300k-line repository is useless.
    """
    resolved = parser_for_path(path)
    if resolved is None:
        return []
    language, parser = resolved

    data = source.encode("utf-8")
    tree = parser.parse(data)
    wanted = _FUNCTION_NODES[language]

    units: list[ExtractedUnit] = []
    for node in _walk(tree.root_node):
        if node.type not in wanted:
            continue

        name = _identifier_of(node, data) or _binding_name(node, data)
        if not name:
            # Anonymous callback. Real, but not something we can write a finding about.
            continue

        start_line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1
        if end_line - start_line + 1 < min_lines:
            continue

        owner = _enclosing_class(node, data)
        qualified = f"{owner}.{name}" if owner else name
        text = _node_text(node, data)

        units.append(
            ExtractedUnit(
                unit=CodeUnit(
                    path=path,
                    span=Span(start_line=start_line, end_line=end_line),
                    language=language,
                    name=qualified,
                    content_hash=content_hash(text),
                ),
                text=text,
            )
        )

    # Stable order: by position in the file. Determinism is a Phase 1 exit criterion, and an
    # unordered walk would reshuffle candidate generation between runs.
    units.sort(key=lambda u: (u.unit.span.start_line, u.unit.span.end_line, u.unit.name))
    return units


def extract_file(
    path: Path, *, min_lines: int = DEFAULT_MIN_LINES, root: Path | None = None
) -> list[ExtractedUnit]:
    """Read and extract a single file. Unreadable files yield nothing."""
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    display = str(path.relative_to(root)) if root else str(path)
    return extract_units(source, display, min_lines=min_lines)
