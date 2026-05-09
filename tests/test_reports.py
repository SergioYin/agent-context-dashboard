from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from agent_context_dashboard.cli import main
from agent_context_dashboard.reports import ReportParseError, load_reports, normalize_report


class NormalizationTests(unittest.TestCase):
    def test_normalizes_agent_context_audit(self) -> None:
        card = normalize_report(
            Path("audit.json"),
            {
                "tool": {"name": "agent-context-audit", "version": "0.1.1"},
                "scanned_root": "/work/repo-one",
                "overall_score": 72,
                "grade": "C",
                "summary": {"score": 72, "warnings": 1},
                "findings": [{"severity": "warning", "message": "Missing owner"}],
            },
        )

        self.assertEqual(card.tool, "agent-context-audit")
        self.assertEqual(card.title, "/work/repo-one")
        self.assertEqual(card.status, "C")
        self.assertEqual(card.risk_count, 1)
        self.assertIn("Missing owner", card.warnings)
        self.assertEqual(card.details["score"], 72)

    def test_normalizes_agent_context_lint(self) -> None:
        card = normalize_report(
            Path("lint.json"),
            {
                "scanned_files": ["AGENTS.md"],
                "summary": {"average_score": 91, "error": 0, "warn": 1, "info": 0},
                "issues": [{"severity": "warn", "code": "owner", "message": "Owner missing"}],
            },
        )

        self.assertEqual(card.tool, "agent-context-lint")
        self.assertEqual(card.title, "AGENTS.md")
        self.assertEqual(card.status, "warn")
        self.assertIn("score 91", card.summary)

    def test_normalizes_agent_instruction_guard(self) -> None:
        card = normalize_report(
            Path("guard.json"),
            {
                "summary": {"high": 1, "medium": 0, "low": 0},
                "suppressed": 2,
                "findings": [{"severity": "high", "recommendation": "Remove unsafe instruction"}],
            },
        )

        self.assertEqual(card.tool, "agent-instruction-guard")
        self.assertEqual(card.status, "blocked")
        self.assertEqual(card.details["decision"], "denied")
        self.assertEqual(card.details["suppressed"], 2)
        self.assertEqual(card.risk_count, 1)


class LoadingAndCliTests(unittest.TestCase):
    def test_malformed_json_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            (path / "broken.json").write_text("{not-json", encoding="utf-8")

            with self.assertRaises(ReportParseError):
                load_reports(path)

    def test_empty_directory_loads_zero_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cards = load_reports(Path(tmp))

        self.assertEqual(cards, [])

    def test_cli_writes_output_file_for_empty_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reports = root / "reports"
            reports.mkdir()
            output = root / "dashboard.md"

            exit_code = main(["build", str(reports), "--output", str(output)])

            self.assertEqual(exit_code, 0)
            dashboard = output.read_text(encoding="utf-8")
            self.assertIn("Reports scanned: 0", dashboard)
            self.assertIn("Add JSON reports", dashboard)

    def test_cli_writes_output_file_with_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reports = root / "reports"
            reports.mkdir()
            (reports / "lint.json").write_text(
                json.dumps({"scanned_files": ["AGENTS.md"], "summary": {"average_score": 100}, "issues": []}),
                encoding="utf-8",
            )
            output = root / "dashboard.md"

            exit_code = main([str(reports), "--output", str(output)])

            self.assertEqual(exit_code, 0)
            dashboard = output.read_text(encoding="utf-8")
            self.assertIn("agent-context-lint", dashboard)
            self.assertIn("Reports scanned: 1", dashboard)


if __name__ == "__main__":
    unittest.main()
