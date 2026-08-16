"""AST normalization: erase names, keep behavior (D5 stage 1).

The whole trick is asymmetry. We want to be **blind to renaming** — `formatCurrency(amount)` and
`formatMoney(value)` are the same function — while staying **sensitive to behavior** — `a <= b`
and `a < b` are not.

The lexical baseline could not do both. Its normalizer replaced every identifier-shaped token
with a placeholder, which also flattened the distinctions that matter, and it scored four of its
false positives on exactly that: inverted sort comparators, inclusive versus exclusive bounds,
`==` versus `===`.

tree-sitter gives us most of the distinction for free. Identifiers and literals are *named* nodes
we can erase; operators and punctuation arrive as *anonymous* nodes whose type is the token
itself, so keeping every anonymous node preserves `<=`, `??`, `?.`, and `!==` while `amount` and
`value` both become a placeholder. Booleans, `null`, and `undefined` survive for the same reason
— they are anonymous token types, so `return true` and `return false` never collide.

**Identifiers are alpha-renamed by first occurrence, not flattened.** Erasing every name to one
`ID` also erases argument order, and `(a, b) => a - b` and `(a, b) => b - a` collapse together —
an ascending and a descending comparator scoring as identical. Numbering distinct names in order
of first appearance (`ID0`, `ID1`, …) keeps full rename-invariance, because the numbering depends
only on position, while preserving the data-flow shape that tells those two comparators apart.
"""

from __future__ import annotations

import hashlib
from typing import Final

from tree_sitter import Node

from reweave_engine.parsing.languages import get_parser
from reweave_shared import Language

#: Named node types that carry a programmer-chosen name. Erased to a placeholder.
_IDENTIFIER_TYPES: Final[frozenset[str]] = frozenset(
    {
        "identifier",
        "property_identifier",
        "type_identifier",
        "field_identifier",
        "shorthand_property_identifier",
        "shorthand_property_identifier_pattern",
        "statement_identifier",
        "namespace_import",
        "label_identifier",
    }
)

#: Named node types holding a value. Erased: the *presence* of a literal is structural, its
#: content usually is not. Booleans and null are excluded on purpose — see _LITERAL_KEEP.
_LITERAL_TYPES: Final[frozenset[str]] = frozenset(
    {
        "string",
        "string_fragment",
        "template_string",
        "integer",
        "float",
        "number",
        "concatenated_string",
        "regex",
        "regex_pattern",
        "char",
    }
)

#: Dropped with their entire subtree. Comments are not behavior, and including them lets a
#: docstring difference mask a code difference (or vice versa).
_SKIP_TYPES: Final[frozenset[str]] = frozenset({"comment", "line_comment", "block_comment"})

IDENTIFIER_PLACEHOLDER: Final = "ID"
LITERAL_PLACEHOLDER: Final = "LIT"

#: Distinct names beyond this many collapse to the unindexed placeholder. Without a cap, a
#: forty-variable function produces forty unique tokens and matches only itself, trading away
#: recall for a precision we do not need at that depth.
DEFAULT_MAX_INDEXED: Final = 12


def normalize_node(
    node: Node,
    source: bytes,
    *,
    indexed: bool = True,
    max_indexed: int = DEFAULT_MAX_INDEXED,
) -> list[str]:
    """Pre-order walk producing the structural token sequence for a subtree.

    Set ``indexed=False`` for the flat placeholder behavior, which exists so the two schemes can
    be compared on the benchmark rather than argued about.
    """
    out: list[str] = []
    names: dict[str, str] = {}
    stack: list[Node] = [node]

    while stack:
        current = stack.pop()
        node_type = current.type

        if node_type in _SKIP_TYPES:
            continue

        if node_type in _IDENTIFIER_TYPES:
            if not indexed:
                out.append(IDENTIFIER_PLACEHOLDER)
                continue
            raw = source[current.start_byte : current.end_byte].decode("utf-8", errors="replace")
            placeholder = names.get(raw)
            if placeholder is None:
                placeholder = (
                    f"{IDENTIFIER_PLACEHOLDER}{len(names)}"
                    if len(names) < max_indexed
                    else IDENTIFIER_PLACEHOLDER
                )
                names[raw] = placeholder
            out.append(placeholder)
            continue

        if node_type in _LITERAL_TYPES:
            out.append(LITERAL_PLACEHOLDER)
            continue

        # Anonymous nodes are the literal tokens: operators, punctuation, keywords. Keeping
        # them verbatim is what makes this normalizer behavior-sensitive.
        out.append(node_type)

        # Reversed so the pre-order sequence reads left-to-right despite the stack.
        stack.extend(reversed(current.children))

    return out


def normalize_source(
    source: str,
    language: Language,
    *,
    tsx: bool = False,
    indexed: bool = True,
) -> list[str]:
    """Normalize a standalone snippet.

    Snippets extracted mid-file (a method without its class) may not parse as a whole module;
    tree-sitter is error-tolerant and produces ERROR nodes rather than raising, which normalize
    to a stable token either way.
    """
    parser = get_parser(language, tsx=tsx)
    data = source.encode("utf-8")
    tree = parser.parse(data)
    return normalize_node(tree.root_node, data, indexed=indexed)


def structural_hash(tokens: list[str]) -> str:
    """Exact structural identity. Two units with the same hash differ only in names, literals,
    comments, and whitespace."""
    joined = " ".join(tokens)
    return "ast1:" + hashlib.sha256(joined.encode("utf-8")).hexdigest()


def shingles(tokens: list[str], width: int = 4) -> set[str]:
    """Overlapping n-grams of the normalized stream, for similarity and MinHash.

    Width 4 rather than the baseline's 3: the AST stream is denser than a token stream (every
    node contributes, not just every lexeme), so a wider window is needed before a shingle
    carries real information.
    """
    if len(tokens) < width:
        return {" ".join(tokens)} if tokens else set()
    return {" ".join(tokens[i : i + width]) for i in range(len(tokens) - width + 1)}
