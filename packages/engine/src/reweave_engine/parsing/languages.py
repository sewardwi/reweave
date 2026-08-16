"""tree-sitter grammar loading and parser reuse (D4).

Parsers are cached per language because constructing one is expensive relative to parsing a
small file, and a full-repository scan builds hundreds of thousands of them otherwise.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import tree_sitter_javascript
import tree_sitter_python
import tree_sitter_typescript
from tree_sitter import Language as TSLanguage
from tree_sitter import Parser

from reweave_shared import Language

#: Extensions we claim to support. Anything absent here is skipped by the scanner rather than
#: guessed at — a wrong grammar produces a plausible-looking wrong parse, which is worse than
#: no parse at all.
EXTENSIONS: dict[str, Language] = {
    ".py": Language.PYTHON,
    ".pyi": Language.PYTHON,
    ".ts": Language.TYPESCRIPT,
    ".tsx": Language.TYPESCRIPT,
    ".mts": Language.TYPESCRIPT,
    ".cts": Language.TYPESCRIPT,
    ".js": Language.JAVASCRIPT,
    ".jsx": Language.JAVASCRIPT,
    ".mjs": Language.JAVASCRIPT,
    ".cjs": Language.JAVASCRIPT,
}


def language_for_path(path: str | Path) -> Language | None:
    """Return the language for a file path, or ``None`` if we do not support it."""
    suffix = Path(path).suffix.lower()
    # .tsx needs the TSX grammar, which differs from plain TypeScript; see get_parser.
    return EXTENSIONS.get(suffix)


def _is_tsx(path: str | Path) -> bool:
    return Path(path).suffix.lower() == ".tsx"


@lru_cache(maxsize=8)
def _load(language: Language, tsx: bool) -> TSLanguage:
    match language:
        case Language.PYTHON:
            return TSLanguage(tree_sitter_python.language())
        case Language.JAVASCRIPT:
            return TSLanguage(tree_sitter_javascript.language())
        case Language.TYPESCRIPT:
            if tsx:
                return TSLanguage(tree_sitter_typescript.language_tsx())
            return TSLanguage(tree_sitter_typescript.language_typescript())


@lru_cache(maxsize=8)
def get_parser(language: Language, tsx: bool = False) -> Parser:
    """Return a cached parser. Callers must not rely on parser state between calls."""
    return Parser(_load(language, tsx))


def parser_for_path(path: str | Path) -> tuple[Language, Parser] | None:
    language = language_for_path(path)
    if language is None:
        return None
    return language, get_parser(language, tsx=_is_tsx(path))
