"""Corpus integrity.

A benchmark corpus is a dataset, and datasets rot silently: duplicate ids, leaked pairs across
splits, labels that drifted from the schema. These tests are the corpus's own CI, and they run
on every PR alongside everything else.
"""

from __future__ import annotations

import hashlib
from collections import Counter

import pytest
from corpus_schema import (
    Advisability,
    InlineSource,
    LabeledPair,
    PairLabel,
    Split,
    load_corpus,
    resolve_text,
)

CORPUS = load_corpus()

#: Phase 0 ships a seed corpus. The plan's floor is 150 pairs; growing to it is a Phase 0/1
#: action item, and this test is the reminder that will not let it be forgotten.
PLANNED_MINIMUM = 150


def _fingerprint(pair: LabeledPair) -> tuple[str, str]:
    texts = sorted(
        hashlib.sha256(resolve_text(side).encode()).hexdigest() for side in (pair.left, pair.right)
    )
    return (texts[0], texts[1])


class TestIntegrity:
    def test_corpus_is_not_empty(self) -> None:
        assert CORPUS

    def test_pair_ids_are_unique(self) -> None:
        counts = Counter(p.pair_id for p in CORPUS)
        assert [pid for pid, n in counts.items() if n > 1] == []

    def test_no_pair_leaks_across_splits(self) -> None:
        """The holdout is worthless if the same code appears in train under another id."""
        train = {_fingerprint(p) for p in CORPUS if p.split is Split.TRAIN}
        holdout = {_fingerprint(p) for p in CORPUS if p.split is Split.HOLDOUT}
        assert train & holdout == set()

    def test_both_splits_are_populated(self) -> None:
        by_split = Counter(p.split for p in CORPUS)
        assert by_split[Split.TRAIN] > 0
        assert by_split[Split.HOLDOUT] > 0

    def test_holdout_is_a_meaningful_fraction(self) -> None:
        holdout = sum(1 for p in CORPUS if p.split is Split.HOLDOUT)
        assert 0.15 <= holdout / len(CORPUS) <= 0.40


class TestBalance:
    def test_has_hard_negatives(self) -> None:
        """Without negatives, precision is unmeasurable — and precision is the product law (D6)."""
        negatives = sum(1 for p in CORPUS if p.label is PairLabel.NOT_DUPLICATE)
        assert negatives / len(CORPUS) >= 0.25

    def test_has_duplicates_that_should_be_left_alone(self) -> None:
        """D16 is unmeasurable without pairs that are duplicates we should not consolidate."""
        leave_alone = sum(1 for p in CORPUS if p.should_consolidate is Advisability.LEAVE_ALONE)
        assert leave_alone >= 5

    def test_exclusion_rules_are_varied(self) -> None:
        """One rule exercised five times teaches the adjudicator less than five rules once each."""
        rules = {p.exclusion for p in CORPUS if p.exclusion is not None}
        assert len(rules) >= 4

    def test_covers_every_supported_language(self) -> None:
        languages = {p.language for p in CORPUS}
        assert len(languages) >= 2


class TestSources:
    def test_inline_sources_carry_text(self) -> None:
        for pair in CORPUS:
            for side in (pair.left, pair.right):
                if isinstance(side, InlineSource):
                    assert side.text.strip()

    def test_pointers_pin_a_commit_and_record_a_license(self) -> None:
        """Pointer records must be reproducible and license-attributed (D12, LICENSE)."""
        for pair in CORPUS:
            for side in (pair.left, pair.right):
                if not isinstance(side, InlineSource):
                    assert len(side.commit) >= 7
                    assert side.license
                    assert side.end_line >= side.start_line


@pytest.mark.xfail(
    reason=f"corpus v0 is a seed; the plan's floor is {PLANNED_MINIMUM} pairs (Phase 0 action)",
    strict=True,
)
def test_corpus_reaches_the_planned_minimum() -> None:
    assert len(CORPUS) >= PLANNED_MINIMUM
