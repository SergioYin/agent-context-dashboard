from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .reports import DashboardError


READY_RANKS = {"blocked": 0, "review": 1, "ready": 2}


class TrendError(DashboardError):
    """Raised when dashboard trend inputs cannot be read or compared."""


@dataclass(frozen=True)
class ScoreDelta:
    source: str
    tool: str
    baseline_score: float
    current_score: float
    score_delta: float


@dataclass(frozen=True)
class WarningDelta:
    source: str
    tool: str
    message: str


@dataclass(frozen=True)
class ReadinessMovement:
    baseline_state: str
    current_state: str
    movement: str
    baseline_rank: int
    current_rank: int


@dataclass(frozen=True)
class TrendResult:
    baseline_path: str
    current_path: str
    score_deltas: list[ScoreDelta]
    new_warnings: list[WarningDelta]
    resolved_warnings: list[WarningDelta]
    readiness: ReadinessMovement


def load_trend(baseline: Path | str, current: Path | str) -> TrendResult:
    baseline_path = Path(baseline)
    current_path = Path(current)
    baseline_payload = _load_dashboard(baseline_path)
    current_payload = _load_dashboard(current_path)
    return compare_dashboards(
        baseline_payload,
        current_payload,
        baseline_path=baseline_path.as_posix(),
        current_path=current_path.as_posix(),
    )


def compare_dashboards(
    baseline_payload: dict[str, Any],
    current_payload: dict[str, Any],
    baseline_path: str = "<baseline>",
    current_path: str = "<current>",
) -> TrendResult:
    baseline_reports = _reports_by_key(baseline_payload, Path(baseline_path))
    current_reports = _reports_by_key(current_payload, Path(current_path))

    score_deltas: list[ScoreDelta] = []
    for key in sorted(set(baseline_reports) & set(current_reports)):
        baseline_score = _report_score(baseline_reports[key])
        current_score = _report_score(current_reports[key])
        if baseline_score is None or current_score is None:
            continue
        score_delta = current_score - baseline_score
        if score_delta == 0:
            continue
        source, tool = key
        score_deltas.append(
            ScoreDelta(
                source=source,
                tool=tool,
                baseline_score=baseline_score,
                current_score=current_score,
                score_delta=score_delta,
            )
        )

    baseline_warnings = _warning_keys(baseline_reports)
    current_warnings = _warning_keys(current_reports)
    new_warnings = [_warning_delta(key) for key in sorted(current_warnings - baseline_warnings)]
    resolved_warnings = [_warning_delta(key) for key in sorted(baseline_warnings - current_warnings)]

    baseline_readiness = _readiness_state(baseline_payload)
    current_readiness = _readiness_state(current_payload)
    baseline_rank = READY_RANKS[baseline_readiness]
    current_rank = READY_RANKS[current_readiness]
    if current_rank > baseline_rank:
        movement = "improved"
    elif current_rank < baseline_rank:
        movement = "regressed"
    else:
        movement = "stable"

    return TrendResult(
        baseline_path=baseline_path,
        current_path=current_path,
        score_deltas=score_deltas,
        new_warnings=new_warnings,
        resolved_warnings=resolved_warnings,
        readiness=ReadinessMovement(
            baseline_state=baseline_readiness,
            current_state=current_readiness,
            movement=movement,
            baseline_rank=baseline_rank,
            current_rank=current_rank,
        ),
    )


def render_trend_json(trend: TrendResult) -> str:
    return json.dumps(trend_payload(trend), indent=2, sort_keys=True) + "\n"


def render_trend_markdown(trend: TrendResult) -> str:
    summary = trend_summary(trend)
    lines = [
        "# Agent Context Dashboard Trend",
        "",
        f"- Baseline dashboard: `{trend.baseline_path}`",
        f"- Current dashboard: `{trend.current_path}`",
        f"- Release readiness: {trend.readiness.baseline_state} -> {trend.readiness.current_state} ({trend.readiness.movement})",
        f"- Score changes: {summary['score_change_count']}",
        f"- Improved scores: {summary['improved_scores']}",
        f"- Regressed scores: {summary['regressed_scores']}",
        f"- Total score delta: {_signed_number(float(summary['total_score_delta']))}",
        f"- New warnings: {summary['new_warning_count']}",
        f"- Resolved warnings: {summary['resolved_warning_count']}",
        "",
        "## Score Changes",
        "",
    ]
    if trend.score_deltas:
        for item in trend.score_deltas:
            lines.append(
                "- "
                f"`{item.source}` ({item.tool}): "
                f"{_format_number(item.baseline_score)} -> {_format_number(item.current_score)} "
                f"({_signed_number(item.score_delta)})"
            )
    else:
        lines.append("- No comparable report scores changed or appeared in both dashboards.")

    lines.extend(["", "## New Warnings", ""])
    if trend.new_warnings:
        lines.extend(f"- `{item.source}` ({item.tool}): {item.message}" for item in trend.new_warnings)
    else:
        lines.append("- No new warnings.")

    lines.extend(["", "## Resolved Warnings", ""])
    if trend.resolved_warnings:
        lines.extend(f"- `{item.source}` ({item.tool}): {item.message}" for item in trend.resolved_warnings)
    else:
        lines.append("- No resolved warnings.")

    lines.extend(["", "## Release Readiness", ""])
    lines.append(
        "- "
        f"{trend.readiness.baseline_state} -> {trend.readiness.current_state} "
        f"({trend.readiness.movement}; rank {trend.readiness.baseline_rank} -> {trend.readiness.current_rank})"
    )
    lines.append("")
    return "\n".join(lines)


