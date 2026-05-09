# Changelog

## 0.4.0

- Added `--html-output PATH` for writing a static HTML dashboard summary alongside existing Markdown or JSON output.
- HTML summaries include generated timestamp, overall status, summary counts, per-report rows, top warnings/errors, baseline comparison, and SARIF report details when present.
- Escaped all report-derived HTML content before rendering.
- Added a small synthetic SARIF sample report under `examples/reports`.

## 0.3.0

- Added SARIF 2.1.0 ingestion for local code scanning reports.
- SARIF reports from `agent-instruction-guard` are normalized under the existing `agent-instruction-guard` tool name when the SARIF driver identifies that tool.
- SARIF summaries now include result, error, warning, and note counts, with risky findings surfaced as dashboard warnings and next actions.
- Empty SARIF reports normalize as passing reports.

## 0.2.1

- Added `--recursive` for discovering JSON reports under multi-repo report workspaces.
- Recursive mode stores stable source paths relative to the input directory, preventing repeated filenames from colliding in JSON output and baseline comparisons.
- Recursive discovery skips common cache, build, and vendor directories.

## 0.2.0

- Added `--baseline PATH` for comparing current normalized reports against a prior JSON dashboard.
- Added Markdown and JSON baseline comparison summaries with regression items for new unknown schemas, new risks, and increased warnings.
- Added resolved-risk comparison items without making them strict-mode failures.
- Strict mode now also fails when baseline comparison includes regression items.

## 0.1.1

- Added `--format markdown|json` with Markdown remaining the default.
- Added machine-readable JSON dashboard output for stdout and `--output`.
- Added `--strict` automation mode, returning non-zero for risky, blocked, error, unknown, or warning-bearing reports.
- Documented JSON and strict-mode commands.

## 0.1.0

- Initial MVP for generating local Markdown dashboards from agent context JSON reports.
- Supports known schemas for agent-context-audit, agent-context-lint, and agent-instruction-guard.
- Preserves unknown JSON reports as warning cards.
