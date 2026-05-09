from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import ReportCard
from .reports import DashboardError


REGRESSION_KINDS = {"new_unknown_schema", "new_risk", "increased_warnings"}


class BaselineError(DashboardError):
    """Raised when a baseline dashboard cannot be read or compared."""


@dataclass(frozen=True)
class ComparisonItem:
    kind: str
    source: str
    tool: str
    message: str
    current_warning_count: int
    baseline_warning_count: int | None = None

    @property
    def is_regression(self) -> bool:
        return self.kind in REGRESSION_KINDS


@dataclass(frozen=True)
class ComparisonResult:
    summary: dict[str, int]
    items: list[ComparisonItem]

    @property
    def has_regressions(self) -> bool:
        return any(item.is_regression for item in self.items)


def load_baseline(path: Path | str) -> dict[tuple[str, str], dict[str, Any]]:
    baseline_path = Path(path)
    try:
        with baseline_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except FileNotFoundError as exc:
        raise BaselineError(f"Baseline dashboard does not exist: {baseline_path}") from exc
    except json.JSONDecodeError as exc:
        raise BaselineError(
            f"Malformed baseline JSON in {baseline_path}: line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc
    except OSError as exc:
        raise BaselineError(f"Could not read baseline dashboard {baseline_path}: {exc}") from exc

    return _dashboard_reports(payload, baseline_path)


def compare_to_baseline(cards: list[ReportCard], baseline: dict[tuple[str, str], dict[str, Any]]) -> ComparisonResult:
    items: list[ComparisonItem] = []

    for card in cards:
        key = _card_key(card)
        previous = baseline.get(key)
        source, tool = key

        if card.tool == "unknown" and previous is None:
            items.append(
                ComparisonItem(
                    kind="new_unknown_schema",
                    source=source,
                    tool=tool,
                    message=f"`{source}` is a new unknown schema.",
                    current_warning_count=card.warning_count,
                )
            )

        if card.is_risky and (previous is None or not _is_risky_payload(previous)):
            items.append(
                ComparisonItem(
                    kind="new_risk",
                    source=source,
                    tool=tool,
                    message=f"`{source}` now has risk for {tool}.",
                    current_warning_count=card.warning_count,
                    baseline_warning_count=_warning_count(previous) if previous is not None else None,
                )
            )

        if previous is not None:
            previous_warnings = _warning_count(previous)
            if card.warning_count > previous_warnings:
                items.append(
                    ComparisonItem(
                        kind="increased_warnings",
                        source=source,
                        tool=tool,
                        message=(
                            f"`{source}` warnings increased from {previous_warnings} "
                            f"to {card.warning_count} for {tool}."
                        ),
                        current_warning_count=card.warning_count,
                        baseline_warning_count=previous_warnings,
                    )
                )
            if _is_risky_payload(previous) and not card.is_risky:
                items.append(
                    ComparisonItem(
                        kind="resolved_risk",
                        source=source,
                        tool=tool,
                        message=f"`{source}` no longer has risk for {tool}.",
                        current_warning_count=card.warning_count,
                        baseline_warning_count=previous_warnings,
                    )
                )

    return ComparisonResult(summary=_summary(items), items=items)


def comparison_payload(comparison: ComparisonResult) -> dict[str, Any]:
    return {
        "summary": comparison.summary,
        "items": [
            {
                "kind": item.kind,
                "source": item.source,
                "tool": item.tool,
                "message": item.message,
                "current_warning_count": item.current_warning_count,
                "baseline_warning_count": item.baseline_warning_count,
                "is_regression": item.is_regression,
            }
            for item in comparison.items
        ],
    }


def _dashboard_reports(payload: Any, path: Path) -> dict[tuple[str, str], dict[str, Any]]:
    if not isinstance(payload, dict):
        raise BaselineError(f"Baseline is not a dashboard JSON object: {path}")
    if (
        not isinstance(payload.get("generated_at"), str)
        or not isinstance(payload.get("summary"), dict)
        or not isinstance(payload.get("reports"), list)
    ):
        raise BaselineError(f"Baseline is not a dashboard produced by --format json: {path}")

    reports: dict[tuple[str, str], dict[str, Any]] = {}
    for index, report in enumerate(payload["reports"]):
        if not isinstance(report, dict):
            raise BaselineError(f"Baseline report #{index + 1} is not an object: {path}")
        source = report.get("source")
        tool = report.get("tool")
        if not isinstance(source, str) or not source or not isinstance(tool, str) or not tool:
            raise BaselineError(f"Baseline report #{index + 1} is missing source or tool: {path}")
        if not isinstance(report.get("status"), str) or not isinstance(report.get("risk_count"), int):
            raise BaselineError(f"Baseline report #{index + 1} is missing dashboard risk fields: {path}")
        if not isinstance(report.get("warning_count"), int):
            raise BaselineError(f"Baseline report #{index + 1} is missing dashboard warning fields: {path}")
        reports[(source, tool)] = report
    return reports


def _card_key(card: ReportCard) -> tuple[str, str]:
    return (card.source_path.name, card.tool)


def _is_risky_payload(report: dict[str, Any]) -> bool:
    return _int_value(report.get("risk_count")) > 0 or str(report.get("status", "")).lower() in {
        "fail",
        "failed",
        "error",
        "blocked",
    }


def _warning_count(report: dict[str, Any]) -> int:
    return _int_value(report.get("warning_count"))


def _int_value(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    return 0


def _summary(items: list[ComparisonItem]) -> dict[str, int]:
    summary = {
        "total_items": len(items),
        "regressions": sum(1 for item in items if item.is_regression),
        "new_unknown_schema": 0,
        "new_risk": 0,
        "increased_warnings": 0,
        "resolved_risk": 0,
    }
    for item in items:
        if item.kind in summary:
            summary[item.kind] += 1
    return summary