def trend_payload(trend: TrendResult) -> dict[str, Any]:
    return {
        "baseline_path": trend.baseline_path,
        "current_path": trend.current_path,
        "summary": trend_summary(trend),
        "readiness": {
            "baseline_state": trend.readiness.baseline_state,
            "current_state": trend.readiness.current_state,
            "movement": trend.readiness.movement,
            "baseline_rank": trend.readiness.baseline_rank,
            "current_rank": trend.readiness.current_rank,
        },
        "score_deltas": [
            {
                "source": item.source,
                "tool": item.tool,
                "baseline_score": _clean_number(item.baseline_score),
                "current_score": _clean_number(item.current_score),
                "score_delta": _clean_number(item.score_delta),
            }
            for item in trend.score_deltas
        ],
        "new_warnings": [_warning_payload(item) for item in trend.new_warnings],
        "resolved_warnings": [_warning_payload(item) for item in trend.resolved_warnings],
    }


def trend_summary(trend: TrendResult) -> dict[str, int | float | str]:
    total_score_delta = sum(item.score_delta for item in trend.score_deltas)
    return {
        "score_change_count": len(trend.score_deltas),
        "improved_scores": sum(1 for item in trend.score_deltas if item.score_delta > 0),
        "regressed_scores": sum(1 for item in trend.score_deltas if item.score_delta < 0),
        "unchanged_scores": sum(1 for item in trend.score_deltas if item.score_delta == 0),
        "total_score_delta": _clean_number(total_score_delta),
        "new_warning_count": len(trend.new_warnings),
        "resolved_warning_count": len(trend.resolved_warnings),
        "release_readiness_movement": trend.readiness.movement,
    }


def _load_dashboard(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except FileNotFoundError as exc:
        raise TrendError(f"Dashboard JSON does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise TrendError(f"Malformed dashboard JSON in {path}: line {exc.lineno}, column {exc.colno}: {exc.msg}") from exc
    except OSError as exc:
        raise TrendError(f"Could not read dashboard JSON {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise TrendError(f"Dashboard JSON is not an object: {path}")
    return payload


def _reports_by_key(payload: dict[str, Any], path: Path) -> dict[tuple[str, str], dict[str, Any]]:
    if not isinstance(payload.get("generated_at"), str) or not isinstance(payload.get("reports"), list):
        raise TrendError(f"Input is not a dashboard produced by --format json: {path}")
    reports: dict[tuple[str, str], dict[str, Any]] = {}
    for index, report in enumerate(payload["reports"]):
        if not isinstance(report, dict):
            raise TrendError(f"Dashboard report #{index + 1} is not an object: {path}")
        source = report.get("source")
        tool = report.get("tool")
        if not isinstance(source, str) or not source or not isinstance(tool, str) or not tool:
            raise TrendError(f"Dashboard report #{index + 1} is missing source or tool: {path}")
        reports[(source, tool)] = report
    return reports


def _report_score(report: dict[str, Any]) -> float | None:
    details = report.get("details")
    if isinstance(details, dict):
        score = _number_value(details.get("score"))
        if score is not None:
            return score
    for key in ("score", "overall_score"):
        score = _number_value(report.get(key))
        if score is not None:
            return score
    return None


def _warning_keys(reports: dict[tuple[str, str], dict[str, Any]]) -> set[tuple[str, str, str]]:
    warnings: set[tuple[str, str, str]] = set()
    for (source, tool), report in reports.items():
        for warning in report.get("warnings", []):
            if isinstance(warning, str) and warning:
                warnings.add((source, tool, warning))
        if _number_int(report.get("warning_count")) > 0 and not isinstance(report.get("warnings"), list):
            warnings.add((source, tool, f"{_number_int(report.get('warning_count'))} warning(s)"))
    return warnings


def _warning_delta(key: tuple[str, str, str]) -> WarningDelta:
    source, tool, message = key
    return WarningDelta(source=source, tool=tool, message=message)


def _readiness_state(payload: dict[str, Any]) -> str:
    reports = payload.get("reports") if isinstance(payload.get("reports"), list) else []
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    reports_with_risk = _number_int(summary.get("reports_with_risk"))
    warnings = _number_int(summary.get("warnings"))
    unknown_schemas = _number_int(summary.get("unknown_schemas"))

    for report in reports:
        if not isinstance(report, dict):
            continue
        status = str(report.get("status") or "").lower()
        risk_count = _number_int(report.get("risk_count"))
        if risk_count > 0 or status in {"blocked", "error", "fail", "failed"}:
            reports_with_risk += 1
        if str(report.get("tool") or "").lower() == "unknown":
            unknown_schemas += 1
        warnings += _number_int(report.get("warning_count"))

    if reports_with_risk > 0:
        return "blocked"
    if warnings > 0 or unknown_schemas > 0:
        return "review"
    return "ready"


def _warning_payload(item: WarningDelta) -> dict[str, str]:
    return {"source": item.source, "tool": item.tool, "message": item.message}


def _number_value(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _number_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    return 0


def _clean_number(value: float) -> int | float:
    return int(value) if value.is_integer() else value


def _format_number(value: float) -> str:
    return str(int(value)) if value.is_integer() else f"{value:.2f}".rstrip("0").rstrip(".")


def _signed_number(value: float) -> str:
    formatted = _format_number(abs(value))
    if value > 0:
        return f"+{formatted}"
    if value < 0:
        return f"-{formatted}"
    return formatted
