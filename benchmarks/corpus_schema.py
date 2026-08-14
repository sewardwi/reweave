"""Corpus schema and loader for the pair benchmark (D12).

Two source kinds, for a reason that matters legally as well as technically:

* ``inline`` — pairs we authored. We own them, so the text lives in the repo.
* ``pointer`` — pairs mined from open-source repositories. We store **only** a URL, commit SHA,
  path, and span. Third-party code is never vendored into this proprietary repo; it is fetched
  on demand and cached under ``benchmarks/.cache/`` (gitignored). This keeps us clean on OSS
  license obligations and is the same discipline D10 applies to customer code.

Every pair carries two independent labels:

* ``label`` — are these the same behavior? (the detection question)
* ``should_consolidate`` — should they be merged? (the D16 advisability question)

Labeling both at once costs almost nothing, because the expensive part is reading the code.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from enum import StrEnum
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from reweave_shared import ExclusionRule, Language

CORPUS_ROOT = Path(__file__).parent / "corpus"
CACHE_ROOT = Path(__file__).parent / ".cache"


class Split(StrEnum):
    TRAIN = "train"
    """Tune here. Freely."""

    HOLDOUT = "holdout"
    """Sacred. Evaluated at phase gates only, never in the per-PR loop (see run_bench.py)."""


class PairLabel(StrEnum):
    DUPLICATE = "duplicate"
    NOT_DUPLICATE = "not_duplicate"


class Advisability(StrEnum):
    CONSOLIDATE = "consolidate"
    LEAVE_ALONE = "leave_alone"
    NOT_APPLICABLE = "not_applicable"
    """Only meaningful for pairs labeled ``duplicate``."""


class InlineSource(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: Literal["inline"] = "inline"
    name: str
    text: str = Field(min_length=1)


class PointerSource(BaseModel):
    """A span of third-party code, referenced but not stored."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["pointer"] = "pointer"
    name: str
    repo: str = Field(description="e.g. https://github.com/owner/name")
    commit: str = Field(min_length=7, description="pinned SHA — a branch ref would drift")
    path: str
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    license: str = Field(description="SPDX id of the source repo, recorded at mining time")


Source = InlineSource | PointerSource


class LabeledPair(BaseModel):
    model_config = ConfigDict(frozen=True)

    pair_id: str = Field(min_length=1)
    split: Split
    language: Language
    label: PairLabel
    should_consolidate: Advisability = Advisability.NOT_APPLICABLE
    exclusion: ExclusionRule | None = None
    left: Source = Field(discriminator="kind")
    right: Source = Field(discriminator="kind")
    notes: str = ""

    @model_validator(mode="after")
    def _labels_are_coherent(self) -> Self:
        if self.label is PairLabel.NOT_DUPLICATE:
            if self.should_consolidate is not Advisability.NOT_APPLICABLE:
                msg = f"{self.pair_id}: non-duplicates cannot carry a consolidation label"
                raise ValueError(msg)
        elif self.should_consolidate is Advisability.NOT_APPLICABLE:
            msg = f"{self.pair_id}: duplicates must be labeled consolidate/leave_alone (D16)"
            raise ValueError(msg)

        if self.should_consolidate is Advisability.LEAVE_ALONE and self.exclusion is None:
            msg = f"{self.pair_id}: leave_alone requires naming which D16 rule applies"
            raise ValueError(msg)
        if self.should_consolidate is not Advisability.LEAVE_ALONE and self.exclusion is not None:
            msg = f"{self.pair_id}: exclusion set but pair is not labeled leave_alone"
            raise ValueError(msg)
        return self


def iter_pairs(root: Path = CORPUS_ROOT) -> Iterator[LabeledPair]:
    """Load every ``*.jsonl`` under the corpus root, in stable filename order."""
    for path in sorted(root.rglob("*.jsonl")):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("//"):
                continue
            try:
                yield LabeledPair.model_validate(json.loads(stripped))
            except Exception as exc:
                msg = f"{path}:{lineno}: invalid corpus record: {exc}"
                raise ValueError(msg) from exc


def load_corpus(split: Split | None = None, root: Path = CORPUS_ROOT) -> list[LabeledPair]:
    pairs = list(iter_pairs(root))
    if split is not None:
        pairs = [p for p in pairs if p.split is split]
    return pairs


def resolve_text(source: Source) -> str:
    """Return the source text for a pair side, fetching and caching pointers as needed."""
    if isinstance(source, InlineSource):
        return source.text
    return _fetch_pointer(source)


def _cache_path(source: PointerSource) -> Path:
    owner_repo = source.repo.rstrip("/").split("/")[-2:]
    return CACHE_ROOT / "/".join(owner_repo) / source.commit / source.path


def _fetch_pointer(source: PointerSource) -> str:
    """Fetch a pinned span from GitHub, caching the whole file under ``benchmarks/.cache/``.

    Deliberately not called during the default CI run: the Phase 0 corpus is inline-only so the
    merge gate stays hermetic and offline. Mined pairs are fetched by ``make repo-eval`` and by
    explicit corpus refreshes.
    """
    cached = _cache_path(source)
    if not cached.exists():
        import urllib.request  # local import: only the network path pays for it

        owner_repo = "/".join(source.repo.rstrip("/").split("/")[-2:])
        url = f"https://raw.githubusercontent.com/{owner_repo}/{source.commit}/{source.path}"
        cached.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(url, timeout=30) as response:
            cached.write_bytes(response.read())

    lines = cached.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(lines[source.start_line - 1 : source.end_line])
