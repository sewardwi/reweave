#!/usr/bin/env python
"""Interactive labeler: turn mined candidates into corpus entries.

Asks the two questions the plan cares about, in order:

    1. Same observable behavior?              → the detection label
    2. If yes, should they be consolidated?   → the D16 advisability label

Question 2 is the one that is almost free to answer here and impossible to reconstruct later,
because you are already reading both functions.

Labeled records are appended to ``benchmarks/corpus/`` and removed from the inbox. Skipped
records stay in the inbox for next time. Quit any time with ``q`` — progress is saved.

Usage:
    python benchmarks/label.py benchmarks/inbox/some-repo.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from corpus_schema import (
    CORPUS_ROOT,
    Advisability,
    LabeledPair,
    PairLabel,
    PointerSource,
    resolve_text,
)

EXCLUSIONS = [
    ("1", "cross_boundary", "different services/packages/owners"),
    ("2", "generated_or_vendored", "generated, vendored, migrations, fixtures"),
    ("3", "diverged_history", "both edited independently, recently"),
    ("4", "requires_flag_param", "unifying needs a flag/param"),
    ("5", "below_size_floor", "too small to be worth the indirection"),
    ("6", "unresolved_call_sites", "references we cannot fully resolve"),
]


def show(record: dict[str, Any]) -> None:
    print("\n" + "═" * 92)
    print(f"  {record['pair_id']}   candidate similarity {record.get('candidate_similarity')}")
    print("═" * 92)
    for side in ("left", "right"):
        source = record[side]
        print(f"\n── {side.upper()}  {source.get('path', '')}:{source.get('start_line', '')}")
        try:
            text = resolve_text(PointerSource.model_validate(source))
        except Exception as exc:
            text = f"<could not resolve: {exc}>"
        for line in text.splitlines()[:40]:
            print(f"   {line}")


def ask(prompt: str, options: dict[str, str]) -> str | None:
    rendered = "  ".join(f"[{k}] {v}" for k, v in options.items())
    while True:
        answer = input(f"\n{prompt}\n  {rendered}  [s] skip  [q] quit\n> ").strip().lower()
        if answer == "q":
            return None
        if answer == "s":
            return "skip"
        if answer in options:
            return answer
        print("  ?")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inbox", type=Path, help="inbox JSONL produced by mine_candidates.py")
    parser.add_argument("--out", type=Path, help="corpus file to append to")
    args = parser.parse_args(argv)

    records = [
        json.loads(line)
        for line in args.inbox.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    out = args.out or CORPUS_ROOT / f"{args.inbox.stem}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)

    remaining: list[dict[str, Any]] = []
    labeled = 0

    for index, record in enumerate(records):
        show(record)
        print(f"\n  ({index + 1} of {len(records)})")

        answer = ask("Same observable behavior?", {"y": "duplicate", "n": "not a duplicate"})
        if answer is None:
            remaining.extend(records[index:])
            break
        if answer == "skip":
            remaining.append(record)
            continue

        record["label"] = (
            PairLabel.DUPLICATE.value if answer == "y" else PairLabel.NOT_DUPLICATE.value
        )
        record["exclusion"] = None

        if answer == "y":
            advice = ask(
                "Should they be consolidated? (D16)", {"y": "consolidate", "n": "leave alone"}
            )
            if advice is None:
                remaining.extend(records[index:])
                break
            if advice == "skip":
                remaining.append(record)
                continue
            if advice == "y":
                record["should_consolidate"] = Advisability.CONSOLIDATE.value
            else:
                record["should_consolidate"] = Advisability.LEAVE_ALONE.value
                rule = ask("Which rule?", {key: name for key, name, _ in EXCLUSIONS})
                if rule is None or rule == "skip":
                    remaining.append(record)
                    continue
                record["exclusion"] = next(name for key, name, _ in EXCLUSIONS if key == rule)
        else:
            record["should_consolidate"] = Advisability.NOT_APPLICABLE.value

        record["notes"] = input("  notes (why — one line, for the next reader)\n> ").strip()
        record.pop("candidate_similarity", None)

        try:
            LabeledPair.model_validate(record)
        except Exception as exc:
            print(f"  ! rejected by schema, returned to inbox: {exc}", file=sys.stderr)
            remaining.append(record)
            continue

        with out.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        labeled += 1

    args.inbox.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in remaining), encoding="utf-8"
    )
    print(f"\n  labeled {labeled} → {out}")
    print(f"  {len(remaining)} left in {args.inbox}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
