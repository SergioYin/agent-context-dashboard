from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ReportCard:
    """Normalized report shape used by the Markdown renderer."""

    source_path: Path
    tool: str
    title: str
    status: str
    summary: str
    risk_count: int = 0
    warning_count: int = 0
    next_actions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def is_risky(self) -> bool:
        return self.risk_count > 0 or self.status.lower() in {"fail", "failed", "error", "blocked"}
