from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from agent_context_dashboard.cli import _has_strict_failures, main
from agent_context_dashboard.compare import ComparisonItem, ComparisonResult, compare_to_baseline, load_baseline
from agent_context_dashboard.render import render_html, render_json
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

    def test_normalizes_agent_instruction_guard_sarif(self) -> None:
        card = normalize_report(
            Path("guard.sarif.json"),
            {
                "version": "2.1.0",
                "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
                "runs": [
                    {
                        "tool": {"driver": {"name": "agent-instruction-guard"}},
                        "results": [
                            {"level": "error", "ruleId": "AIG001", "message": {"text": "Blocked unsafe instruction"}},
                            {"level": "warning", "ruleId": "AIG002", "message": {"text": "Review ambiguous instruction"}},
                            {"level": "note", "ruleId": "AIG003", "message": {"text": "Informational note"}},
                            {"level": "none", "ruleId": "AIG004", "message": {"text": "Passed check"}},
                            {"ruleId": "AIG005"},
                        ],
                    }
                ],
            },
        )

        self.assertEqual(card.tool, "agent-instruction-guard")
        self.assertEqual(card.title, "agent-instruction-guard")
        self.assertEqual(card.status, "error")
        self.assertEqual(card.risk_count, 3)
        self.assertEqual(card.warning_count, 3)
        self.assertIn("Blocked unsafe instruction", card.warnings)
        self.assertIn("Review ambiguous instruction", card.warnings)
        self.assertIn("AIG005", card.warnings)
        self.assertNotIn("Informational note", card.warnings)
        self.assertEqual(card.details["sarif_version"], "2.1.0")
        self.assertEqual(card.details["runs"], 1)
        self.assertEqual(card.details["results"], 5)
        self.assertEqual(card.details["errors"], 1)
        self.assertEqual(card.details["warnings"], 1)
        self.assertEqual(card.details["notes"], 1)
        self.assertTrue(card.next_actions[0].startswith("Review SARIF finding:"))

    def test_empty_sarif_passes(self) -> None:
        card = normalize_report(
            Path("scan.json"),
            {
                "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
                "runs": [{"tool": {"driver": {"name": "Static Scan"}}, "results": []}],
            },
        )

        self.assertEqual(card.tool, "sarif")
        self.assertEqual(card.title, "Static Scan")
        self.assertEqual(card.status, "pass")
        self.assertEqual(card.summary, "0 result(s); errors: 0; warnings: 0; notes: 0")
        self.assertEqual(card.risk_count, 0)
        self.assertEqual(card.warning_count, 0)
        self.assertEqual(card.warnings, [])


