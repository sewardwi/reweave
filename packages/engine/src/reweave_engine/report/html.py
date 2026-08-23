"""Self-contained HTML audit report.

One file, no network, no external assets — it has to open from a laptop with no internet, and
`reweave-audit` runs on private code where phoning out for a font would be a betrayal of the
whole pitch (D10).

Form choices follow the data's job rather than habit. Nothing here is categorical: removable
lines are *magnitude* (sequential blue, one hue), resolution coverage is *a ratio against a
limit* (a meter, not a two-slice pie), and remediable/blocked is *state* (reserved status
colors, always with an icon and a word so color never carries meaning alone). The single number
the report leads with is a hero figure, not a one-bar chart.

Accessibility, concretely: light and dark are each selected against their own surface rather
than flipped; a full table view ships alongside the visual list via native `<details>`, so
every value is reachable without reading a bar; and the status badge pairs a glyph with text.
"""

from __future__ import annotations

import html
from pathlib import Path

from reweave_engine.report.model import AuditReport, ClusterReport
from reweave_engine.scan import read_snippet

#: Palette roles. Sequential blue for magnitude; reserved status colors for state; chrome and
#: ink from the documented scale. Dark is stepped for the dark surface, not an inverted light.
_STYLE = """
:root {
  color-scheme: light;
  --surface: #fcfcfb;
  --plane: #f9f9f7;
  --ink: #0b0b0b;
  --ink-2: #52514e;
  --ink-muted: #898781;
  --rule: #e1e0d9;
  --baseline: #c3c2b7;
  --border: rgba(11, 11, 11, 0.10);
  --seq: #2a78d6;
  --seq-track: #cde2fb;
  --good: #0ca30c;
  --warn: #fab219;
  --shadow: 0 1px 2px rgba(11,11,11,.04), 0 8px 24px rgba(11,11,11,.05);
}
@media (prefers-color-scheme: dark) {
  :root:where(:not([data-theme="light"])) {
    color-scheme: dark;
    --surface: #1a1a19; --plane: #0d0d0d; --ink: #ffffff; --ink-2: #c3c2b7;
    --ink-muted: #898781; --rule: #2c2c2a; --baseline: #383835;
    --border: rgba(255,255,255,0.10);
    --seq: #3987e5; --seq-track: #184f95; --good: #0ca30c; --warn: #fab219;
    --shadow: none;
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --surface: #1a1a19; --plane: #0d0d0d; --ink: #ffffff; --ink-2: #c3c2b7;
  --ink-muted: #898781; --rule: #2c2c2a; --baseline: #383835;
  --border: rgba(255,255,255,0.10);
  --seq: #3987e5; --seq-track: #184f95; --good: #0ca30c; --warn: #fab219;
  --shadow: none;
}

* { box-sizing: border-box; }
body {
  margin: 0; padding: 0 20px 72px;
  background: var(--plane); color: var(--ink);
  font: 15px/1.55 system-ui, -apple-system, "Segoe UI", sans-serif;
  -webkit-font-smoothing: antialiased;
}
.wrap { max-width: 940px; margin: 0 auto; }
a { color: inherit; }

header { padding: 40px 0 8px; }
.eyebrow { font-size: 12px; letter-spacing: .08em; text-transform: uppercase;
  color: var(--ink-muted); margin: 0 0 6px; }
h1 { font-size: 22px; margin: 0 0 6px; font-weight: 650; overflow-wrap: anywhere; }
.sub { color: var(--ink-2); font-size: 13px; margin: 0; }
.theme-btn { position: absolute; top: 40px; right: 20px; font: inherit; font-size: 13px;
  background: var(--surface); color: var(--ink-2); border: 1px solid var(--border);
  border-radius: 8px; padding: 6px 12px; cursor: pointer; }
.theme-btn:hover { color: var(--ink); }

.card { background: var(--surface); border: 1px solid var(--border);
  border-radius: 14px; box-shadow: var(--shadow); }

.hero { padding: 28px 26px; margin: 24px 0 16px; }
.hero .figure { font-size: 56px; line-height: 1.05; font-weight: 680; letter-spacing: -.02em; }
.hero .unit { font-size: 18px; font-weight: 550; color: var(--ink-2); margin-left: 6px; }
.hero .caption { color: var(--ink-2); margin: 10px 0 0; max-width: 62ch; }
.hero .method { color: var(--ink-muted); font-size: 12px; margin: 8px 0 0; }

.kpis { display: grid; gap: 12px; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  margin-bottom: 16px; }
.kpi { padding: 16px 18px; }
.kpi .label { font-size: 12.5px; color: var(--ink-2); margin: 0 0 6px; }
.kpi .value { font-size: 26px; font-weight: 640; letter-spacing: -.01em; }
.kpi .note { font-size: 12px; color: var(--ink-muted); margin: 4px 0 0; }

.meter-card { padding: 18px 20px; margin-bottom: 28px; }
.meter-head { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; }
.meter-head .label { font-size: 13px; color: var(--ink-2); }
.meter-head .value { font-size: 15px; font-weight: 620; }
.meter { height: 10px; border-radius: 5px; background: var(--seq-track);
  margin-top: 10px; overflow: hidden; }
.meter > i { display: block; height: 100%; background: var(--seq);
  border-radius: 0 5px 5px 0; }
.meter-note { font-size: 12px; color: var(--ink-muted); margin: 8px 0 0; }

h2 { font-size: 15px; font-weight: 640; margin: 28px 0 4px; }
.section-note { font-size: 12.5px; color: var(--ink-muted); margin: 0 0 12px; }

.cluster { padding: 18px 20px; margin-bottom: 12px; }
.cluster-top { display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; }
.cluster-title { font-weight: 600; font-size: 14.5px; }
.cluster-sub { color: var(--ink-2); font-size: 12.5px; margin-top: 3px; }
.bar-row { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: center;
  gap: 10px; margin: 12px 0 4px; }
.bar-track { min-width: 0; }
.bar { height: 14px; background: var(--seq); border-radius: 0 4px 4px 0; min-width: 3px; }
.bar-value { font-size: 12.5px; color: var(--ink-2); font-variant-numeric: tabular-nums;
  white-space: nowrap; }

.badge { display: inline-flex; align-items: center; gap: 6px; white-space: nowrap;
  font-size: 12px; font-weight: 550; color: var(--ink-2);
  border: 1px solid var(--border); border-radius: 999px; padding: 3px 10px; }
.badge .dot { width: 8px; height: 8px; border-radius: 50%; flex: none; }
.badge.ok .dot { background: var(--good); }
.badge.blocked .dot { background: var(--warn); }

.metrics { display: flex; flex-wrap: wrap; gap: 18px; margin-top: 10px;
  font-size: 12.5px; color: var(--ink-2); }
.metrics b { font-weight: 600; color: var(--ink); font-variant-numeric: tabular-nums; }

.units { margin: 12px 0 0; padding: 0; list-style: none; }
.units li { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12.5px;
  color: var(--ink-2); padding: 2px 0; overflow-wrap: anywhere; }

details { margin-top: 12px; }
summary { cursor: pointer; font-size: 12.5px; color: var(--ink-2); }
summary:hover { color: var(--ink); }
.evidence { display: grid; gap: 12px; grid-template-columns: 1fr 1fr; margin-top: 10px; }
@media (max-width: 720px) { .evidence { grid-template-columns: 1fr; } }
.snippet { border: 1px solid var(--border); border-radius: 10px; overflow: hidden; }
.snippet .loc { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 11.5px;
  color: var(--ink-2); padding: 7px 10px; border-bottom: 1px solid var(--rule);
  background: var(--plane); overflow-wrap: anywhere; }
.snippet pre { margin: 0; padding: 10px; overflow-x: auto; font-size: 12px; line-height: 1.5;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.pairline { font-size: 12.5px; color: var(--ink-2); margin: 12px 0 0; }

table { width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 10px; }
th, td { text-align: left; padding: 7px 10px; border-bottom: 1px solid var(--rule); }
th { font-weight: 600; color: var(--ink-2); font-size: 12px; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
caption { text-align: left; color: var(--ink-muted); font-size: 12px; padding-bottom: 6px; }

.empty { padding: 40px 26px; text-align: center; }
.empty .mark { font-size: 30px; }
.empty h2 { margin: 10px 0 6px; font-size: 17px; }
.empty p { color: var(--ink-2); margin: 0 auto; max-width: 52ch; }

footer { margin-top: 34px; padding-top: 18px; border-top: 1px solid var(--rule);
  color: var(--ink-muted); font-size: 12px; }
footer h3 { font-size: 12.5px; color: var(--ink-2); margin: 0 0 6px; }
footer li { margin-bottom: 3px; }
"""

