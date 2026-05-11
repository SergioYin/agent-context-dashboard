#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = Path("/tmp/agent-context-dashboard-selfcheck.md")
HUB_OUTPUT = Path("/tmp/agent-context-dashboard-selfcheck-hub.html")
BADGES_OUTPUT = Path("/tmp/agent-context-dashboard-selfcheck-badges.md")
MULTI_OUTPUT = Path("/tmp/agent-context-dashboard-selfcheck-multi.md")


def main() -> int:
    cmd = [
        sys.executable,
        "-m",
        "agent_context_dashboard",
        "build",
        str(ROOT / "examples" / "reports"),
        "--compare",
        str(ROOT / "examples" / "compare.json"),
        "--hub",
        str(HUB_OUTPUT),
        "--badge-snippets",
        str(BADGES_OUTPUT),
        "--output",
        str(OUTPUT),
    ]
    result = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        return result.returncode

    dashboard = OUTPUT.read_text(encoding="utf-8")
    expected = [
        "Agent Context Asset Health Dashboard",
        "agent-context-audit",
        "agent-context-lint",
        "agent-instruction-guard",
        "Unknown schemas: 1",
        "Score Trends",
        "82 -> 90 (+8)",
        "Next Actions",
    ]
    missing = [text for text in expected if text not in dashboard]
    if missing:
        sys.stderr.write(f"Dashboard missing expected text: {missing}\n")
        return 1

    hub = HUB_OUTPUT.read_text(encoding="utf-8")
    hub_expected = [
        "Agent Context Asset Hub",
        'id="badge-snippets"',
        "Agent Context Health",
        "Agent Context Trend",
    ]
    hub_missing = [text for text in hub_expected if text not in hub]
    if hub_missing:
        sys.stderr.write(f"Hub missing expected text: {hub_missing}\n")
        return 1

    badges = BADGES_OUTPUT.read_text(encoding="utf-8")
    badge_expected = [
        "Agent Context Badge Snippets",
        "[**Agent Context Health:** risk]",
        "<span style=",
    ]
    badge_missing = [text for text in badge_expected if text not in badges]
    if badge_missing:
        sys.stderr.write(f"Badge snippets missing expected text: {badge_missing}\n")
        return 1

    multi_cmd = [
        sys.executable,
        "-m",
        "agent_context_dashboard",
        "build",
        str(ROOT / "examples" / "multi-repo-reports"),
        "--recursive",
        "--compare",
        str(ROOT / "examples" / "multi-repo-compare.json"),
        "--output",
        str(MULTI_OUTPUT),
    ]
    multi_result = subprocess.run(multi_cmd, cwd=ROOT, text=True, capture_output=True)
    if multi_result.returncode != 0:
        sys.stderr.write(multi_result.stderr)
        return multi_result.returncode

    multi_dashboard = MULTI_OUTPUT.read_text(encoding="utf-8")
    multi_expected = [
        "Reports scanned: 5",
        "`repo-alpha/audit.json`",
        "`repo-beta/guard.json`",
        "`repo-gamma/lint.json`",
        "87 -> 91 (+4)",
    ]
    multi_missing = [text for text in multi_expected if text not in multi_dashboard]
    if multi_missing:
        sys.stderr.write(f"Multi-repo dashboard missing expected text: {multi_missing}\n")
        return 1

    print(f"selfcheck ok: {OUTPUT}; {HUB_OUTPUT}; {BADGES_OUTPUT}; {MULTI_OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
