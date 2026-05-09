# Changelog

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
