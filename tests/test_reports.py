from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
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

    def test_cli_prints_json_to_stdout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            reports = Path(tmp)
            (reports / "lint.json").write_text(
                json.dumps({"scanned_files": ["AGENTS.md"], "summary": {"average_score": 100}, "issues": []}),
                encoding="utf-8",
            )
            stdout = StringIO()

            with redirect_stdout(stdout):
                exit_code = main([str(reports), "--format", "json"])

            self.assertEqual(exit_code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertIn("generated_at", payload)
            self.assertEqual(payload["summary"]["reports_scanned"], 1)
            self.assertEqual(payload["summary"]["passing_reports"], 1)
            self.assertEqual(payload["reports"][0]["tool"], "agent-context-lint")
            self.assertEqual(payload["risks_and_warnings"], [])

    def test_cli_writes_json_output_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reports = root / "reports"
            reports.mkdir()
            (reports / "unknown.json").write_text(json.dumps({"tool": "new-tool"}), encoding="utf-8")
            output = root / "dashboard.json"

            exit_code = main([str(reports), "--format", "json", "--output", str(output)])

            self.assertEqual(exit_code, 0)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["summary"]["unknown_schemas"], 1)
            self.assertEqual(payload["reports"][0]["status"], "unknown")
            self.assertEqual(payload["risks_and_warnings"][0]["kind"], "unknown_schema")

    def test_strict_returns_nonzero_for_warnings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            reports = Path(tmp)
            (reports / "lint.json").write_text(
                json.dumps(
                    {
                        "scanned_files": ["AGENTS.md"],
                        "summary": {"average_score": 85},
                        "issues": [{"severity": "warn", "message": "Owner missing"}],
                    }
                ),
                encoding="utf-8",
            )

            self.assertEqual(main([str(reports), "--strict", "--output", str(reports / "dashboard.md")]), 1)

    def test_non_strict_returns_zero_for_unknown_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            reports = Path(tmp)
            (reports / "unknown.json").write_text(json.dumps({"tool": "new-tool"}), encoding="utf-8")

            self.assertEqual(main([str(reports), "--output", str(reports / "dashboard.md")]), 0)

    def test_strict_returns_nonzero_for_unknown_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            reports = Path(tmp)
            (reports / "unknown.json").write_text(json.dumps({"tool": "new-tool"}), encoding="utf-8")

            self.assertEqual(main([str(reports), "--strict", "--output", str(reports / "dashboard.md")]), 1)


if __name__ == "__main__":
    unittest.main()
