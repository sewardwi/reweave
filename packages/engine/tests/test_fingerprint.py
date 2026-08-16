"""MinHash signatures and LSH candidate generation."""

from reweave_engine.fingerprint import (
    DEFAULT_PERMUTATIONS,
    band_keys,
    estimate_jaccard,
    generate_candidates,
    signature,
)


def shingle_set(start: int, count: int) -> set[str]:
    return {f"tok{i}" for i in range(start, start + count)}


class TestSignature:
    def test_width_matches_permutations(self) -> None:
        assert len(signature(shingle_set(0, 20))) == DEFAULT_PERMUTATIONS

    def test_is_stable_across_calls(self) -> None:
        """Determinism is a Phase 1 exit criterion, so hashing must not be salted per process."""
        assert signature(shingle_set(0, 20)) == signature(shingle_set(0, 20))

    def test_identical_sets_have_identical_signatures(self) -> None:
        assert signature({"a", "b", "c"}) == signature({"c", "b", "a"})

    def test_empty_set_is_handled(self) -> None:
        assert len(signature(set())) == DEFAULT_PERMUTATIONS


class TestJaccardEstimate:
    def test_identical_sets_estimate_one(self) -> None:
        sig = signature(shingle_set(0, 50))
        assert estimate_jaccard(sig, sig) == 1.0

    def test_disjoint_sets_estimate_near_zero(self) -> None:
        left = signature(shingle_set(0, 50))
        right = signature(shingle_set(1000, 50))
        assert estimate_jaccard(left, right) < 0.05

    def test_overlapping_sets_estimate_near_true_jaccard(self) -> None:
        # 40 shared of 60 union -> true Jaccard 0.667.
        left = signature(shingle_set(0, 50))
        right = signature(shingle_set(10, 50))
        assert abs(estimate_jaccard(left, right) - (40 / 60)) < 0.12


class TestBanding:
    def test_band_count_is_respected(self) -> None:
        assert len(band_keys(signature(shingle_set(0, 10)), bands=32)) == 32

    def test_rejects_indivisible_band_counts(self) -> None:
        import pytest

        with pytest.raises(ValueError, match="cannot split"):
            band_keys(signature(shingle_set(0, 10)), bands=7)


class TestCandidateGeneration:
    def test_similar_units_become_candidates(self) -> None:
        sigs = [signature(shingle_set(0, 60)), signature(shingle_set(2, 60))]
        assert generate_candidates(sigs).pairs == [(0, 1)]

    def test_dissimilar_units_do_not(self) -> None:
        sigs = [signature(shingle_set(0, 60)), signature(shingle_set(5000, 60))]
        assert generate_candidates(sigs).pairs == []

    def test_output_is_deterministic(self) -> None:
        sigs = [signature(shingle_set(i, 60)) for i in range(0, 12, 2)]
        assert generate_candidates(sigs).pairs == generate_candidates(sigs).pairs

    def test_budget_truncates_and_reports_honestly(self) -> None:
        """A silently truncated scan is a lie about coverage."""
        sigs = [signature(shingle_set(0, 60)) for _ in range(20)]
        result = generate_candidates(sigs, budget=5)
        assert len(result.pairs) == 5
        assert result.truncated
        assert result.dropped_to_budget == result.considered - 5

    def test_oversized_buckets_are_skipped(self) -> None:
        """4,000 identical generated methods must not consume the whole budget."""
        sigs = [signature(shingle_set(0, 60)) for _ in range(50)]
        assert generate_candidates(sigs, max_bucket=10).pairs == []
        assert generate_candidates(sigs, max_bucket=100).pairs != []