_THEME_SCRIPT = """
(function () {
  var root = document.documentElement;
  var stored = null;
  try { stored = localStorage.getItem('reweave-theme'); } catch (e) {}
  if (stored) root.setAttribute('data-theme', stored);
  var btn = document.createElement('button');
  btn.className = 'theme-btn';
  btn.type = 'button';
  var label = function () {
    var dark = root.getAttribute('data-theme') === 'dark' ||
      (!root.getAttribute('data-theme') &&
       window.matchMedia('(prefers-color-scheme: dark)').matches);
    btn.textContent = dark ? 'Light theme' : 'Dark theme';
    btn.setAttribute('aria-label', btn.textContent);
  };
  btn.addEventListener('click', function () {
    var dark = root.getAttribute('data-theme') === 'dark' ||
      (!root.getAttribute('data-theme') &&
       window.matchMedia('(prefers-color-scheme: dark)').matches);
    var next = dark ? 'light' : 'dark';
    root.setAttribute('data-theme', next);
    try { localStorage.setItem('reweave-theme', next); } catch (e) {}
    label();
  });
  label();
  document.body.appendChild(btn);
})();
"""


def _esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def _compact(value: int) -> str:
    """1,284 / 12.9K / 4.2M — stat-tile figures stay short enough to scan."""
    if value < 10_000:
        return f"{value:,}"
    if value < 1_000_000:
        return f"{value / 1_000:.1f}K".replace(".0K", "K")
    return f"{value / 1_000_000:.1f}M".replace(".0M", "M")


