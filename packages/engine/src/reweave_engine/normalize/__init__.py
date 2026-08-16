"""AST normalization: strip identifiers and literals, keep structure (Phase 1, D5 stage 1)."""

from reweave_engine.normalize.ast_normalize import (
    IDENTIFIER_PLACEHOLDER,
    LITERAL_PLACEHOLDER,
    normalize_node,
    normalize_source,
    shingles,
    structural_hash,
)

__all__ = [
    "IDENTIFIER_PLACEHOLDER",
    "LITERAL_PLACEHOLDER",
    "normalize_node",
    "normalize_source",
    "shingles",
    "structural_hash",
]
