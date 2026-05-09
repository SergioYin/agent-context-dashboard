#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = Path("/tmp/agent-context-dashboard-selfcheck.md")


def main() -> int:
    cmd = [
        sys.executable,
        "-m",
        "agent_context_dashboard",
        "build",
        str(ROOT / "examples" / "reports"),
        "--compare",
        str(ROOT / "examples" / "compare.json"),
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

    print(f"selfcheck ok: {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
