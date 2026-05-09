from __future__ import annotations

import json
from html import escape
from datetime import datetime, timezone
from typing import Any

from .compare import CompareTrend, ComparisonResult, compare_trends_payload, compare_trends_summary, comparison_payload
from .models import ReportCard


def render_markdown(
    cards: list[ReportCard],
    generated_at: datetime | None = None,
    comparison: ComparisonResult | None = None,
    compare_trends: list[CompareTrend] | None = None,
) -> str:
    stamp = generated_at or datetime.now(timezone.utc)
    summary = _summary_counts(cards)
    lines: list[str] = [
        "# Agent Context Asset Health Dashboard",
        "",
        f"Generated: {stamp.replace(microsecond=0).isoformat()}",
        "",
        "## Summary",
        "",
    ]

    lines.extend(
        [
            f"- Reports scanned: {summary['reports_scanned']}",
            f"- Passing reports: {summary['passing_reports']}",
            f"- Reports with risk: {summary['reports_with_risk']}",
            f"- Warnings: {summary['warnings']}",
            f"- Unknown schemas: {summary['unknown_schemas']}",
            "",
            "## Reports",
            "",
        ]
    )

    if cards:
        for card in cards:
            lines.extend(_render_card(card))
    else:
        lines.extend(["No JSON reports were found in the input directory.", ""])

    lines.extend(["## Risks And Warnings", ""])
    risk_lines = _risk_lines(cards)
    if risk_lines:
        lines.extend(risk_lines)
    else:
        lines.append("No risks or warnings were detected.")
    lines.append("")

    if comparison is not None:
        lines.extend(_render_comparison(comparison))
    if compare_trends:
        lines.extend(_render_compare_trends(compare_trends))

    lines.extend(["## Next Actions", ""])
    actions = _next_actions(cards)
    if actions:
        lines.extend(f"- {action}" for action in actions)
    else:
        lines.append("- Add JSON reports from agent-context-audit, agent-context-lint, or agent-instruction-guard.")
    lines.append("")

    return "\n".join(lines)


def render_json(
    cards: list[ReportCard],
    generated_at: datetime | None = None,
    comparison: ComparisonResult | None = None,
    compare_trends: list[CompareTrend] | None = None,
) -> str:
    payload = dashboard_payload(
        cards,
        generated_at=generated_at,
        comparison=comparison,
        compare_trends=compare_trends,
    )
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def render_html(
    cards: list[ReportCard],
    generated_at: datetime | None = None,
    comparison: ComparisonResult | None = None,
    compare_trends: list[CompareTrend] | None = None,
) -> str:
    stamp = generated_at or datetime.now(timezone.utc)
    stamp_text = stamp.replace(microsecond=0).isoformat()
    summary = _summary_counts(cards)
    overall_status = _overall_status(cards, comparison)
    risk_items = _risk_payload(cards)
    sarif_cards = [card for card in cards if card.tool == "sarif" or card.details.get("sarif_version") is not None]

    parts = [
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        "<title>Agent Context Asset Health Dashboard</title>",
        "<style>",
        _html_styles(),
        "</style>",
        "</head>",
        "<body>",
        "<main>",
        "<header>",
        "<h1>Agent Context Asset Health Dashboard</h1>",
        f"<p>Generated: <time datetime=\"{_h(stamp_text)}\">{_h(stamp_text)}</time></p>",
        f'<p class="status status-{_h(overall_status)}">Overall status: {_h(overall_status.replace("_", " "))}</p>',
        "</header>",
        '<section aria-labelledby="summary-heading">',
        '<h2 id="summary-heading">Summary</h2>',
        '<dl class="summary-grid">',
    ]
    for label, key in (
        ("Reports scanned", "reports_scanned"),
        ("Passing reports", "passing_reports"),
        ("Reports with risk", "reports_with_risk"),
        ("Warnings", "warnings"),
        ("Unknown schemas", "unknown_schemas"),
    ):
        parts.extend([f"<div><dt>{_h(label)}</dt><dd>{summary[key]}</dd></div>"])
    parts.extend(["</dl>", "</section>"])

    parts.extend(_render_html_reports(cards))
    parts.extend(_render_html_risks(risk_items))
    if comparison is not None:
        parts.extend(_render_html_comparison(comparison))
    if compare_trends:
        parts.extend(_render_html_compare_trends(compare_trends))
    if sarif_cards:
        parts.extend(_render_html_sarif(sarif_cards))
    parts.extend(_render_html_next_actions(cards))
    parts.extend(["</main>", "</body>", "</html>", ""])
    return "\n".join(parts)