def _plural(count: int, singular: str, plural: str | None = None) -> str:
    return singular if count == 1 else (plural or singular + "s")


def _badge(cluster: ClusterReport) -> str:
    if cluster.safely_remediable:
        return '<span class="badge ok"><span class="dot"></span>Safe to consolidate</span>'
    reasons = ", ".join(reason.replace("_", " ") for reason in cluster.blocked_reasons)
    detail = f" — {_esc(reasons)}" if reasons else ""
    return f'<span class="badge blocked"><span class="dot"></span>Needs review{detail}</span>'


def _cluster_card(cluster: ClusterReport, root: Path, widest: int, *, with_code: bool) -> str:
    width = 4 if widest == 0 else max(4, round(100 * cluster.removable_lines / widest))
    primary = cluster.units[0]
    others = len(cluster.units) - 1
    churn = "—" if cluster.churn is None else f"{cluster.churn}"

    parts = [
        '<article class="card cluster">',
        '<div class="cluster-top"><div>',
        f'<div class="cluster-title">{_esc(primary.name)}'
        f"{f' and {others} more' if others else ''}</div>",
        f'<div class="cluster-sub">{_esc(primary.path)}</div>',
        f"</div>{_badge(cluster)}</div>",
        '<div class="bar-row"><div class="bar-track">',
        f'<div class="bar" style="width:{width}%" role="img" '
        f'aria-label="{cluster.removable_lines} removable lines"></div></div>',
        f'<span class="bar-value">{cluster.removable_lines:,} lines</span>',
        "</div>",
        '<div class="metrics">'
        f"<span>Removable lines <b>{cluster.removable_lines:,}</b></span>"
        f"<span>Resolved call sites <b>{cluster.call_sites:,}</b></span>"
        f"<span>Commits (90d) <b>{churn}</b></span>"
        f"<span>Copies <b>{cluster.unit_count}</b></span>"
        "</div>",
        '<ul class="units">',
    ]
    for unit in cluster.units:
        parts.append(f"<li>{_esc(unit.location)} · {_esc(unit.name)}</li>")
    parts.append("</ul>")

    for pair in cluster.evidence:
        parts.append(
            "<details><summary>"
            f"{_esc(pair.left.name)} ↔ {_esc(pair.right.name)} — "
            f"{pair.structural_percent}% structural, {pair.textual_percent}% textual"
            "</summary>"
            f'<p class="pairline">{_esc(pair.structural_method)} · '
            f"{_esc(pair.textual_method)}</p>"
        )
        if with_code:
            parts.append('<div class="evidence">')
            for side in (pair.left, pair.right):
                snippet = read_snippet(root, side)
                parts.append(
                    '<div class="snippet">'
                    f'<div class="loc">{_esc(side.location)}</div>'
                    f"<pre>{_esc(snippet)}</pre></div>"
                )
            parts.append("</div>")
        parts.append("</details>")

    parts.append("</article>")
    return "".join(parts)


