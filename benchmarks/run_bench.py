#!/usr/bin/env python
"""Pair benchmark — the CI merge gate (D12).

**Split discipline, which is the whole point of this file.** The plan says never tune on the
holdout. A CI gate that scores the holdout on every PR *is* tuning on the holdout: you iterate
until it goes green, and the number stops meaning anything. So:

* ``make bench`` scores the **train** split. This runs on every PR and blocks merges.
* ``make bench -- --split holdout`` scores the holdout. Run it at phase gates only, record the
  result in the ADR or phase notes, and do not iterate against it.

Usage:
    python benchmarks/run_bench.py [--split train|holdout] [--json reports/bench.json]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import cast

from corpus_schema import (
    Advisability,
    LabeledPair,
    PairLabel,
    Source,
    Split,
    load_corpus,
    resolve_text,
)

from reweave_engine import LoadedUnit, TokenOverlapDetector
from reweave_engine.detector import PairDetector
from reweave_shared import CodeUnit, Span, Verdict

GATES_PATH = Path(__file__).parent / "gates.toml"


@dataclass(frozen=True)
class Scores:
    detector: str
    split: str
    pairs: int
    true_positives: int
    false_positives: int
    false_negatives: int
    true_negatives: int
    discarded_uncertain: int
    precision: float
    recall: float
    f1: float
    advisability_correct: int
    advisability_total: int

    @property
    def advisability_accuracy(self) -> float:
        if self.advisability_total == 0:
            return 0.0
        return self.advisability_correct / self.advisability_total


def _to_loaded_unit(source: Source, pair: LabeledPair, side: str) -> LoadedUnit:
    text = resolve_text(source)
    line_count = max(1, len(text.splitlines()))
    return LoadedUnit(
        unit=CodeUnit(
            path=f"corpus/{pair.pair_id}/{side}",
            span=Span(start_line=1, end_line=line_count),
            language=pair.language,
            name=source.name,
            content_hash=f"sha256:{hashlib.sha256(text.encode()).hexdigest()[:16]}",
        ),
        text=text,
    )


def score(
    detector: PairDetector,
    pairs: list[LabeledPair],
    split: Split,
    errors: list[str] | None = None,
) -> Scores:
    tp = fp = fn = tn = discarded = 0
    advis_correct = advis_total = 0

    for pair in pairs:
        finding = detector.judge(
            _to_loaded_unit(pair.left, pair, "left"),
            _to_loaded_unit(pair.right, pair, "right"),
        )
        predicted_duplicate = finding.verdict is Verdict.DUPLICATE
        actually_duplicate = pair.label is PairLabel.DUPLICATE

        if finding.verdict is Verdict.UNCERTAIN:
            discarded += 1

        if predicted_duplicate and actually_duplicate:
            tp += 1
        elif predicted_duplicate and not actually_duplicate:
            fp += 1
            if errors is not None:
                errors.append(
                    f"    FP  {pair.pair_id:<28} structural="
                    f"{finding.metrics.structural.percent}%  {pair.notes[:60]}"
                )
        elif not predicted_duplicate and actually_duplicate:
            fn += 1
            if errors is not None:
                errors.append(
                    f"    FN  {pair.pair_id:<28} structural="
                    f"{finding.metrics.structural.percent}%  {pair.notes[:60]}"
                )
        else:
            tn += 1

        # D16 advisability, reported but not gated until a detector can actually evaluate it.
        if actually_duplicate and pair.should_consolidate is not Advisability.NOT_APPLICABLE:
            advis_total += 1
            recommended = finding.advice is not None and finding.advice.recommended
            if recommended == (pair.should_consolidate is Advisability.CONSOLIDATE):
                advis_correct += 1

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    return Scores(
        detector=detector.name,
        split=split.value,
        pairs=len(pairs),
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
        true_negatives=tn,
        discarded_uncertain=discarded,
        precision=precision,
        recall=recall,
        f1=f1,
        advisability_correct=advis_correct,
        advisability_total=advis_total,
    )


def load_gates() -> dict[str, float]:
    raw: dict[str, object] = tomllib.loads(GATES_PATH.read_text(encoding="utf-8"))
    gate_raw: object = raw.get("gate", {})
    if not isinstance(gate_raw, dict):
        msg = "gates.toml: [gate] must be a table"
        raise TypeError(msg)
    gate = cast("dict[str, object]", gate_raw)

    typed: dict[str, float] = {}
    for key, value in gate.items():
        if not isinstance(value, (int, float)):
            msg = f"gates.toml: gate '{key}' must be a number, got {type(value).__name__}"
            raise TypeError(msg)
        typed[str(key)] = float(value)
    return typed


def render(scores: Scores, gates: dict[str, float], corpus_size: int) -> str:
    lines = [
        "",
        f"  detector           {scores.detector}",
        f"  split              {scores.split}  ({scores.pairs} pairs of {corpus_size} total)",
        "",
        f"  precision          {scores.precision:.3f}   (gate ≥ {gates['min_precision']:.2f})",
        f"  recall             {scores.recall:.3f}   (gate ≥ {gates['min_recall']:.2f})",
        f"  f1                 {scores.f1:.3f}",
        "",
        f"  true positives     {scores.true_positives}",
        f"  false positives    {scores.false_positives}   ← the ones that cost customers (D6)",
        f"  false negatives    {scores.false_negatives}",
        f"  true negatives     {scores.true_negatives}",
        f"  discarded (uncertain) {scores.discarded_uncertain}",
        "",
        f"  D16 advisability   {scores.advisability_accuracy:.3f} "
        f"({scores.advisability_correct}/{scores.advisability_total}) — reported, not gated",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--split",
        choices=[s.value for s in Split],
        default=Split.TRAIN.value,
        help="which split to score (default: train; holdout is for phase gates only)",
    )
    parser.add_argument("--json", dest="json_out", help="also write the report here")
    parser.add_argument(
        "--show-errors",
        action="store_true",
        help="list the misclassified pairs — the fastest way to see what a change broke",
    )
    args = parser.parse_args(argv)

    split = Split(args.split)
    all_pairs = load_corpus()
    pairs = [p for p in all_pairs if p.split is split]

    if not pairs:
        print(f"error: corpus has no pairs in the '{split.value}' split", file=sys.stderr)
        return 1

    if split is Split.HOLDOUT:
        print(
            "\n  ⚠  Scoring the HOLDOUT split.\n"
            "     Record this number and stop. Iterating against it destroys the only unbiased\n"
            "     estimate we have (D12).",
            file=sys.stderr,
        )

    detector = TokenOverlapDetector()
    errors: list[str] = []
    scores = score(detector, pairs, split, errors=errors)
    gates = load_gates()

    print(render(scores, gates, corpus_size=len(all_pairs)))

    if args.show_errors and errors:
        print("  misclassified:")
        for line in errors:
            print(line)
        print("")

    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(asdict(scores), indent=2) + "\n", encoding="utf-8")

    failures: list[str] = []
    if split is Split.TRAIN:
        if scores.precision < gates["min_precision"]:
            failures.append(f"precision {scores.precision:.3f} < gate {gates['min_precision']:.2f}")
        if scores.recall < gates["min_recall"]:
            failures.append(f"recall {scores.recall:.3f} < gate {gates['min_recall']:.2f}")

    if failures:
        for failure in failures:
            print(f"  FAIL  {failure}", file=sys.stderr)
        print("", file=sys.stderr)
        return 1

    print("  PASS\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