def dashboard_payload(
    cards: list[ReportCard],
    generated_at: datetime | None = None,
    comparison: ComparisonResult | None = None,
    compare_trends: list[CompareTrend] | None = None,
) -> dict[str, Any]:
    stamp = generated_at or datetime.now(timezone.utc)
    payload = {
        "generated_at": stamp.replace(microsecond=0).isoformat(),
        "summary": _summary_counts(cards),
        "reports": [_report_payload(card) for card in cards],
        "risks_and_warnings": _risk_payload(cards),
        "next_actions": _next_actions(cards)
        or ["Add JSON reports from agent-context-audit, agent-context-lint, or agent-instruction-guard."],
    }
    if comparison is not None:
        payload["comparison"] = comparison_payload(comparison)
    if compare_trends:
        payload["compare_summary"] = compare_trends_summary(compare_trends)
        payload["compare_entries"] = compare_trends_payload(compare_trends)
    return payload


def _render_card(card: ReportCard) -> list[str]:
    lines = [
        f"### {card.title}",
        "",
        f"- Tool: {card.tool}",
        f"- Source: `{_source_id(card)}`",
        f"- Status: {card.status}",
        f"- Summary: {card.summary}",
    ]
    for key, value in sorted(card.details.items()):
        if value is not None:
            lines.append(f"- {key.replace('_', ' ').title()}: {value}")
    lines.append("")
    return lines


def _summary_counts(cards: list[ReportCard]) -> dict[str, int]:
    return {
        "reports_scanned": len(cards),
        "passing_reports": sum(1 for card in cards if card.status == "pass"),
        "reports_with_risk": sum(1 for card in cards if card.is_risky),
        "warnings": sum(card.warning_count for card in cards),
        "unknown_schemas": sum(1 for card in cards if card.tool == "unknown"),
    }


def _overall_status(cards: list[ReportCard], comparison: ComparisonResult | None = None) -> str:
    if comparison is not None and comparison.has_regressions:
        return "regression"
    if any(card.is_risky for card in cards):
        return "risk"
    if any(card.tool == "unknown" for card in cards):
        return "unknown"
    if any(card.warning_count for card in cards):
        return "warning"
    return "pass"


def _report_payload(card: ReportCard) -> dict[str, Any]:
    return {
        "source": _source_id(card),
        "tool": card.tool,
        "title": card.title,
        "status": card.status,
        "summary": card.summary,
        "risk_count": card.risk_count,
        "warning_count": card.warning_count,
        "warnings": list(card.warnings),
        "next_actions": list(card.next_actions),
        "details": _json_safe(card.details),
    }


def _risk_lines(cards: list[ReportCard]) -> list[str]:
    lines: list[str] = []
    for card in cards:
        if card.tool == "unknown":
            lines.append(f"- `{_source_id(card)}`: unknown schema.")
        for warning in card.warnings[:5]:
            lines.append(f"- `{_source_id(card)}`: {warning}")
    return lines


def _risk_payload(cards: list[ReportCard]) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for card in cards:
        if card.tool == "unknown":
            items.append(
                {
                    "source": _source_id(card),
                    "kind": "unknown_schema",
                    "message": "unknown schema",
                }
            )
        for warning in card.warnings[:5]:
            items.append(
                {
                    "source": _source_id(card),
                    "kind": "warning",
                    "message": warning,
                }
            )
    return items


