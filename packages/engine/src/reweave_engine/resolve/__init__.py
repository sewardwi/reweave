"""Imports to symbol references to a conservative call graph.

Unresolved references are counted, never guessed: remediation refuses to rewrite call sites in
files whose references we could not fully resolve (see PLAN.md §4).
"""

from reweave_engine.resolve.graph import (
    Definition,
    Reference,
    SymbolGraph,
    build_symbol_graph,
)
from reweave_engine.resolve.imports import (
    FileImports,
    ImportedName,
    Unresolved,
    UnresolvedReason,
    extract_imports,
    resolve_specifier,
)

__all__ = [
    "Definition",
    "FileImports",
    "ImportedName",
    "Reference",
    "SymbolGraph",
    "Unresolved",
    "UnresolvedReason",
    "build_symbol_graph",
    "extract_imports",
    "resolve_specifier",
]
