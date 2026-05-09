from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from .models import ReportCard


def render_markdown(cards: list[ReportCard], generated_at: datetime | None = None) -> str:
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

    lines.extend(["## Next Actions", ""])
    actions = _next_actions(cards)
    if actions:
        lines.extend(f"- {action}" for action in actions)
    else:
        lines.append("- Add JSON reports from agent-context-audit, agent-context-lint, or agent-instruction-guard.")
    lines.append("")

    return "\n".join(lines)


def render_json(cards: list[ReportCard], generated_at: datetime | None = None) -> str:
    payload = dashboard_payload(cards, generated_at=generated_at)
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def dashboard_payload(cards: list[ReportCard], generated_at: datetime | None = None) -> dict[str, Any]:
    stamp = generated_at or datetime.now(timezone.utc)
    return {
        "generated_at": stamp.replace(microsecond=0).isoformat(),
        "summary": _summary_counts(cards),
        "reports": [_report_payload(card) for card in cards],
        "risks_and_warnings": _risk_payload(cards),
        "next_actions": _next_actions(cards)
        or ["Add JSON reports from agent-context-audit, agent-context-lint, or agent-instruction-guard."],
    }


def _render_card(card: ReportCard) -> list[str]:
    lines = [
        f"### {card.title}",
        "",
        f"- Tool: {card.tool}",
        f"- Source: `{card.source_path.name}`",
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


def _report_payload(card: ReportCard) -> dict[str, Any]:
    return {
        "source": card.source_path.name,
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
            lines.append(f"- `{card.source_path.name}`: unknown schema.")
        for warning in card.warnings[:5]:
            lines.append(f"- `{card.source_path.name}`: {warning}")
    return lines


def _risk_payload(cards: list[ReportCard]) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for card in cards:
        if card.tool == "unknown":
            items.append(
                {
                    "source": card.source_path.name,
                    "kind": "unknown_schema",
                    "message": "unknown schema",
                }
            )
        for warning in card.warnings[:5]:
            items.append(
                {
                    "source": card.source_path.name,
                    "kind": "warning",
                    "message": warning,
                }
            )
    return items


def _next_actions(cards: list[ReportCard]) -> list[str]:
    if not cards:
        return []

    actions: list[str] = []
    seen: set[str] = set()
    for card in cards:
        if card.tool == "unknown":
            candidate = f"Map `{card.source_path.name}` to a supported schema or review it manually."
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
