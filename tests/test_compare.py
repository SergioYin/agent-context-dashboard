from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from agent_context_dashboard.compare import BaselineError, compare_to_baseline, load_baseline, load_compare_trend
from agent_context_dashboard.reports import normalize_report
from agent_context_dashboard.render import render_html, render_json, render_markdown
from agent_context_dashboard.trend import compare_dashboards, render_trend_json, render_trend_markdown


class BaselineComparisonTests(unittest.TestCase):
    def test_load_baseline_rejects_non_dashboard_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "baseline.json"
            path.write_text(json.dumps({"reports": "not-a-list"}), encoding="utf-8")

            with self.assertRaises(BaselineError):
                load_baseline(path)

    def test_detects_regressions_and_resolved_risk(self) -> None:
        current = [
            normalize_report(Path("unknown.json"), {"new": "shape"}),
            normalize_report(
                Path("lint.json"),
                {
                    "scanned_files": ["AGENTS.md"],
                    "summary": {"average_score": 80},
                    "issues": [{"severity": "warn", "message": "Owner missing"}],
                },
            ),
            normalize_report(
                Path("audit.json"),
                {
                    "tool": {"name": "agent-context-audit"},
                    "overall_score": 100,
                    "findings": [],
                },
            ),
        ]
        baseline = {
            ("lint.json", "agent-context-lint"): {
                "source": "lint.json",
                "tool": "agent-context-lint",
                "status": "pass",
                "risk_count": 0,
                "warning_count": 0,
            },
            ("audit.json", "agent-context-audit"): {
                "source": "audit.json",
                "tool": "agent-context-audit",
                "status": "fail",
                "risk_count": 1,
                "warning_count": 1,
            },
        }

        comparison = compare_to_baseline(current, baseline)

        self.assertTrue(comparison.has_regressions)
        self.assertEqual(comparison.summary["new_unknown_schema"], 1)
        self.assertEqual(comparison.summary["new_risk"], 1)
        self.assertEqual(comparison.summary["increased_warnings"], 1)
        self.assertEqual(comparison.summary["resolved_risk"], 1)
        self.assertEqual(
            [item.kind for item in comparison.items],
            ["new_unknown_schema", "new_risk", "increased_warnings", "resolved_risk"],
        )

    def test_renderers_include_comparison_only_when_provided(self) -> None:
        cards = [
            normalize_report(
                Path("lint.json"),
                {"scanned_files": ["AGENTS.md"], "summary": {"average_score": 100}, "issues": []},
            )
        ]
        comparison = compare_to_baseline(cards, {})

        markdown = render_markdown(cards, comparison=comparison)
        payload = json.loads(render_json(cards, comparison=comparison))

        self.assertIn("## Baseline Comparison", markdown)
        self.assertIn("comparison", payload)
        self.assertNotIn("comparison", json.loads(render_json(cards)))

    def test_load_compare_trend_from_agent_context_audit_compare_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "compare.json"
            path.write_text(
                json.dumps(
                    {
                        "baseline": {"overall_score": 84},
                        "current": {"overall_score": 91},
                        "changed_file_count": 4,
                        "added_file_count": 1,
                        "removed_file_count": 0,
                        "files_improved": [
                            {"path": "README.md", "baseline_score": 60, "current_score": 80, "delta": 20},
                            {"path": "AGENTS.md", "baseline_score": 70, "current_score": 80, "delta": 10},
                            {"path": "CONTRIBUTING.md", "baseline_score": 75, "current_score": 85, "delta": 10},
                        ],
                        "files_regressed": [
                            {"path": "ARCHITECTURE.md", "baseline_score": 90, "current_score": 80, "delta": -10}
                        ],
                        "rule_issue_count_deltas": {"baseline_total": 4, "current_total": 2, "delta": -2},
                    }
                ),
                encoding="utf-8",
            )

            trends = load_compare_trend(path)

        self.assertEqual(len(trends), 1)
        trend = trends[0]
        self.assertEqual(trend.baseline_score, 84)
        self.assertEqual(trend.current_score, 91)
        self.assertEqual(trend.score_delta, 7)
        self.assertEqual(trend.changed_file_count, 4)
        self.assertEqual(trend.added_file_count, 1)
        self.assertEqual(trend.removed_file_count, 0)
        self.assertEqual(trend.files_improved_count, 3)
        self.assertEqual(trend.files_regressed_count, 1)
        self.assertEqual(trend.rule_issue_delta, -2)

    def test_compare_trend_renderers_include_score_deltas(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "compare.json"
            path.write_text(
                json.dumps(
                    {
                        "baseline_score": 90,
                        "current_score": 87,
                        "changed_file_count": 2,
                        "added_file_count": 0,
                        "removed_file_count": 1,
                        "files_improved_count": 1,
                        "files_regressed_count": 2,
                        "rule_issue_delta": 3,
                    }
                ),
                encoding="utf-8",
            )
            trends = load_compare_trend(path)

        markdown = render_markdown([], compare_trends=trends)
        payload = json.loads(render_json([], compare_trends=trends))
        html = render_html([], compare_trends=trends)

        self.assertIn("## Score Trends", markdown)
        self.assertIn("90 -> 87 (-3)", markdown)
        self.assertEqual(payload["compare_entries"][0]["baseline_score"], 90)
        self.assertEqual(payload["compare_entries"][0]["current_score"], 87)
        self.assertEqual(payload["compare_entries"][0]["score_delta"], -3)
        self.assertEqual(payload["compare_entries"][0]["changed_file_count"], 2)
        self.assertEqual(payload["compare_entries"][0]["files_improved_count"], 1)
        self.assertEqual(payload["compare_entries"][0]["files_regressed_count"], 2)
        self.assertEqual(payload["compare_entries"][0]["rule_issue_delta"], 3)
        self.assertEqual(payload["compare_entries"][0]["source"], path.as_posix())
        self.assertIn("Score Trends", html)
        self.assertIn('class="regression">-3</td>', html)

    def test_dashboard_trend_compares_scores_warnings_and_readiness(self) -> None:
        baseline = {
            "generated_at": "2026-05-10T00:00:00+00:00",
            "summary": {"reports_scanned": 2, "reports_with_risk": 1, "warnings": 2, "unknown_schemas": 0},
            "reports": [
                {
                    "source": "audit.json",
                    "tool": "agent-context-audit",
                    "status": "C",
                    "risk_count": 1,
                    "warning_count": 1,
                    "warnings": ["Missing owner"],
                    "details": {"score": 72},
                },
                {
                    "source": "lint.json",
                    "tool": "agent-context-lint",
                    "status": "warn",
                    "risk_count": 1,
                    "warning_count": 1,
                    "warnings": ["Line too long"],
                    "details": {"score": 88},
                },
            ],
        }
        current = {
            "generated_at": "2026-05-11T00:00:00+00:00",
            "summary": {"reports_scanned": 2, "reports_with_risk": 0, "warnings": 1, "unknown_schemas": 0},
            "reports": [
                {
                    "source": "audit.json",
                    "tool": "agent-context-audit",
                    "status": "pass",
                    "risk_count": 0,
                    "warning_count": 0,
                    "warnings": [],
                    "details": {"score": 91},
                },
                {
                    "source": "lint.json",
                    "tool": "agent-context-lint",
                    "status": "warn",
                    "risk_count": 0,
                    "warning_count": 1,
                    "warnings": ["New formatting warning"],
                    "details": {"score": 84},
                },
            ],
        }

        trend = compare_dashboards(baseline, current, baseline_path="before.json", current_path="after.json")
        markdown = render_trend_markdown(trend)
        payload = json.loads(render_trend_json(trend))

        self.assertIn("# Agent Context Dashboard Trend", markdown)
        self.assertIn("Release readiness: blocked -> review (improved)", markdown)
        self.assertIn("`audit.json` (agent-context-audit): 72 -> 91 (+19)", markdown)
        self.assertIn("`lint.json` (agent-context-lint): New formatting warning", markdown)
        self.assertIn("`audit.json` (agent-context-audit): Missing owner", markdown)
        self.assertEqual(payload["summary"]["score_change_count"], 2)
        self.assertEqual(payload["summary"]["improved_scores"], 1)
        self.assertEqual(payload["summary"]["regressed_scores"], 1)
        self.assertEqual(payload["summary"]["total_score_delta"], 15)
        self.assertEqual(payload["summary"]["new_warning_count"], 1)
        self.assertEqual(payload["summary"]["resolved_warning_count"], 2)
        self.assertEqual(payload["readiness"]["movement"], "improved")
        self.assertEqual(payload["score_deltas"][0]["source"], "audit.json")


if __name__ == "__main__":
    unittest.main()
