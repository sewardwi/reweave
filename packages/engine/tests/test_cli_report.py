"""The scan pipeline, the report, and the CLI.

The HTML report is a file a developer may forward to their lead, so it is treated as an
untrusted-input renderer: repository content reaches it, and repository content is attacker
controlled on a public-repo audit.
"""

from __future__ import annotations

import json
from pathlib import Path

from reweave_engine.cli import (
    EXIT_FINDINGS,
    EXIT_NOTHING_TO_SCAN,
    EXIT_OK,
    EXIT_USAGE,
    main,
)
from reweave_engine.report import SCHEMA_VERSION, render_html
from reweave_engine.scan import discover_files, scan

DUPLICATED = """
def format_money(value):
    rounded = round(value * 100) / 100
    return f"{rounded:.2f}"


def render_total(items):
    total = len(items)
    return format_money(total)
"""

DUPLICATE_TWIN = """
def format_cash(amount):
    scaled = round(amount * 100) / 100
    return f"{scaled:.2f}"
"""

UNIQUE = """
def slugify(title):
    lowered = title.lower()
    return lowered.replace(" ", "-")
"""


def make_repo(tmp_path: Path, files: dict[str, str]) -> Path:
    root = tmp_path / "repo"
    for name, content in files.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return root


class TestDiscovery:
    def test_finds_supported_sources(self, tmp_path: Path) -> None:
        root = make_repo(tmp_path, {"a.py": UNIQUE, "b.ts": "export const x = 1;"})
        assert set(discover_files(root)) == {"a.py", "b.ts"}

    def test_skips_vendored_and_generated_trees(self, tmp_path: Path) -> None:
        root = make_repo(
            tmp_path,
            {
                "a.py": UNIQUE,
                "node_modules/pkg/index.js": "export const y = 2;",
                ".venv/lib/mod.py": UNIQUE,
                "dist/bundle.js": "var z = 3;",
            },
        )
        assert set(discover_files(root)) == {"a.py"}

    def test_ignores_unsupported_languages(self, tmp_path: Path) -> None:
        root = make_repo(tmp_path, {"a.py": UNIQUE, "main.rs": "fn main() {}", "README.md": "hi"})
        assert set(discover_files(root)) == {"a.py"}


class TestScan:
    def test_finds_a_duplicate_cluster(self, tmp_path: Path) -> None:
        root = make_repo(tmp_path, {"money.py": DUPLICATED, "cash.py": DUPLICATE_TWIN})
        report = scan(root, use_git=False)
        assert report.clusters
        assert report.total_removable_lines > 0

    def test_clean_repo_reports_no_clusters(self, tmp_path: Path) -> None:
        root = make_repo(tmp_path, {"a.py": UNIQUE})
        report = scan(root, use_git=False)
        assert report.clusters == []
        assert report.coverage.units_extracted == 1

    def test_churn_is_none_when_git_is_unavailable(self, tmp_path: Path) -> None:
        """Unavailable is not zero — a report showing '0 commits' for history it never read
        is stating something false."""
        root = make_repo(tmp_path, {"money.py": DUPLICATED, "cash.py": DUPLICATE_TWIN})
        report = scan(root, use_git=False)
        assert report.coverage.churn_available is False
        assert all(cluster.churn is None for cluster in report.clusters)

    def test_top_limits_clusters(self, tmp_path: Path) -> None:
        files = {f"m{i}.py": DUPLICATE_TWIN.replace("format_cash", f"format_{i}") for i in range(6)}
        root = make_repo(tmp_path, files)
        assert len(scan(root, use_git=False, max_clusters=1).clusters) == 1

    def test_coverage_counts_are_reported(self, tmp_path: Path) -> None:
        root = make_repo(tmp_path, {"money.py": DUPLICATED, "cash.py": DUPLICATE_TWIN})
        coverage = scan(root, use_git=False).coverage
        assert coverage.files_scanned == 2
        assert coverage.units_extracted == 3
        assert coverage.total_possible_pairs == 3

    def test_scan_is_deterministic(self, tmp_path: Path) -> None:
        root = make_repo(tmp_path, {"money.py": DUPLICATED, "cash.py": DUPLICATE_TWIN})
        first, second = scan(root, use_git=False), scan(root, use_git=False)
        assert [c.cluster_id for c in first.clusters] == [c.cluster_id for c in second.clusters]
        assert first.total_removable_lines == second.total_removable_lines


class TestJson:
    def test_is_valid_and_schema_versioned(self, tmp_path: Path) -> None:
        root = make_repo(tmp_path, {"money.py": DUPLICATED, "cash.py": DUPLICATE_TWIN})
        payload = json.loads(scan(root, use_git=False).to_json())
        assert payload["schema_version"] == SCHEMA_VERSION

    def test_measurements_carry_their_method(self, tmp_path: Path) -> None:
        """D17: no number appears without naming how it was computed."""
        root = make_repo(tmp_path, {"money.py": DUPLICATED, "cash.py": DUPLICATE_TWIN})
        payload = json.loads(scan(root, use_git=False).to_json())
        cluster = payload["clusters"][0]
        assert cluster["score_method"]
        evidence = cluster["evidence"][0]
        assert evidence["structural_method"]
        assert evidence["textual_method"]

    def test_output_is_byte_stable_across_runs(self, tmp_path: Path) -> None:
        root = make_repo(tmp_path, {"money.py": DUPLICATED, "cash.py": DUPLICATE_TWIN})

        def normalized() -> str:
            payload = json.loads(scan(root, use_git=False).to_json())
            payload.pop("generated_at")
            payload.pop("duration_seconds")
            return json.dumps(payload, sort_keys=True)

        assert normalized() == normalized()


