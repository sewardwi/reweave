#!/usr/bin/env python
"""Mine candidate duplicate pairs from a checked-out repository, for hand-labeling.

Corpus growth is the bottleneck on every detection claim we will ever make, so this exists to
make the expensive part — a human reading two functions and deciding — as cheap as it can be.
It does the cheap part (finding plausible pairs) and refuses to do the expensive part.

Output goes to ``benchmarks/inbox/`` as unlabeled candidates, never straight into ``corpus/``.
An unlabeled record is not evidence, and the corpus must never contain one.

Function extraction here is regex-based, which is crude and will miss things. That is acceptable
for *candidate generation* — a missed candidate costs us one corpus entry — and is replaced by
tree-sitter in Phase 1. Do not reuse this for anything a customer sees.

Usage:
    python benchmarks/mine_candidates.py ~/src/some-oss-repo \\
        --repo https://github.com/owner/name --commit a1b2c3d --license MIT --limit 40
"""

from __future__ import annotations

import argparse
import itertools
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from reweave_engine.baseline import structural_similarity

INBOX_ROOT = Path(__file__).parent / "inbox"

EXTENSIONS: Final[dict[str, str]] = {
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".py": "python",
}

SKIP_DIRS: Final[frozenset[str]] = frozenset(
    {"node_modules", ".git", "dist", "build", "vendor", "__pycache__", ".venv", "migrations"}
)

#: Candidates below this are noise; above ~0.95 they are usually trivial copy-paste we already
#: have plenty of. The interesting labeling happens in the middle.
MIN_SIMILARITY: Final = 0.55
MAX_SIMILARITY: Final = 0.97
MIN_LINES: Final = 5


@dataclass(frozen=True)
class Chunk:
    path: str
    name: str
    start_line: int
    end_line: int
    language: str
    text: str


def extract_chunks(path: Path, root: Path, language: str) -> list[Chunk]:
    """Split a file into function-ish blocks by indentation/brace heuristics."""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []

    starts: list[int] = []
    for i, line in enumerate(lines):
        stripped = line.lstrip()
        is_def = stripped.startswith(("def ", "async def ", "function ", "export function "))
        is_arrow = "=>" in stripped and stripped.startswith(("const ", "export const "))
        if is_def or is_arrow:
            starts.append(i)

    chunks: list[Chunk] = []
    for idx, start in enumerate(starts):
        end = starts[idx + 1] - 1 if idx + 1 < len(starts) else len(lines) - 1
        if end - start + 1 < MIN_LINES:
            continue
        body = "\n".join(lines[start : end + 1])
        name = lines[start].strip()[:60]
        chunks.append(
            Chunk(
                path=str(path.relative_to(root)),
                name=name,
                start_line=start + 1,
                end_line=end + 1,
                language=language,
                text=body,
            )
        )
    return chunks


def collect(root: Path) -> list[Chunk]:
    chunks: list[Chunk] = []
    for path in root.rglob("*"):
        if not path.is_file() or any(part in SKIP_DIRS for part in path.parts):
            continue
        language = EXTENSIONS.get(path.suffix)
        if language:
            chunks.extend(extract_chunks(path, root, language))
    return chunks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="local checkout to mine")
    parser.add_argument("--repo", required=True, help="canonical repo URL, recorded as a pointer")
    parser.add_argument("--commit", required=True, help="pinned commit SHA of the checkout")
    parser.add_argument("--license", required=True, help="SPDX id of the source repo")
    parser.add_argument("--limit", type=int, default=50, help="max candidates to emit")
    parser.add_argument("--out", type=Path, help="output path (default: inbox/<repo>.jsonl)")
    args = parser.parse_args(argv)

    root: Path = args.path.expanduser().resolve()
    chunks = collect(root)
    print(f"extracted {len(chunks)} chunks from {root}")

    scored: list[tuple[float, Chunk, Chunk]] = []
    for left, right in itertools.combinations(chunks, 2):
        if left.path == right.path and left.start_line == right.start_line:
            continue
        similarity = structural_similarity(left.text, right.text).value
        if MIN_SIMILARITY <= similarity <= MAX_SIMILARITY:
            scored.append((similarity, left, right))

    scored.sort(key=lambda item: item[0], reverse=True)
    selected = scored[: args.limit]

    out = args.out or INBOX_ROOT / f"{args.repo.rstrip('/').split('/')[-1]}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)

    with out.open("w", encoding="utf-8") as fh:
        for rank, (similarity, left, right) in enumerate(selected):
            record = {
                "pair_id": f"mined-{out.stem}-{rank:03d}",
                "split": "train",
                "language": left.language,
                "label": None,  # ← the human fills this in
                "should_consolidate": None,
                "exclusion": None,
                "candidate_similarity": round(similarity, 3),
                "left": _pointer(left, args),
                "right": _pointer(right, args),
                "notes": "",
            }
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"wrote {len(selected)} unlabeled candidates to {out}")
    print("next: python benchmarks/label.py", out)
    return 0


def _pointer(chunk: Chunk, args: argparse.Namespace) -> dict[str, object]:
    return {
        "kind": "pointer",
        "name": chunk.name,
        "repo": args.repo,
        "commit": args.commit,
        "path": chunk.path,
        "start_line": chunk.start_line,
        "end_line": chunk.end_line,
        "license": args.license,
    }


if __name__ == "__main__":
    raise SystemExit(main())
