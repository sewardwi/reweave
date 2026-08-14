#!/usr/bin/env python
"""Repo-level eval — the ship gate (D12).

The pair benchmark scores a roughly balanced set of curated pairs. Production is not balanced: a
300k-LOC repository holds on the order of 10^9 candidate pairs of which perhaps a few hundred are
true duplicates. A detector at 0.95 precision on balanced pairs can land far below 0.30 precision
in production, and production precision is what the customer actually experiences.

So this eval scans whole repositories, surfaces the top-k findings, and requires that **every
surfaced finding is hand-labeled**. It reports precision@k and findings-per-KLOC — the two numbers
that predict whether the ratchet will feel sharp or noisy.

Workflow:
    1. ``python benchmarks/run_repo_eval.py --collect``   scan the repo set, write findings to
       ``benchmarks/repos/<name>/findings.jsonl`` with ``label: null``
    2. label every record by hand (``label: true|false``)
    3. ``python benchmarks/run_repo_eval.py``             score the labeled findings

Step 2 is the expensive one and there is no way around it. That is the price of knowing.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

REPOS_ROOT = Path(__file__).parent / "repos"
DEFAULT_K = 20


@dataclass(frozen=True)
class RepoScore:
    repo: str
    surfaced: int
    labeled: int
    true_positives: int
    kloc: float

    @property
    def precision_at_k(self) -> float:
        if self.labeled == 0:
            return 0.0
        return self.true_positives / self.labeled

    @property
    def findings_per_kloc(self) -> float:
        if self.kloc == 0:
            return 0.0
        return self.surfaced / self.kloc


def load_repo_scores(k: int) -> list[RepoScore]:
    scores: list[RepoScore] = []
    for findings_path in sorted(REPOS_ROOT.rglob("findings.jsonl")):
        manifest_path = findings_path.parent / "manifest.json"
        if not manifest_path.exists():
            msg = f"{findings_path.parent}: missing manifest.json"
            raise FileNotFoundError(msg)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        records = [
            json.loads(line)
            for line in findings_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ][:k]
        labeled = [r for r in records if r.get("label") is not None]

        scores.append(
            RepoScore(
                repo=str(manifest["repo"]),
                surfaced=len(records),
                labeled=len(labeled),
                true_positives=sum(1 for r in labeled if r["label"] is True),
                kloc=float(manifest.get("kloc", 0.0)),
            )
        )
    return scores


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--k", type=int, default=DEFAULT_K, help=f"top-k (default {DEFAULT_K})")
    parser.add_argument(
        "--collect",
        action="store_true",
        help="scan the repo set and emit unlabeled findings (needs the Phase 1 engine)",
    )
    args = parser.parse_args(argv)

    if args.collect:
        print(
            "collect: requires the Phase 1 scan pipeline (parsing → fingerprint → adjudicate).\n"
            "The Phase 0 baseline judges pairs, not repositories, so there is nothing to collect\n"
            "yet. See docs/PLAN.md Phase 1.",
            file=sys.stderr,
        )
        return 69  # EX_UNAVAILABLE

    scores = load_repo_scores(args.k)
    if not scores:
        print(
            "No repo evals found under benchmarks/repos/.\n\n"
            "This gate is empty until Phase 1 ships a scan pipeline. It is wired up now so that\n"
            "the first full-repo scan gets measured properly instead of eyeballed.",
            file=sys.stderr,
        )
        return 0

    print(f"\n  repo-level eval (top-{args.k})\n")
    unlabeled = 0
    for s in scores:
        print(
            f"  {s.repo:<40} precision@{args.k}={s.precision_at_k:.3f}  "
            f"findings/KLOC={s.findings_per_kloc:.2f}  labeled={s.labeled}/{s.surfaced}"
        )
        unlabeled += s.surfaced - s.labeled

    if unlabeled:
        print(
            f"\n  {unlabeled} surfaced findings are unlabeled. Partial labeling biases the "
            f"result — label all of them or the number means nothing.\n",
            file=sys.stderr,
        )
        return 1

    print("")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
