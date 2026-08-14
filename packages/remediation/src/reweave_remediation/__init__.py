"""Remediation: planning, constrained edits, and sandboxed verification (Phase 4).

May depend on ``reweave_engine``; the reverse is forbidden (PLAN.md §5 layout rules).

Nothing here writes to a repository. Every write goes through ``apps/api/github/GitWriter``,
which is the only module permitted to talk to the GitHub write API (D7).
"""

__all__: list[str] = []
