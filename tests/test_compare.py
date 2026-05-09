from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from agent_context_dashboard.compare import BaselineError, compare_to_baseline, load_baseline
from agent_context_dashboard.reports import normalize_report
from agent_context_dashboard.render import render_json, render_markdown


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


if __name__ == "__main__":
    unittest.main()
