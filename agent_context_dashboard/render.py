from __future__ import annotations

from datetime import datetime, timezone

from .models import ReportCard


def render_markdown(cards: list[ReportCard], generated_at: datetime | None = None) -> str:
    stamp = generated_at or datetime.now(timezone.utc)
    lines: list[str] = [
        "# Agent Context Asset Health Dashboard",
        "",
        f"Generated: {stamp.replace(microsecond=0).isoformat()}",
        "",
        "## Summary",
        "",
    ]

    total = len(cards)
    risky = sum(1 for card in cards if card.is_risky)
    warnings = sum(card.warning_count for card in cards)
    unknown = sum(1 for card in cards if card.tool == "unknown")
    passing = sum(1 for card in cards if card.status == "pass")

    lines.extend(
        [
            f"- Reports scanned: {total}",
            f"- Passing reports: {passing}",
            f"- Reports with risk: {risky}",
            f"- Warnings: {warnings}",
            f"- Unknown schemas: {unknown}",
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


def _risk_lines(cards: list[ReportCard]) -> list[str]:
    lines: list[str] = []
    for card in cards:
        if card.tool == "unknown":
            lines.append(f"- `{card.source_path.name}`: unknown schema.")
        for warning in card.warnings[:5]:
            lines.append(f"- `{card.source_path.name}`: {warning}")
    return lines


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
