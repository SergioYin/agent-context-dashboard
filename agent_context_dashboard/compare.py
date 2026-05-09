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


@dataclass(frozen=True)
class CompareTrend:
    source: str
    baseline_score: float
    current_score: float
    score_delta: float
    changed_file_count: int
    added_file_count: int
    removed_file_count: int
    files_improved_count: int
    files_regressed_count: int
    rule_issue_delta: int


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


def load_compare_trends(paths: list[Path] | tuple[Path, ...] | None) -> list[CompareTrend]:
    trends: list[CompareTrend] = []
    for path in paths or []:
        trends.extend(load_compare_trend(path))
    return trends


def load_compare_trend(path: Path | str) -> list[CompareTrend]:
    compare_path = Path(path)
    try:
        with compare_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except FileNotFoundError as exc:
        raise BaselineError(f"Compare JSON does not exist: {compare_path}") from exc
    except json.JSONDecodeError as exc:
        raise BaselineError(
            f"Malformed compare JSON in {compare_path}: line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc
    except OSError as exc:
        raise BaselineError(f"Could not read compare JSON {compare_path}: {exc}") from exc

    entries = _compare_entries(payload, compare_path)
    return [_normalize_compare_entry(entry, compare_path) for entry in entries]


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


def compare_trends_payload(trends: list[CompareTrend]) -> list[dict[str, Any]]:
    return [
        {
            "source": trend.source,
            "baseline_score": _clean_number(trend.baseline_score),
            "current_score": _clean_number(trend.current_score),
            "score_delta": _clean_number(trend.score_delta),
            "changed_file_count": trend.changed_file_count,
            "added_file_count": trend.added_file_count,
            "removed_file_count": trend.removed_file_count,
            "files_improved_count": trend.files_improved_count,
            "files_regressed_count": trend.files_regressed_count,
            "rule_issue_delta": trend.rule_issue_delta,
        }
        for trend in trends
    ]


def compare_trends_summary(trends: list[CompareTrend]) -> dict[str, Any]:
    return {
        "total_entries": len(trends),
        "improved_entries": sum(1 for trend in trends if trend.score_delta > 0),
        "regressed_entries": sum(1 for trend in trends if trend.score_delta < 0),
        "unchanged_entries": sum(1 for trend in trends if trend.score_delta == 0),
        "total_score_delta": _clean_number(sum(trend.score_delta for trend in trends)),
        "changed_file_count": sum(trend.changed_file_count for trend in trends),
        "added_file_count": sum(trend.added_file_count for trend in trends),
        "removed_file_count": sum(trend.removed_file_count for trend in trends),
        "files_improved_count": sum(trend.files_improved_count for trend in trends),
        "files_regressed_count": sum(trend.files_regressed_count for trend in trends),
        "rule_issue_delta": sum(trend.rule_issue_delta for trend in trends),
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


def _compare_entries(payload: Any, path: Path) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        entries = payload
    elif isinstance(payload, dict):
        for key in ("comparisons", "compare_entries", "entries", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                entries = value
                break
        else:
            entries = [payload]
    else:
        raise BaselineError(f"Compare JSON is not an object or list: {path}")

    objects: list[dict[str, Any]] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise BaselineError(f"Compare entry #{index + 1} is not an object: {path}")
        objects.append(entry)
    return objects


def _normalize_compare_entry(entry: dict[str, Any], path: Path) -> CompareTrend:
    baseline_score = _required_number(entry, ("baseline_score", "previous_score", "before_score"), path)
    if baseline_score is None:
        baseline_score = _required_number(_as_dict(entry.get("baseline")), ("score", "overall_score"), path)
    current_score = _required_number(entry, ("current_score", "after_score"), path)
    if current_score is None:
        current_score = _required_number(_as_dict(entry.get("current")), ("score", "overall_score"), path)
    if baseline_score is None or current_score is None:
        raise BaselineError(f"Compare entry is missing baseline/current scores: {path}")

    score_delta = _optional_number(entry, ("score_delta", "delta", "score_change"))
    if score_delta is None:
        score_delta = current_score - baseline_score

    files = _as_dict(entry.get("files"))
    file_changes = _as_dict(entry.get("file_changes"))
    rules = _as_dict(entry.get("rules"))
    issues = _as_dict(entry.get("issues"))
    rule_issue_count_deltas = _as_dict(entry.get("rule_issue_count_deltas"))

    return CompareTrend(
        source=path.as_posix(),
        baseline_score=baseline_score,
        current_score=current_score,
        score_delta=score_delta,
        changed_file_count=_optional_int(entry, ("changed_file_count", "changed_files"))
        or _optional_int(files, ("changed", "changed_count"))
        or _optional_int(file_changes, ("changed", "changed_count"))
        or 0,
        added_file_count=_optional_int(entry, ("added_file_count", "added_files"))
        or _optional_int(files, ("added", "added_count"))
        or _optional_int(file_changes, ("added", "added_count"))
        or 0,
        removed_file_count=_optional_int(entry, ("removed_file_count", "removed_files"))
        or _optional_int(files, ("removed", "removed_count"))
        or _optional_int(file_changes, ("removed", "removed_count"))
        or 0,
        files_improved_count=_optional_int(entry, ("files_improved_count", "improved_files"))
        or _list_count(entry.get("files_improved"))
        or _optional_int(files, ("improved", "improved_count"))
        or 0,
        files_regressed_count=_optional_int(entry, ("files_regressed_count", "regressed_files"))
        or _list_count(entry.get("files_regressed"))
        or _optional_int(files, ("regressed", "regressed_count"))
        or 0,
        rule_issue_delta=_optional_int(entry, ("rule_issue_delta", "issue_delta"))
        or _optional_int(rule_issue_count_deltas, ("delta",))
        or _optional_int(rules, ("issue_delta", "delta"))
        or _optional_int(issues, ("rule_issue_delta", "delta"))
        or 0,
    )


def _card_key(card: ReportCard) -> tuple[str, str]:
    return (card.source_path.as_posix(), card.tool)


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


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _required_number(payload: dict[str, Any], keys: tuple[str, ...], path: Path) -> float | None:
    for key in keys:
        if key in payload:
            value = payload[key]
            number = _number_value(value)
            if number is None:
                raise BaselineError(f"Compare field {key} is not numeric in {path}")
            return number
    return None


def _optional_number(payload: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        if key in payload:
            return _number_value(payload[key])
    return None


def _optional_int(payload: dict[str, Any], keys: tuple[str, ...]) -> int | None:
    number = _optional_number(payload, keys)
    if number is None:
        return None
    return int(number)


def _list_count(value: Any) -> int | None:
    return len(value) if isinstance(value, list) else None


def _number_value(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _clean_number(value: int | float) -> int | float:
    return int(value) if isinstance(value, float) and value.is_integer() else value


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
