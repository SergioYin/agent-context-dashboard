from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import ReportCard


class DashboardError(Exception):
    """Base exception for user-facing dashboard errors."""


class ReportDirectoryError(DashboardError):
    """Raised when the input report directory cannot be read."""


class ReportParseError(DashboardError):
    """Raised when a JSON report cannot be parsed."""


def load_reports(input_dir: Path | str) -> list[ReportCard]:
    directory = Path(input_dir)
    if not directory.exists():
        raise ReportDirectoryError(f"Report directory does not exist: {directory}")
    if not directory.is_dir():
        raise ReportDirectoryError(f"Report path is not a directory: {directory}")

    cards: list[ReportCard] = []
    for path in sorted(directory.glob("*.json")):
        try:
            with path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except json.JSONDecodeError as exc:
            raise ReportParseError(
                f"Malformed JSON in {path}: line {exc.lineno}, column {exc.colno}: {exc.msg}"
            ) from exc
        except OSError as exc:
            raise ReportParseError(f"Could not read {path}: {exc}") from exc

        cards.append(normalize_report(path, data))
    return cards


def normalize_report(path: Path | str, data: Any) -> ReportCard:
    source_path = Path(path)
    if isinstance(data, dict):
        if _looks_like_audit(data):
            return _normalize_audit(source_path, data)
        if _looks_like_lint(data):
            return _normalize_lint(source_path, data)
        if _looks_like_guard(data):
            return _normalize_guard(source_path, data)

    return _normalize_unknown(source_path, data)


def _looks_like_audit(data: dict[str, Any]) -> bool:
    tool = data.get("tool")
    tool_name = tool.get("name") if isinstance(tool, dict) else data.get("tool_name")
    return tool_name == "agent-context-audit" or "overall_score" in data or {"repository", "summary", "findings"}.issubset(data)


def _looks_like_lint(data: dict[str, Any]) -> bool:
    summary = data.get("summary")
    return {"file", "violations", "score"}.issubset(data) or (
        isinstance(summary, dict)
        and "average_score" in summary
        and ("scanned_files" in data or "files" in data or "issues" in data)
    )


def _looks_like_guard(data: dict[str, Any]) -> bool:
    keys = set(data)
    has_decision = bool(keys & {"allow", "allowed", "deny", "denied", "blocked"})
    summary = data.get("summary")
    return (
        has_decision and bool(keys & {"repository", "target", "file", "path", "subject"})
    ) or (
        isinstance(summary, dict)
        and ("findings" in data or "issues" in data)
        and ("suppressed" in data or {"high", "medium", "low"} & set(summary))
    )


def _normalize_audit(path: Path, data: dict[str, Any]) -> ReportCard:
    findings = _as_list(data.get("findings"))
    summary = data.get("summary")
    score = data.get("overall_score", data.get("score"))
    grade = data.get("grade")
    summary_text = _summary_to_text(summary, fallback=f"score: {score}; {len(findings)} finding(s)" if score is not None else f"{len(findings)} finding(s)")
    risk_count = _count_risky_items(findings)
    status = str(data.get("status") or grade or _status_from_counts(risk_count, len(findings)))
    repository = str(data.get("repository") or data.get("scanned_root") or data.get("root") or path.stem)
    warnings = _extract_warnings(findings)

    return ReportCard(
        source_path=path,
        tool="agent-context-audit",
        title=repository,
        status=status,
        summary=summary_text,
        risk_count=risk_count,
        warning_count=len(warnings),
        warnings=warnings,
        next_actions=_actions_from_findings(findings, "Review audit findings."),
        details={
            "generated_at": data.get("generated_at"),
            "findings": len(findings),
            "repository": repository,
            "score": score,
            "grade": grade,
        },
    )


def _normalize_lint(path: Path, data: dict[str, Any]) -> ReportCard:
    violations = _as_list(data.get("violations", data.get("issues")))
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    score = data.get("score", summary.get("average_score"))
    scanned_files = _as_list(data.get("scanned_files"))
    file_name = str(data.get("file") or (", ".join(str(item) for item in scanned_files[:3]) if scanned_files else path.name))
    risk_count = len(violations)
    status = "pass" if risk_count == 0 else "warn"
    score_text = f"score {score}" if score is not None else "no score"
    warnings = _extract_warnings(violations)

    return ReportCard(
        source_path=path,
        tool="agent-context-lint",
        title=file_name,
        status=status,
        summary=f"{score_text}; {risk_count} violation(s)",
        risk_count=risk_count,
        warning_count=len(warnings),
        warnings=warnings,
        next_actions=_actions_from_findings(violations, "Fix lint violations."),
        details={
            "score": score,
            "violations": risk_count,
            "file": file_name,
            "errors": summary.get("error"),
            "warnings": summary.get("warn"),
            "info": summary.get("info"),
        },
    )