class LoadingAndCliTests(unittest.TestCase):
    def test_html_renderer_escapes_report_content(self) -> None:
        card = normalize_report(
            Path("unsafe.json"),
            {
                "tool": {"name": "agent-context-audit"},
                "repository": "<script>alert('x')</script>",
                "summary": "A & B < C",
                "findings": [{"severity": "warning", "message": "<b>Check owner</b> & docs"}],
            },
        )

        html = render_html([card])

        self.assertIn("&lt;script&gt;alert(&#x27;x&#x27;)&lt;/script&gt;", html)
        self.assertIn("A &amp; B &lt; C", html)
        self.assertIn("&lt;b&gt;Check owner&lt;/b&gt; &amp; docs", html)
        self.assertNotIn("<script>alert", html)
        self.assertNotIn("<b>Check owner</b>", html)

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

    def test_load_reports_defaults_to_top_level_json_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "lint.json").write_text(
                json.dumps({"scanned_files": ["AGENTS.md"], "summary": {"average_score": 100}, "issues": []}),
                encoding="utf-8",
            )
            nested = root / "repo-a"
            nested.mkdir()
            (nested / "lint.json").write_text(
                json.dumps({"scanned_files": ["README.md"], "summary": {"average_score": 100}, "issues": []}),
                encoding="utf-8",
            )

            cards = load_reports(root)

        self.assertEqual([card.source_path.as_posix() for card in cards], ["lint.json"])

    def test_recursive_reports_keep_distinct_relative_sources_for_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for repo_name, scanned_file in (("repo-a", "AGENTS.md"), ("repo-b", "README.md")):
                repo = root / repo_name
                repo.mkdir()
                (repo / "lint.json").write_text(
                    json.dumps(
                        {
                            "scanned_files": [scanned_file],
                            "summary": {"average_score": 100},
                            "issues": [],
                        }
                    ),
                    encoding="utf-8",
                )
            cache = root / "node_modules"
            cache.mkdir()
            (cache / "ignored.json").write_text(json.dumps({"tool": "new-tool"}), encoding="utf-8")

            cards = load_reports(root, recursive=True)
            baseline_path = root / "baseline.json"
            baseline_path.write_text(render_json(cards), encoding="utf-8")
            comparison = compare_to_baseline(cards, load_baseline(baseline_path))

        self.assertEqual([card.source_path.as_posix() for card in cards], ["repo-a/lint.json", "repo-b/lint.json"])
        self.assertEqual(comparison.summary["total_items"], 0)
        self.assertFalse(comparison.has_regressions)

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

    def test_cli_writes_html_output_file_alongside_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reports = root / "reports"
            reports.mkdir()
            (reports / "lint.json").write_text(
                json.dumps({"scanned_files": ["AGENTS.md"], "summary": {"average_score": 100}, "issues": []}),
                encoding="utf-8",
            )
            markdown_output = root / "dashboard.md"
            html_output = root / "dashboard.html"

            exit_code = main([str(reports), "--output", str(markdown_output), "--html-output", str(html_output)])

            self.assertEqual(exit_code, 0)
            self.assertIn("Reports scanned: 1", markdown_output.read_text(encoding="utf-8"))
            html = html_output.read_text(encoding="utf-8")
            self.assertIn("<!doctype html>", html)
            self.assertIn("Agent Context Asset Health Dashboard", html)
            self.assertIn("agent-context-lint", html)

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

    def test_cli_json_includes_sarif_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            reports = Path(tmp)
            (reports / "scan.json").write_text(
                json.dumps(
                    {
                        "version": "2.1.0",
                        "runs": [
                            {
                                "tool": {"driver": {"name": "Example SARIF Tool"}},
                                "results": [{"level": "warning", "ruleId": "EX001"}],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            stdout = StringIO()

            with redirect_stdout(stdout):
                exit_code = main([str(reports), "--format", "json"])

            self.assertEqual(exit_code, 0)
            payload = json.loads(stdout.getvalue())
            report = payload["reports"][0]
            self.assertEqual(payload["summary"]["reports_scanned"], 1)
            self.assertEqual(payload["summary"]["reports_with_risk"], 1)
            self.assertEqual(report["tool"], "sarif")
            self.assertEqual(report["title"], "Example SARIF Tool")
            self.assertEqual(report["details"]["sarif_version"], "2.1.0")
            self.assertEqual(report["details"]["results"], 1)
            self.assertEqual(report["warnings"], ["EX001"])

    def test_html_includes_baseline_and_sarif_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            reports = Path(tmp) / "reports"
            reports.mkdir()
            (reports / "scan.json").write_text(
                json.dumps(
                    {
                        "version": "2.1.0",
                        "runs": [
                            {
                                "tool": {"driver": {"name": "Example SARIF Tool"}},
                                "results": [{"level": "warning", "ruleId": "EX001"}],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            baseline = Path(tmp) / "baseline.json"
            baseline.write_text(
                json.dumps(
                    {
                        "generated_at": "2026-05-09T00:00:00+00:00",
                        "summary": {"reports_scanned": 1},
                        "reports": [
                            {
                                "source": "scan.json",
                                "tool": "sarif",
                                "status": "pass",
                                "risk_count": 0,
                                "warning_count": 0,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            output = Path(tmp) / "dashboard.html"
            markdown_output = Path(tmp) / "dashboard.md"

            exit_code = main(
                [
                    str(reports),
                    "--baseline",
                    str(baseline),
                    "--output",
                    str(markdown_output),
                    "--html-output",
                    str(output),
                ]
            )

            self.assertEqual(exit_code, 0)
            html = output.read_text(encoding="utf-8")
            self.assertIn("Baseline Comparison", html)
            self.assertIn("SARIF Reports", html)
            self.assertIn("warnings increased from 0 to 1", html)
            self.assertIn("results: 1", html)

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

    def test_cli_returns_error_for_malformed_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            reports = Path(tmp) / "reports"
            reports.mkdir()
            (reports / "lint.json").write_text(
                json.dumps({"scanned_files": ["AGENTS.md"], "summary": {"average_score": 100}, "issues": []}),
                encoding="utf-8",
            )
            baseline = Path(tmp) / "baseline.json"
            baseline.write_text("{broken", encoding="utf-8")

            self.assertEqual(main([str(reports), "--baseline", str(baseline)]), 2)

    def test_cli_json_includes_baseline_comparison(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            reports = Path(tmp) / "reports"
            reports.mkdir()
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
            baseline = Path(tmp) / "baseline.json"
            baseline.write_text(
                json.dumps(
                    {
                        "generated_at": "2026-05-09T00:00:00+00:00",
                        "summary": {"reports_scanned": 1},
                        "reports": [
                            {
                                "source": "lint.json",
                                "tool": "agent-context-lint",
                                "status": "pass",
                                "risk_count": 0,
                                "warning_count": 0,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            output = Path(tmp) / "dashboard.json"

            exit_code = main([str(reports), "--baseline", str(baseline), "--format", "json", "--output", str(output)])

            self.assertEqual(exit_code, 0)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["comparison"]["summary"]["new_risk"], 1)
            self.assertEqual(payload["comparison"]["summary"]["increased_warnings"], 1)

    def test_strict_fails_for_baseline_regression_when_report_passes(self) -> None:
        cards = [
            normalize_report(
                Path("lint.json"),
                {"scanned_files": ["AGENTS.md"], "summary": {"average_score": 100}, "issues": []},
            )
        ]
        comparison = ComparisonResult(
            summary={"total_items": 1, "regressions": 1},
            items=[
                ComparisonItem(
                    kind="new_unknown_schema",
                    source="other.json",
                    tool="unknown",
                    message="regression",
                    current_warning_count=1,
                )
            ],
        )

        self.assertTrue(_has_strict_failures(cards, comparison))

    def test_strict_ignores_resolved_risk_when_current_report_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            reports = Path(tmp) / "reports"
            reports.mkdir()
            (reports / "lint.json").write_text(
                json.dumps({"scanned_files": ["AGENTS.md"], "summary": {"average_score": 100}, "issues": []}),
                encoding="utf-8",
            )
            baseline = Path(tmp) / "baseline.json"
            baseline.write_text(
                json.dumps(
                    {
                        "generated_at": "2026-05-09T00:00:00+00:00",
                        "summary": {"reports_scanned": 1},
                        "reports": [
                            {
                                "source": "lint.json",
                                "tool": "agent-context-lint",
                                "status": "fail",
                                "risk_count": 1,
                                "warning_count": 1,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            output = Path(tmp) / "dashboard.md"

            self.assertEqual(main([str(reports), "--baseline", str(baseline), "--strict", "--output", str(output)]), 0)


if __name__ == "__main__":
    unittest.main()