def _render_html_reports(cards: list[ReportCard]) -> list[str]:
    lines = [
        '<section aria-labelledby="reports-heading">',
        '<h2 id="reports-heading">Reports</h2>',
    ]
    if not cards:
        lines.extend(["<p>No JSON reports were found in the input directory.</p>", "</section>"])
        return lines

    lines.extend(
        [
            '<div class="table-wrap">',
            "<table>",
            "<thead>",
            "<tr>"
            '<th scope="col">Source</th><th scope="col">Tool</th><th scope="col">Title</th>'
            '<th scope="col">Status</th><th scope="col">Risks</th><th scope="col">Warnings</th>'
            '<th scope="col">Summary</th>'
            "</tr>",
            "</thead>",
            "<tbody>",
        ]
    )
    for card in cards:
        lines.extend(
            [
                "<tr>",
                f"<td><code>{_h(_source_id(card))}</code></td>",
                f"<td>{_h(card.tool)}</td>",
                f"<td>{_h(card.title)}</td>",
                f'<td><span class="status status-{_h(_status_class(card.status))}">{_h(card.status)}</span></td>',
                f"<td>{card.risk_count}</td>",
                f"<td>{card.warning_count}</td>",
                f"<td>{_h(card.summary)}</td>",
                "</tr>",
            ]
        )
    lines.extend(["</tbody>", "</table>", "</div>", "</section>"])
    return lines


def _render_html_risks(risk_items: list[dict[str, str]]) -> list[str]:
    lines = [
        '<section aria-labelledby="risks-heading">',
        '<h2 id="risks-heading">Top Warnings And Errors</h2>',
    ]
    if not risk_items:
        lines.extend(["<p>No risks or warnings were detected.</p>", "</section>"])
        return lines

    lines.append("<ul>")
    for item in risk_items[:12]:
        lines.append(
            f"<li><strong>{_h(item['kind'].replace('_', ' '))}</strong> "
            f"<code>{_h(item['source'])}</code>: {_h(item['message'])}</li>"
        )
    lines.extend(["</ul>", "</section>"])
    return lines


def _render_html_comparison(comparison: ComparisonResult) -> list[str]:
    summary = comparison.summary
    lines = [
        '<section aria-labelledby="comparison-heading">',
        '<h2 id="comparison-heading">Baseline Comparison</h2>',
        '<dl class="summary-grid">',
    ]
    for label, key in (
        ("Total comparison items", "total_items"),
        ("Regression items", "regressions"),
        ("New unknown schemas", "new_unknown_schema"),
        ("New risks", "new_risk"),
        ("Increased warnings", "increased_warnings"),
        ("Resolved risks", "resolved_risk"),
    ):
        lines.append(f"<div><dt>{_h(label)}</dt><dd>{summary[key]}</dd></div>")
    lines.extend(["</dl>"])
    if comparison.items:
        lines.append("<ul>")
        for item in comparison.items:
            regression = " regression" if item.is_regression else ""
            lines.append(f'<li class="{regression.strip()}">{_h(item.kind)}: {_h(item.message)}</li>')
        lines.append("</ul>")
    else:
        lines.append("<p>No baseline changes detected.</p>")
    lines.append("</section>")
    return lines


