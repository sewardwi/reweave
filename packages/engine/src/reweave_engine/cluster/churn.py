"""Recent churn, read from git history.

Churn is half of blast radius: duplicated logic in a file nobody touches costs little, while the
same duplication in a file edited weekly costs on every edit. It is also the signal behind D16's
``diverged_history`` exclusion, so it earns its place twice.

Reading git is best-effort by design. A shallow clone, a tarball, or a non-repository directory
yields zero churn rather than an error — a scan must not fail because history is unavailable.
"""

from __future__ import annotations

import shutil
import subprocess
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Final

#: Window for "recent". Ninety days matches the D16 divergence rule, so the two use one notion of
#: recency rather than drifting apart.
DEFAULT_WINDOW_DAYS: Final = 90


@lru_cache(maxsize=1)
def _git_executable() -> str | None:
    """Absolute path to git, or None when it is not installed.

    Resolved rather than invoked as a bare name: an absolute path is what makes the call
    unambiguous about which binary runs, and "git is missing" becomes an explicit branch instead
    of an OSError caught three frames later.
    """
    return shutil.which("git")


def file_churn(
    repo_root: Path,
    *,
    window_days: int = DEFAULT_WINDOW_DAYS,
    timeout_seconds: float = 30.0,
) -> dict[str, int]:
    """Return ``path -> commit count`` over the window. Empty when history is unavailable."""
    git = _git_executable()
    if git is None:
        return {}

    try:
        result = subprocess.run(  # noqa: S603 - absolute path, fixed argv, no shell
            [
                git,
                "-C",
                str(repo_root),
                "log",
                f"--since={window_days}.days.ago",
                "--name-only",
                "--pretty=format:",
                "--no-renames",
            ],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return {}

    if result.returncode != 0:
        return {}

    counts: Counter[str] = Counter()
    for line in result.stdout.splitlines():
        path = line.strip()
        if path:
            counts[path] += 1
    return dict(counts)


def last_touched(
    repo_root: Path,
    paths: list[str],
    *,
    timeout_seconds: float = 30.0,
) -> dict[str, str]:
    """Return ``path -> ISO date of last commit``. Used by the D16 divergence check."""
    git = _git_executable()
    if git is None:
        return {}

    out: dict[str, str] = {}
    for path in paths:
        try:
            result = subprocess.run(  # noqa: S603 - absolute path, fixed argv, no shell
                [git, "-C", str(repo_root), "log", "-1", "--format=%cI", "--", path],
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if result.returncode == 0 and result.stdout.strip():
            out[path] = result.stdout.strip()
    return out
