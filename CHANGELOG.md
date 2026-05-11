# Changelog

## 0.5.0

- Added `trend BEFORE.json AFTER.json` mode for comparing two dashboard JSON outputs without rebuilding source reports.
- Trend Markdown and JSON output now include comparable score deltas, new/resolved warning messages, and release-readiness movement across `ready`, `review`, and `blocked` states.
- Added synthetic trend dashboard fixtures and a README/Feishu-friendly Markdown trend example.
- Expanded CLI, renderer, and selfcheck coverage for deterministic trend output.

## 0.4.5

- Added `--portfolio PATH` for writing a local Markdown package-publish and portfolio landing page from the same hub metadata used by JSON hub exports.
- Portfolio pages include package install/smoke-test commands, deterministic hub badge summaries, report asset inventory, risk notes, and a publish checklist.
- JSON dashboards now include a `portfolio` metadata object when `--portfolio` is used.
- Expanded tests and selfcheck coverage for portfolio output and deterministic renderer behavior.

## 0.4.4

- Added `--badge-snippets PATH` for writing static Markdown and HTML badge snippets that link to the generated asset hub.
- Added a `Badge Snippets` section to static asset hub HTML exports and included snippet data under `hub.snippets` in JSON dashboards when `--hub` is used.
- Added a synthetic recursive multi-repo fixture for asset hub and dashboard examples.
- Expanded selfcheck and tests to cover badge snippets, hub snippet sections, and multi-repo recursive sample output.

## 0.4.3

- Added deterministic Health and Trend badges to static asset hub HTML exports.
- JSON dashboards now include the same `hub.badges` data when hub export is requested.
- Documented the hub badge output and added regression coverage.

## 0.4.2

- Added `--hub PATH` for writing a standalone static HTML asset hub landing page.
- Hub pages include stable Overview, Asset Matrix, Trend Signals, Verification Commands, and Source Reports sections for README or local sharing workflows.
- JSON dashboards now include `hub` metadata with path, generated timestamp, and input count when hub export is requested.
- Added synthetic hub export coverage and documentation.

## 0.4.1

- Added repeatable `--compare PATH` support for `agent-context-audit compare` JSON trend inputs.
- JSON dashboards now include `compare_summary` and `compare_entries` with baseline/current scores, score delta, file change counts, improved/regressed file counts, rule issue delta, and source path.
- Markdown and HTML dashboards now include a concise `Score Trends` section when compare JSON is provided.
- Added malformed compare input validation and coverage for JSON, Markdown, and HTML outputs.

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