def _normalize_guard(path: Path, data: dict[str, Any]) -> ReportCard:
    allow_value = data.get("allow", data.get("allowed"))
    deny_value = data.get("deny", data.get("denied", data.get("blocked")))
    findings = _as_list(data.get("findings", data.get("issues", data.get("matches"))))
    target = str(data.get("repository") or data.get("target") or data.get("file") or data.get("path") or path.stem)

    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    denied = _truthy(deny_value) or allow_value is False or int(summary.get("high", 0) or 0) > 0
    status = "blocked" if denied else "pass"
    risk_count = max(1, len(findings)) if denied else len(findings)
    warnings = _extract_warnings(findings)
    decision = "denied" if denied else "allowed"

    return ReportCard(
        source_path=path,
        tool="agent-instruction-guard",
        title=target,
        status=status,
        summary=f"guard decision: {decision}; {len(findings)} finding(s); suppressed: {data.get('suppressed', 0)}",
        risk_count=risk_count,
        warning_count=len(warnings),
        warnings=warnings,
        next_actions=_actions_from_findings(findings, "Review blocked or sensitive instructions."),
        details={"decision": decision, "findings": len(findings), "target": target, "suppressed": data.get("suppressed", 0)},
    )


def _normalize_unknown(path: Path, data: Any) -> ReportCard:
    if isinstance(data, dict):
        shape = f"{len(data)} top-level key(s)"
    elif isinstance(data, list):
        shape = f"{len(data)} list item(s)"
    else:
        shape = type(data).__name__

    return ReportCard(
        source_path=path,
        tool="unknown",
        title=path.name,
        status="unknown",
        summary=f"Unrecognized JSON schema; {shape}.",
        warning_count=1,
        warnings=["Unrecognized JSON schema. Add a normalizer or inspect this report manually."],
        next_actions=["Inspect this report and map it to a supported schema if it is recurring."],
        details={"file": path.name, "schema": "unknown", "shape": shape},
    )


def _summary_to_text(summary: Any, fallback: str) -> str:
    if isinstance(summary, str) and summary.strip():
        return summary.strip()
    if isinstance(summary, dict):
        parts = [f"{key}: {value}" for key, value in sorted(summary.items()) if _is_scalar(value)]
        if parts:
            return "; ".join(parts)
    return fallback


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _count_risky_items(items: list[Any]) -> int:
    if not items:
        return 0
    risky = 0
    for item in items:
        if not isinstance(item, dict):
            risky += 1
            continue
        severity = str(item.get("severity") or item.get("level") or item.get("status") or "").lower()
        if severity in {"", "info", "ok", "pass", "passed"}:
            continue
        risky += 1
    return risky


def _extract_warnings(items: list[Any]) -> list[str]:
    warnings: list[str] = []
    for item in items:
        if isinstance(item, dict):
            text = item.get("message") or item.get("title") or item.get("rule") or item.get("id")
            severity = str(item.get("severity") or item.get("level") or "warning").lower()
            if text and severity not in {"info", "ok", "pass", "passed"}:
                warnings.append(str(text))
        elif item:
            warnings.append(str(item))
    return warnings


def _actions_from_findings(items: list[Any], fallback: str) -> list[str]:
    actions: list[str] = []
    for item in items[:5]:
        if isinstance(item, dict):
            action = item.get("next_action") or item.get("recommendation") or item.get("fix") or item.get("message")
            if action:
                actions.append(str(action))
        elif item:
            actions.append(str(item))
    return actions or [fallback]


def _status_from_counts(risk_count: int, total: int) -> str:
    if risk_count == 0:
        return "pass"
    if risk_count == total:
        return "fail"
    return "warn"


def _truthy(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "deny", "denied", "blocked", "fail", "failed"}
    return bool(value)


def _is_scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))