class TestHtml:
    def test_escapes_hostile_repository_content(self, tmp_path: Path) -> None:
        """A repo is attacker-controlled input on a public audit; a shared report must not
        become a script-injection vector.

        The payload has to be *valid* source, or the parser rejects it and it never reaches the
        renderer — which would make this test pass for the wrong reason. So it rides in a string
        literal inside a function that really does get extracted, clustered, and quoted into the
        evidence block.
        """
        payload = '</pre></script><script>alert("xss")</script><img src=x onerror=alert(1)>'
        hostile = (
            f'def render_banner(value):\n    marker = "{payload}"\n    return marker + str(value)\n'
        )
        twin = f'def render_header(item):\n    token = "{payload}"\n    return token + str(item)\n'
        root = make_repo(tmp_path, {"evil.py": hostile, "twin.py": twin})
        report = scan(root, use_git=False)

        # The payload must actually be in the report, or this proves nothing.
        assert report.clusters, "fixture failed to produce a cluster"
        page = render_html(report, root=root)
        assert "alert(&quot;xss&quot;)" in page or "alert(" in page.replace("<script>", "")

        # Nothing executable survives.
        assert '<script>alert("xss")</script>' not in page
        assert "onerror=alert(1)>" not in page
        assert "&lt;script&gt;" in page

    def test_is_self_contained(self, tmp_path: Path) -> None:
        """No network at render or view time — the whole point of a local CLI (D10)."""
        root = make_repo(tmp_path, {"money.py": DUPLICATED, "cash.py": DUPLICATE_TWIN})
        page = render_html(scan(root, use_git=False), root=root)
        assert "http://" not in page
        assert "https://" not in page
        assert "<link" not in page

    def test_renders_a_designed_empty_state(self, tmp_path: Path) -> None:
        root = make_repo(tmp_path, {"a.py": UNIQUE})
        page = render_html(scan(root, use_git=False), root=root)
        assert "No duplicate logic found" in page
        assert "proof of absence" in page

    def test_shows_unavailable_churn_as_a_dash(self, tmp_path: Path) -> None:
        root = make_repo(tmp_path, {"money.py": DUPLICATED, "cash.py": DUPLICATE_TWIN})
        page = render_html(scan(root, use_git=False), root=root)
        assert "Commit counts are unavailable" in page

    def test_ships_a_table_view(self, tmp_path: Path) -> None:
        """Accessibility: every value reachable without reading a bar."""
        root = make_repo(tmp_path, {"money.py": DUPLICATED, "cash.py": DUPLICATE_TWIN})
        page = render_html(scan(root, use_git=False), root=root)
        assert "Table view" in page
        assert "<table>" in page

    def test_defines_both_themes(self, tmp_path: Path) -> None:
        root = make_repo(tmp_path, {"money.py": DUPLICATED, "cash.py": DUPLICATE_TWIN})
        page = render_html(scan(root, use_git=False), root=root)
        assert "prefers-color-scheme: dark" in page
        assert '[data-theme="dark"]' in page

    def test_can_omit_source_snippets(self, tmp_path: Path) -> None:
        root = make_repo(tmp_path, {"money.py": DUPLICATED, "cash.py": DUPLICATE_TWIN})
        page = render_html(scan(root, use_git=False), root=root, with_code=False)
        assert "format_cash" in page  # names still shown
        assert "<pre>" not in page  # bodies are not


class TestCli:
    def test_no_subcommand_prints_help(self) -> None:
        assert main([]) == EXIT_USAGE

    def test_missing_directory_is_a_usage_error(self, tmp_path: Path) -> None:
        assert main(["scan", str(tmp_path / "nope")]) == EXIT_USAGE

    def test_directory_without_sources_exits_unavailable(self, tmp_path: Path) -> None:
        (tmp_path / "notes.md").write_text("hello", encoding="utf-8")
        assert main(["scan", str(tmp_path)]) == EXIT_NOTHING_TO_SCAN

    def test_clean_scan_exits_zero(self, tmp_path: Path) -> None:
        root = make_repo(tmp_path, {"a.py": UNIQUE})
        assert main(["scan", str(root), "--no-git", "--quiet"]) == EXIT_OK

    def test_findings_alone_do_not_fail(self, tmp_path: Path) -> None:
        root = make_repo(tmp_path, {"money.py": DUPLICATED, "cash.py": DUPLICATE_TWIN})
        assert main(["scan", str(root), "--no-git", "--quiet"]) == EXIT_OK

    def test_fail_on_findings_exits_one(self, tmp_path: Path) -> None:
        root = make_repo(tmp_path, {"money.py": DUPLICATED, "cash.py": DUPLICATE_TWIN})
        code = main(["scan", str(root), "--no-git", "--quiet", "--fail-on-findings"])
        assert code == EXIT_FINDINGS

    def test_fail_on_findings_is_quiet_when_clean(self, tmp_path: Path) -> None:
        root = make_repo(tmp_path, {"a.py": UNIQUE})
        code = main(["scan", str(root), "--no-git", "--quiet", "--fail-on-findings"])
        assert code == EXIT_OK

    def test_writes_both_outputs(self, tmp_path: Path) -> None:
        root = make_repo(tmp_path, {"money.py": DUPLICATED, "cash.py": DUPLICATE_TWIN})
        out_json = tmp_path / "out" / "audit.json"
        out_html = tmp_path / "out" / "audit.html"
        main(
            [
                "scan",
                str(root),
                "--no-git",
                "--quiet",
                "--json",
                str(out_json),
                "--html",
                str(out_html),
            ]
        )
        assert json.loads(out_json.read_text())["schema_version"] == SCHEMA_VERSION
        assert out_html.read_text().startswith("<!doctype html>")
