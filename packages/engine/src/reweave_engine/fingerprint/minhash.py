"""MinHash + LSH candidate generation under a hard budget (D5 stage 1).

The problem this solves is quadratic. A 300k-LOC repository holds roughly 15k code units, which
is ~10^8 pairs; comparing them all takes minutes of pure Python and produces a candidate list
nobody can pay to embed, let alone adjudicate. MinHash reduces each unit to a fixed-width
signature, and banded LSH turns "find similar pairs" into "find units that collide in a bucket",
which is linear in the number of units.

The budget is not a nicety. Without a hard cap, one pathological repository — a generated client
with 4,000 near-identical methods — produces millions of candidates and the scan never finishes.
Exceeding the budget is a normal, reportable outcome, not an error: we keep the highest-signal
candidates and record how many we dropped, because a silently truncated scan is a lie about
coverage.

Hashing is seeded and stable across runs and processes (``blake2b``, not Python's salted
``hash()``), because determinism is a Phase 1 exit criterion.
"""

from __future__ import annotations

import hashlib
import itertools
from collections import defaultdict
from dataclasses import dataclass
from typing import Final

#: Signature width. 128 permutations estimate Jaccard to roughly ±0.09 at one standard
#: deviation, which is well inside the uncertain band the detector already discards on.
DEFAULT_PERMUTATIONS: Final = 128

#: Banding controls the similarity at which pairs start colliding. With 128 permutations,
#: 32 bands of 4 rows gives ~50% collision probability around Jaccard 0.6 and near-certain
#: collision above 0.8 — comfortably below the 0.70 duplicate threshold, so stage 1's recall is
#: bounded by its threshold rather than by the index.
DEFAULT_BANDS: Final = 32

#: Maximum candidate pairs a single scan may produce. Sized so the shortlist stays affordable
#: to embed and adjudicate.
DEFAULT_CANDIDATE_BUDGET: Final = 50_000

_MERSENNE_PRIME: Final = (1 << 61) - 1
_MAX_HASH: Final = _MERSENNE_PRIME


def _hash_shingle(shingle: str) -> int:
    """One stable 64-bit hash per shingle.

    ``blake2b`` rather than the builtin ``hash()``: Python salts string hashing per process, so
    builtin hashes would make signatures differ between runs and break both the embedding cache
    and the determinism exit criterion.
    """
    return int.from_bytes(
        hashlib.blake2b(shingle.encode("utf-8"), digest_size=8).digest(), "little"
    )


def _permutation_coefficients(permutations: int) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """Fixed (a, b) pairs for the universal hash family ``(a*h + b) mod p``.

    Derived deterministically from a constant seed rather than randomly, so signatures are
    comparable across processes, machines, and releases. Changing this seed invalidates every
    stored signature, so treat it as a schema version.
    """
    coefficients: list[tuple[int, int]] = []
    for index in range(permutations):
        digest = hashlib.blake2b(
            b"reweave-minhash-v1", digest_size=16, salt=index.to_bytes(8, "little")
        ).digest()
        a = int.from_bytes(digest[:8], "little") % (_MERSENNE_PRIME - 1) + 1
        b = int.from_bytes(digest[8:], "little") % _MERSENNE_PRIME
        coefficients.append((a, b))
    return tuple(a for a, _ in coefficients), tuple(b for _, b in coefficients)


_COEFF_CACHE: dict[int, tuple[tuple[int, ...], tuple[int, ...]]] = {}


def _coefficients(permutations: int) -> tuple[tuple[int, ...], tuple[int, ...]]:
    cached = _COEFF_CACHE.get(permutations)
    if cached is None:
        cached = _permutation_coefficients(permutations)
        _COEFF_CACHE[permutations] = cached
    return cached


def signature(shingles: set[str], permutations: int = DEFAULT_PERMUTATIONS) -> tuple[int, ...]:
    """MinHash signature: the minimum hash of the shingle set under each permutation.

    Each shingle is hashed **once** with blake2b and then permuted with cheap integer arithmetic.
    Hashing per (shingle, permutation) instead — the obvious implementation — costs 128 blake2b
    calls per shingle and dominated scan time on a real repository.
    """
    if not shingles:
        return tuple([_MAX_HASH] * permutations)

    a_coeffs, b_coeffs = _coefficients(permutations)
    mins = [_MAX_HASH] * permutations
    prime = _MERSENNE_PRIME

    for shingle in shingles:
        base = _hash_shingle(shingle)
        for i in range(permutations):
            value = (a_coeffs[i] * base + b_coeffs[i]) % prime
            if value < mins[i]:
                mins[i] = value

    return tuple(mins)


def estimate_jaccard(left: tuple[int, ...], right: tuple[int, ...]) -> float:
    """Fraction of signature positions that agree — an unbiased Jaccard estimate."""
    if not left or len(left) != len(right):
        return 0.0
    agreed = sum(1 for a, b in zip(left, right, strict=True) if a == b)
    return agreed / len(left)


@dataclass(frozen=True, slots=True)
class CandidateSet:
    """Candidate pairs plus an honest account of what was left out."""

    pairs: list[tuple[int, int]]
    considered: int
    """Distinct pairs that collided in at least one band, before the budget was applied."""

    dropped_to_budget: int
    """Collided pairs discarded because the budget was exhausted. Non-zero means this scan is
    incomplete, and the report must say so."""

    @property
    def truncated(self) -> bool:
        return self.dropped_to_budget > 0


def band_keys(
    signature_values: tuple[int, ...], bands: int = DEFAULT_BANDS
) -> list[tuple[int, bytes]]:
    """Split a signature into bands; equal band values are what put two units in a bucket."""
    if bands <= 0 or len(signature_values) % bands != 0:
        msg = f"cannot split a {len(signature_values)}-wide signature into {bands} bands"
        raise ValueError(msg)
    rows = len(signature_values) // bands
    keys: list[tuple[int, bytes]] = []
    for band in range(bands):
        chunk = signature_values[band * rows : (band + 1) * rows]
        keys.append((band, b"".join(value.to_bytes(8, "little") for value in chunk)))
    return keys


def generate_candidates(
    signatures: list[tuple[int, ...]],
    *,
    bands: int = DEFAULT_BANDS,
    budget: int = DEFAULT_CANDIDATE_BUDGET,
    max_bucket: int = 200,
) -> CandidateSet:
    """Return candidate index pairs via banded LSH.

    ``max_bucket`` guards against the degenerate case that motivates the budget: a bucket holding
    4,000 identical generated methods contributes ~8M pairs by itself and would consume the entire
    budget on one uninteresting cluster. Oversized buckets are skipped and counted — the cluster
    is real, but enumerating every pair inside it teaches us nothing that its size has not
    already told us.
    """
    buckets: dict[tuple[int, bytes], list[int]] = defaultdict(list)
    for index, sig in enumerate(signatures):
        for key in band_keys(sig, bands):
            buckets[key].append(index)

    seen: set[tuple[int, int]] = set()
    oversized = 0
    for members in buckets.values():
        if len(members) < 2:
            continue
        if len(members) > max_bucket:
            oversized += 1
            continue
        for left, right in itertools.combinations(sorted(members), 2):
            seen.add((left, right))

    # Sorted for determinism: identical inputs must produce an identical candidate list.
    ordered = sorted(seen)
    kept = ordered[:budget]
    return CandidateSet(
        pairs=kept,
        considered=len(ordered),
        dropped_to_budget=len(ordered) - len(kept),
    )
