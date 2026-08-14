"""``reweave-audit`` — the local, private-code audit CLI.

Phase 2 publishes this via pipx so that teams can audit private repositories without code ever
leaving their machine. Scanning lands in Phase 1; today the CLI exists so the entry point, exit
codes, and the no-network promise are established and testable from the start.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from reweave_engine import __version__

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_NOT_IMPLEMENTED = 69  # EX_UNAVAILABLE


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="reweave-audit",
        description="Audit a codebase for semantically duplicated logic. Runs entirely locally.",
    )
    parser.add_argument("--version", action="version", version=f"reweave-audit {__version__}")
    sub = parser.add_subparsers(dest="command")

    scan = sub.add_parser("scan", help="Scan a directory and write a report")
    scan.add_argument("path", nargs="?", default=".", help="directory to scan (default: .)")
    scan.add_argument("--json", dest="json_out", help="write JSON findings to this path")
    scan.add_argument("--html", dest="html_out", help="write an HTML report to this path")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return EXIT_USAGE

    sys.stderr.write(
        "reweave-audit: scanning arrives in Phase 1 (see docs/PLAN.md).\n"
        "The engine currently ships only the Phase 0 baseline detector, used by the benchmark.\n"
    )
    return EXIT_NOT_IMPLEMENTED


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
