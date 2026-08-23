"""``reweave-audit`` — the local, private-code audit CLI.

Published via pipx in Phase 2 so a team can audit a private repository without the code ever
leaving their machine. That promise is the reason this exists as a CLI at all, so it is
enforced rather than asserted: nothing here opens a socket, and the only paths written are the
ones the user names.

Exit codes are meant to be used in CI:

* ``0`` — scan completed (with or without findings)
* ``1`` — scan completed and ``--fail-on-findings`` was set with clusters present
* ``2`` — usage error
* ``69`` — nothing scannable found (EX_UNAVAILABLE)
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from reweave_engine import __version__
from reweave_engine.fingerprint import DEFAULT_CANDIDATE_BUDGET
from reweave_engine.parsing import DEFAULT_MIN_LINES
from reweave_engine.report.html import render_html
from reweave_engine.report.model import AuditReport
from reweave_engine.scan import scan

EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_USAGE = 2
EXIT_NOTHING_TO_SCAN = 69


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="reweave-audit",
        description=(
            "Find semantically duplicated logic in a codebase. Runs entirely on this machine — "
            "no code is uploaded."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  reweave-audit scan .\n"
            "  reweave-audit scan ~/src/app --html audit.html --json audit.json\n"
            "  reweave-audit scan . --top 10 --fail-on-findings\n"
        ),
    )
    parser.add_argument("--version", action="version", version=f"reweave-audit {__version__}")
    sub = parser.add_subparsers(dest="command")

    scan_cmd = sub.add_parser("scan", help="scan a directory for duplicate logic")
    scan_cmd.add_argument("path", nargs="?", default=".", help="directory to scan (default: .)")
    scan_cmd.add_argument("--json", dest="json_out", metavar="FILE", help="write JSON findings")
    scan_cmd.add_argument("--html", dest="html_out", metavar="FILE", help="write an HTML report")
    scan_cmd.add_argument(
        "--top", type=int, metavar="N", help="keep only the N highest-blast-radius clusters"
    )
    scan_cmd.add_argument(
        "--min-lines",
        type=int,
        default=DEFAULT_MIN_LINES,
        metavar="N",
        help=f"ignore functions shorter than N lines (default: {DEFAULT_MIN_LINES})",
    )
    scan_cmd.add_argument(
        "--budget",
        type=int,
        default=DEFAULT_CANDIDATE_BUDGET,
        metavar="N",
        help=f"max candidate pairs to compare (default: {DEFAULT_CANDIDATE_BUDGET:,})",
    )
    scan_cmd.add_argument(
        "--no-git", action="store_true", help="skip git history (churn will read as unavailable)"
    )
    scan_cmd.add_argument(
        "--no-code",
        action="store_true",
        help="omit source snippets from the HTML report",
    )
    scan_cmd.add_argument(
        "--fail-on-findings",
        action="store_true",
        help="exit 1 when any cluster is found (for CI)",
    )
    scan_cmd.add_argument("--quiet", action="store_true", help="suppress the terminal summary")
    return parser


def _summary(report: AuditReport, limit: int = 5) -> str:
    coverage = report.coverage
    lines = [
        "",
        f"  Reweave audit · {report.root}",
        f"  {coverage.units_extracted:,} functions in {coverage.files_scanned:,} files · "
        f"{coverage.candidate_pairs:,} pairs compared · {report.duration_seconds:g}s",
        "",
    ]

    if not report.clusters:
        lines += [
            "  No duplicate logic found.",
            "",
            "  That is a clean result, not an empty one — but it is also not proof of",
            "  absence: this build detects structural duplicates, and semantic",
            "  reimplementations need the full pipeline.",
            "",
        ]
        return "\n".join(lines)

    lines += [
        f"  {report.total_removable_lines:,} removable lines across "
        f"{len(report.clusters):,} clusters "
        f"({report.remediable_clusters:,} safe to consolidate)",
        "",
    ]
    for cluster in report.clusters[:limit]:
        state = "safe" if cluster.safely_remediable else "needs review"
        churn = "—" if cluster.churn is None else str(cluster.churn)
        lines.append(
            f"  -{cluster.removable_lines:>5,} lines  {cluster.unit_count:>2} copies  "
            f"{cluster.call_sites:>3} calls  churn {churn:>3}  [{state}]"
        )
        lines.append(f"        {cluster.units[0].location}  {cluster.units[0].name}")
    if len(report.clusters) > limit:
        lines.append(f"  … and {len(report.clusters) - limit:,} more")
    lines.append("")

    if coverage.candidates_truncated:
        lines += [
            "  Note: the candidate budget was reached, so this scan is incomplete and",
            "  understates duplication. Raise --budget for full coverage.",
            "",
        ]
    return "\n".join(lines)


def _write(path_text: str, content: str) -> Path:
    path = Path(path_text).expanduser()
    if path.parent != Path():
        path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return EXIT_USAGE

    root = Path(args.path).expanduser()
    if not root.is_dir():
        print(f"reweave-audit: not a directory: {root}", file=sys.stderr)
        return EXIT_USAGE

    report = scan(
        root,
        min_lines=args.min_lines,
        budget=args.budget,
        use_git=not args.no_git,
        max_clusters=args.top,
        tool_version=__version__,
    )

    if report.coverage.files_scanned == 0:
        print(
            f"reweave-audit: no TypeScript, JavaScript or Python files under {root}",
            file=sys.stderr,
        )
        return EXIT_NOTHING_TO_SCAN

    if args.json_out:
        written = _write(args.json_out, report.to_json())
        if not args.quiet:
            print(f"  JSON  {written}")

    if args.html_out:
        written = _write(args.html_out, render_html(report, root=root, with_code=not args.no_code))
        if not args.quiet:
            print(f"  HTML  {written}")

    if not args.quiet:
        print(_summary(report))

    if args.fail_on_findings and report.clusters:
        return EXIT_FINDINGS
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