def _render_html_compare_trends(trends: list[CompareTrend]) -> list[str]:
    summary = compare_trends_summary(trends)
    lines = [
        '<section aria-labelledby="compare-trends-heading">',
        '<h2 id="compare-trends-heading">Score Trends</h2>',
        '<dl class="summary-grid">',
    ]
    for label, key in (
        ("Compare entries", "total_entries"),
        ("Improved entries", "improved_entries"),
        ("Regressed entries", "regressed_entries"),
        ("Total score delta", "total_score_delta"),
        ("Files changed", "changed_file_count"),
        ("Rule issue delta", "rule_issue_delta"),
    ):
        lines.append(f"<div><dt>{_h(label)}</dt><dd>{_h(summary[key])}</dd></div>")
    lines.extend(["</dl>", '<div class="table-wrap">', "<table>", "<thead>"])
    lines.append(
        "<tr>"
        '<th scope="col">Source</th><th scope="col">Baseline</th><th scope="col">Current</th>'
        '<th scope="col">Delta</th><th scope="col">Changed</th><th scope="col">Added</th>'
        '<th scope="col">Removed</th><th scope="col">Improved</th><th scope="col">Regressed</th>'
        '<th scope="col">Rule Issues</th>'
        "</tr>"
    )
    lines.extend(["</thead>", "<tbody>"])
    for trend in trends:
        status_class = "pass" if trend.score_delta >= 0 else "regression"
        lines.extend(
            [
                "<tr>",
                f"<td><code>{_h(trend.source)}</code></td>",
                f"<td>{_h(_format_number(trend.baseline_score))}</td>",
                f"<td>{_h(_format_number(trend.current_score))}</td>",
                f'<td class="{_h(status_class)}">{_h(_signed_number(trend.score_delta))}</td>',
                f"<td>{trend.changed_file_count}</td>",
                f"<td>{trend.added_file_count}</td>",
                f"<td>{trend.removed_file_count}</td>",
                f"<td>{trend.files_improved_count}</td>",
                f"<td>{trend.files_regressed_count}</td>",
                f"<td>{_h(_signed_int(trend.rule_issue_delta))}</td>",
                "</tr>",
            ]
        )
    lines.extend(["</tbody>", "</table>", "</div>", "</section>"])
    return lines


def _render_html_sarif(cards: list[ReportCard]) -> list[str]:
    lines = [
        '<section aria-labelledby="sarif-heading">',
        '<h2 id="sarif-heading">SARIF Reports</h2>',
        "<ul>",
    ]
    for card in cards:
        details = card.details
        lines.append(
            "<li>"
            f"<code>{_h(_source_id(card))}</code>: {_h(card.title)}; "
            f"results: {_h(details.get('results', 0))}; "
            f"errors: {_h(details.get('errors', 0))}; "
            f"warnings: {_h(details.get('warnings', 0))}; "
            f"notes: {_h(details.get('notes', 0))}"
            "</li>"
        )
    lines.extend(["</ul>", "</section>"])
    return lines


def _render_html_next_actions(cards: list[ReportCard]) -> list[str]:
    actions = _next_actions(cards) or ["Add JSON reports from agent-context-audit, agent-context-lint, or agent-instruction-guard."]
    lines = [
        '<section aria-labelledby="actions-heading">',
        '<h2 id="actions-heading">Next Actions</h2>',
        "<ul>",
    ]
    lines.extend(f"<li>{_h(action)}</li>" for action in actions)
    lines.extend(["</ul>", "</section>"])
    return lines


def _render_comparison(comparison: ComparisonResult) -> list[str]:
    summary = comparison.summary
    lines = [
        "## Baseline Comparison",
        "",
        f"- Total comparison items: {summary['total_items']}",
        f"- Regression items: {summary['regressions']}",
        f"- New unknown schemas: {summary['new_unknown_schema']}",
        f"- New risks: {summary['new_risk']}",
        f"- Increased warnings: {summary['increased_warnings']}",
        f"- Resolved risks: {summary['resolved_risk']}",
        "",
    ]
    if comparison.items:
        lines.extend(f"- {item.kind}: {item.message}" for item in comparison.items)
    else:
        lines.append("- No baseline changes detected.")
    lines.append("")
    return lines


def _render_compare_trends(trends: list[CompareTrend]) -> list[str]:
    summary = compare_trends_summary(trends)
    lines = [
        "## Score Trends",
        "",
        f"- Compare entries: {summary['total_entries']}",
        f"- Improved entries: {summary['improved_entries']}",
        f"- Regressed entries: {summary['regressed_entries']}",
        f"- Total score delta: {_signed_number(float(summary['total_score_delta']))}",
        f"- Files changed: {summary['changed_file_count']}",
        f"- Files improved/regressed: {summary['files_improved_count']}/{summary['files_regressed_count']}",
        f"- Rule issue delta: {_signed_int(int(summary['rule_issue_delta']))}",
        "",
    ]
    for trend in trends:
        lines.append(
            "- "
            f"`{trend.source}`: "
            f"{_format_number(trend.baseline_score)} -> {_format_number(trend.current_score)} "
            f"({_signed_number(trend.score_delta)}); "
            f"files changed/added/removed: {trend.changed_file_count}/{trend.added_file_count}/{trend.removed_file_count}; "
            f"files improved/regressed: {trend.files_improved_count}/{trend.files_regressed_count}; "
            f"rule issue delta: {_signed_int(trend.rule_issue_delta)}"
        )
    lines.append("")
    return lines


