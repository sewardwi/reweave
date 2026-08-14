"""Imports to symbol references to a conservative call graph.

Unresolved references are counted, never guessed: remediation refuses to rewrite call sites in
files whose references we could not fully resolve (see PLAN.md §4)."""
