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
from collections import Counter
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

TEST_MARKERS: Final[tuple[str, ...]] = (
    "/test/",
    "/tests/",
    "/spec/",
    "/__tests__/",
    "/fixtures/",
    "test_",
    "_test.",
    ".test.",
    ".spec.",
    "conftest.py",
)

#: Diversity caps. Ranking purely by similarity produces a monoculture: the first run of this
#: script against date-fns returned 23 of 60 candidates from a single locale file, and against
#: httpx 26 of 60 from `_client.py`. A corpus of forty copies of one pattern measures one
#: pattern. These caps trade a little similarity for a lot of coverage.
MAX_PER_CHUNK: Final = 2
MAX_PER_FILE_PAIR: Final = 3
MAX_PER_FILE: Final = 6

#: Similarity bands, filled round-robin. Without this, everything lands at the top of the range
#: and we never see the 0.6-0.8 band where the interesting judgment calls live.
BANDS: Final[tuple[float, ...]] = (0.55, 0.65, 0.75, 0.85, 0.95)


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


def is_test_path(path: str) -> bool:
    normalized = "/" + path.replace("\\", "/")
    return any(marker in normalized for marker in TEST_MARKERS)


def collect(root: Path, include_tests: bool) -> list[Chunk]:
    chunks: list[Chunk] = []
    for path in root.rglob("*"):
        if not path.is_file() or any(part in SKIP_DIRS for part in path.parts):
            continue
        language = EXTENSIONS.get(path.suffix)
        if not language:
            continue
        relative = str(path.relative_to(root))
        if not include_tests and is_test_path(relative):
            continue
        chunks.extend(extract_chunks(path, root, language))
    return chunks


def _chunk_key(chunk: Chunk) -> str:
    return f"{chunk.path}:{chunk.start_line}"


def select_diverse(
    scored: list[tuple[float, Chunk, Chunk]], limit: int
) -> list[tuple[float, Chunk, Chunk]]:
    """Pick a spread of candidates instead of the top-N by similarity.

    Ranking by similarity alone returns whatever pattern the repository repeats most, which is
    one data point photocopied N times. We cap how often any chunk, file, or file-pair may appear
    and fill similarity bands round-robin.
    """
    by_band: dict[float, list[tuple[float, Chunk, Chunk]]] = {band: [] for band in BANDS}
    for item in sorted(scored, key=lambda i: i[0], reverse=True):
        band = max(b for b in BANDS if item[0] >= b)
        by_band[band].append(item)

    chunk_counts: Counter[str] = Counter()
    file_counts: Counter[str] = Counter()
    file_pair_counts: Counter[tuple[str, str]] = Counter()
    selected: list[tuple[float, Chunk, Chunk]] = []

    # Round-robin across bands so a dense band cannot crowd out a sparse one.
    cursors = dict.fromkeys(BANDS, 0)
    while len(selected) < limit:
        progressed = False
        for band in BANDS:
            if len(selected) >= limit:
                break
            candidates = by_band[band]
            while cursors[band] < len(candidates):
                similarity, left, right = candidates[cursors[band]]
                cursors[band] += 1
                file_pair = tuple(sorted((left.path, right.path)))
                if (
                    chunk_counts[_chunk_key(left)] >= MAX_PER_CHUNK
                    or chunk_counts[_chunk_key(right)] >= MAX_PER_CHUNK
                    or file_pair_counts[file_pair] >= MAX_PER_FILE_PAIR  # pyright: ignore[reportArgumentType]
                    or file_counts[left.path] >= MAX_PER_FILE
                    or file_counts[right.path] >= MAX_PER_FILE
                ):
                    continue
                chunk_counts[_chunk_key(left)] += 1
                chunk_counts[_chunk_key(right)] += 1
                file_counts[left.path] += 1
                file_counts[right.path] += 1
                file_pair_counts[file_pair] += 1  # pyright: ignore[reportArgumentType]
                selected.append((similarity, left, right))
                progressed = True
                break
        if not progressed:
            break

    return selected


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="local checkout to mine")
    parser.add_argument("--repo", required=True, help="canonical repo URL, recorded as a pointer")
    parser.add_argument("--commit", required=True, help="pinned commit SHA of the checkout")
    parser.add_argument("--license", required=True, help="SPDX id of the source repo")
    parser.add_argument("--limit", type=int, default=50, help="max candidates to emit")
    parser.add_argument("--out", type=Path, help="output path (default: inbox/<repo>.jsonl)")
    parser.add_argument(
        "--include-tests",
        action="store_true",
        help="mine test files too (off by default: tests are a population we would never "
        "remediate, and they swamp the candidate list)",
    )
    args = parser.parse_args(argv)

    root: Path = args.path.expanduser().resolve()
    chunks = collect(root, include_tests=args.include_tests)
    print(f"extracted {len(chunks)} chunks from {root}")

    scored: list[tuple[float, Chunk, Chunk]] = []
    for left, right in itertools.combinations(chunks, 2):
        if left.path == right.path and left.start_line == right.start_line:
            continue
        similarity = structural_similarity(left.text, right.text).value
        if MIN_SIMILARITY <= similarity <= MAX_SIMILARITY:
            scored.append((similarity, left, right))

    selected = select_diverse(scored, args.limit)
    print(f"scored {len(scored)} candidate pairs, selected {len(selected)} diverse")

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