def _score_method(report: AuditReport) -> str:
    return report.clusters[0].score_method if report.clusters else "blast_radius_v1"


def _table(report: AuditReport) -> str:
    rows = [
        "<tr>"
        f"<td>{_esc(cluster.units[0].name)}</td>"
        f"<td>{_esc(cluster.units[0].path)}</td>"
        f'<td class="num">{cluster.unit_count}</td>'
        f'<td class="num">{cluster.removable_lines:,}</td>'
        f'<td class="num">{cluster.call_sites:,}</td>'
        f'<td class="num">{"—" if cluster.churn is None else cluster.churn}</td>'
        f'<td class="num">{cluster.score:,.1f}</td>'
        f"<td>{'Safe' if cluster.safely_remediable else 'Needs review'}</td>"
        "</tr>"
        for cluster in report.clusters
    ]
    return (
        "<details><summary>Table view — every cluster, every value</summary>"
        "<table><caption>Ranked by blast radius "
        f"({_esc(_score_method(report))}).</caption>"
        "<thead><tr><th>Symbol</th><th>Path</th><th class='num'>Copies</th>"
        "<th class='num'>Removable</th><th class='num'>Call sites</th>"
        "<th class='num'>Commits</th><th class='num'>Score</th><th>State</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></details>"
    )


def _empty(report: AuditReport) -> str:
    return (
        '<section class="card empty">'
        '<div class="mark" aria-hidden="true">✳</div>'
        "<h2>No duplicate logic found</h2>"
        f"<p>Reweave read {report.coverage.units_extracted:,} "
        f"{_plural(report.coverage.units_extracted, 'function')} across "
        f"{report.coverage.files_scanned:,} {_plural(report.coverage.files_scanned, 'file')} "
        "and found nothing worth consolidating. That is a good result, not an empty one — "
        "though it also means this scan has nothing to show you, so treat it as a clean bill "
        "rather than proof of absence.</p></section>"
    )