def _next_actions(cards: list[ReportCard]) -> list[str]:
    if not cards:
        return []

    actions: list[str] = []
    seen: set[str] = set()
    for card in cards:
        if card.tool == "unknown":
            candidate = f"Map `{_source_id(card)}` to a supported schema or review it manually."
            if candidate not in seen:
                actions.append(candidate)
                seen.add(candidate)
        if card.is_risky or card.warning_count:
            for action in card.next_actions:
                if action not in seen:
                    actions.append(action)
                    seen.add(action)

    if not actions:
        actions.append("Keep current report generation in CI or local maintenance scripts.")
    return actions[:8]


def _source_id(card: ReportCard) -> str:
    return card.source_path.as_posix()


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in sorted(value.items(), key=lambda item: str(item[0]))}
    return str(value)


def _h(value: Any) -> str:
    return escape(str(value), quote=True)


def _status_class(status: str) -> str:
    normalized = "".join(ch if ch.isalnum() else "-" for ch in status.lower()).strip("-")
    return normalized or "unknown"


def _format_number(value: float) -> str:
    return str(int(value)) if value.is_integer() else f"{value:.2f}".rstrip("0").rstrip(".")


def _signed_number(value: float) -> str:
    formatted = _format_number(abs(value))
    if value > 0:
        return f"+{formatted}"
    if value < 0:
        return f"-{formatted}"
    return formatted


def _signed_int(value: int) -> str:
    return f"+{value}" if value > 0 else str(value)


def _html_styles() -> str:
    return """
:root { color-scheme: light; --border: #d8dee4; --muted: #57606a; --bg: #ffffff; --soft: #f6f8fa; --text: #24292f; --risk: #bc4c00; --bad: #cf222e; --ok: #1a7f37; }
body { margin: 0; background: var(--bg); color: var(--text); font: 16px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
main { max-width: 1120px; margin: 0 auto; padding: 32px 20px 56px; }
header, section { border-bottom: 1px solid var(--border); padding: 20px 0; }
h1 { font-size: 2rem; margin: 0 0 8px; }
h2 { font-size: 1.35rem; margin: 0 0 16px; }
p { margin: 0 0 12px; }
code { background: var(--soft); border-radius: 4px; padding: 0.1rem 0.25rem; }
.summary-grid { display: grid; gap: 12px; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); margin: 0; }
.summary-grid div { border: 1px solid var(--border); border-radius: 6px; padding: 12px; background: var(--soft); }
dt { color: var(--muted); font-size: 0.9rem; }
dd { font-size: 1.5rem; font-weight: 700; margin: 4px 0 0; }
.table-wrap { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; min-width: 820px; }
th, td { border: 1px solid var(--border); padding: 9px 10px; text-align: left; vertical-align: top; }
th { background: var(--soft); }
.status { display: inline-block; border: 1px solid var(--border); border-radius: 999px; padding: 2px 10px; font-weight: 700; }
.status-pass { color: var(--ok); }
.status-risk, .status-warning, .status-warn, .status-unknown { color: var(--risk); }
.status-regression, .status-error, .status-fail, .status-failed, .status-blocked { color: var(--bad); }
.regression { color: var(--bad); }
ul { padding-left: 1.4rem; }
li { margin: 0.35rem 0; }
@media (max-width: 640px) { main { padding: 20px 14px 40px; } h1 { font-size: 1.55rem; } }
""".strip()
