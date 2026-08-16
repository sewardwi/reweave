"""Structural hashing and MinHash/LSH candidate generation, under a hard budget.

Phase 1, D5 stage 1.
"""

from reweave_engine.fingerprint.minhash import (
    DEFAULT_BANDS,
    DEFAULT_CANDIDATE_BUDGET,
    DEFAULT_PERMUTATIONS,
    CandidateSet,
    band_keys,
    estimate_jaccard,
    generate_candidates,
    signature,
)

__all__ = [
    "DEFAULT_BANDS",
    "DEFAULT_CANDIDATE_BUDGET",
    "DEFAULT_PERMUTATIONS",
    "CandidateSet",
    "band_keys",
    "estimate_jaccard",
    "generate_candidates",
    "signature",
]