def render_html(report: AuditReport, *, root: Path | None = None, with_code: bool = True) -> str:
    """Render a complete, self-contained HTML document."""
    source_root = root or Path(report.root)
    coverage = report.coverage
    widest = max((c.removable_lines for c in report.clusters), default=0)

    churn_note = (
        "Commit counts come from git history over the last 90 days."
        if coverage.churn_available
        else "Commit counts are unavailable — no readable git history, so churn shows as “—” "
        "rather than zero."
    )

    body: list[str] = [
        '<div class="wrap">',
        "<header>",
        '<p class="eyebrow">Reweave audit</p>',
        f"<h1>{_esc(Path(report.root).name or report.root)}</h1>",
        f'<p class="sub">{_esc(report.generated_at)} · {_esc(report.detector)} · '
        f"scanned in {report.duration_seconds:g}s</p>",
        "</header>",
    ]

    if report.clusters:
        body += [
            '<section class="card hero">',
            f'<div class="figure">{_compact(report.total_removable_lines)}'
            '<span class="unit">lines</span></div>',
            '<p class="caption">Duplicated lines that would disappear if every cluster below '
            "were consolidated. One implementation in each cluster survives, so this counts "
            "the copies — not the total lines involved.</p>",
            f'<p class="method">{report.duplicated_line_percent:.1f}% of the '
            f"{coverage.lines_in_units:,} lines Reweave parsed into functions.</p>",
            "</section>",
            '<div class="kpis">',
            f'<div class="card kpi"><p class="label">Duplicate clusters</p>'
            f'<div class="value">{len(report.clusters):,}</div>'
            f'<p class="note">{report.remediable_clusters:,} safe to consolidate</p></div>',
            f'<div class="card kpi"><p class="label">Functions scanned</p>'
            f'<div class="value">{_compact(coverage.units_extracted)}</div>'
            f'<p class="note">across {coverage.files_scanned:,} '
            f"{_plural(coverage.files_scanned, 'file')}</p></div>",
            f'<div class="card kpi"><p class="label">Pairs compared</p>'
            f'<div class="value">{_compact(coverage.candidate_pairs)}</div>'
            f'<p class="note">of {_compact(coverage.total_possible_pairs)} possible</p></div>',
            f'<div class="card kpi"><p class="label">Largest cluster</p>'
            f'<div class="value">{max(c.unit_count for c in report.clusters)}</div>'
            '<p class="note">copies of one behavior</p></div>',
            "</div>",
            '<section class="card meter-card">',
            '<div class="meter-head"><span class="label">Files with a fully resolved call graph'
            f'</span><span class="value">{coverage.files_fully_resolved:,} of '
            f"{coverage.files_scanned:,}</span></div>",
            f'<div class="meter"><i style="width:{coverage.resolution_percent}%"></i></div>',
            '<p class="meter-note">Consolidation is only offered for files where every caller '
            "is visible. Dynamic imports, wildcard imports and path aliases hide callers, so "
            "those files are counted out rather than guessed at.</p>",
            "</section>",
            "<h2>Clusters by blast radius</h2>",
            '<p class="section-note">Ranked by removable lines, resolved call sites and recent '
            "commits — the components are shown separately below each heading.</p>",
        ]
        for cluster in report.clusters:
            body.append(_cluster_card(cluster, source_root, widest, with_code=with_code))
        body.append(_table(report))
    else:
        body.append(_empty(report))

    unresolved_rows = "".join(
        f"<li>{_esc(reason.replace('_', ' '))}: {count:,}</li>"
        for reason, count in coverage.unresolved_by_reason.items()
    )
    body += [
        "<footer>",
        "<h3>How to read these numbers</h3><ul>",
        "<li><b>Removable lines</b> — total lines in each cluster minus its largest member, "
        "since one implementation has to survive.</li>",
        "<li><b>Structural similarity</b> — overlap of normalized syntax trees with identifiers "
        "alpha-renamed; blind to renaming, sensitive to operators and argument order.</li>",
        "<li><b>Textual overlap</b> — raw token overlap, the measure text-based tools use. "
        "Shown beside the structural figure because the two disagreeing is informative.</li>",
        f"<li><b>Blast-radius score</b> — a published roll-up ({_esc(_score_method(report))}) "
        "of removable lines, call sites and churn. The components above it are the "
        "measurements; this is a ranking aid.</li>",
        f"<li>{_esc(churn_note)}</li>",
        "</ul>",
    ]
    if unresolved_rows:
        body += [
            "<h3>References we did not follow</h3>",
            "<p>Counted rather than guessed at, so the coverage figure above means something."
            "</p><ul>",
            unresolved_rows,
            "</ul>",
        ]
    if coverage.candidates_truncated:
        body.append(
            "<p><b>This scan was truncated.</b> The candidate budget was reached, so some "
            "pairs were never compared and this report understates duplication.</p>"
        )
    body += [
        f"<p>Reweave {_esc(report.tool_version)} · report schema "
        f"{_esc(report.schema_version)} · generated locally; no code left this machine.</p>",
        "</footer></div>",
    ]

    return (
        "<!doctype html>\n"
        '<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>Reweave audit — {_esc(Path(report.root).name)}</title>"
        f"<style>{_STYLE}</style></head><body>"
        + "".join(body)
        + f"<script>{_THEME_SCRIPT}</script>"
        "</body></html>\n"
    )
