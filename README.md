# agent-context-dashboard

`agent-context-dashboard` is a zero-dependency Python CLI that aggregates local JSON outputs from agent context toolchains into Markdown, JSON, and static HTML asset health dashboards.

It is built for maintainers and consultants operating multiple AI-agent context or instruction repositories who need a quick portfolio summary without SaaS, hosted services, or external packages.

## What It Does

- Reads JSON report files from a directory.
- Normalizes known schemas from `agent-context-audit`, `agent-context-lint`, `agent-instruction-guard`, and SARIF 2.1.0.
- Keeps unknown JSON visible as warning cards instead of dropping it.
- Generates a README/Feishu-friendly Markdown dashboard with summary counts, report cards, risks, warnings, and next actions.
- Emits machine-readable JSON for local automation.
- Writes a static, escaped HTML summary for local review or sharing.
- Compares current output against a previous JSON dashboard to surface regressions.

## Install From Source

```bash
git clone <repo-url>
cd agent-context-dashboard
python -m pip install .
```

For local development without installing:

```bash
python -m agent_context_dashboard examples/reports --output examples/DASHBOARD.md
python -m agent_context_dashboard examples/reports --output examples/DASHBOARD.md --html-output examples/DASHBOARD.html
```

## Usage

```bash
agent-context-dashboard <reports-dir> --output DASHBOARD.md
agent-context-dashboard build <reports-dir> --output DASHBOARD.md
python -m agent_context_dashboard <reports-dir> --output DASHBOARD.md
```

Sample command:

```bash
python -m agent_context_dashboard build examples/reports --output examples/DASHBOARD.md
python -m agent_context_dashboard build examples/reports --output examples/DASHBOARD.md --html-output examples/DASHBOARD.html
```

SARIF files can live beside the other JSON reports. For example, include SARIF emitted by `agent-instruction-guard` and build the dashboard from that shared report directory:

```bash
mkdir -p /tmp/agent-reports
agent-instruction-guard scan AGENTS.md --format sarif --output /tmp/agent-reports/guard.sarif.json
python -m agent_context_dashboard /tmp/agent-reports --output /tmp/dashboard.md
```

If `--output` is omitted, the dashboard is printed to stdout.

Markdown is the default output format. Use JSON for scripts:

```bash
python -m agent_context_dashboard examples/reports --format json
python -m agent_context_dashboard examples/reports --format json --output examples/DASHBOARD.json
```

Use `--html-output` to write a static HTML summary alongside Markdown or JSON output:

```bash
python -m agent_context_dashboard examples/reports --output examples/DASHBOARD.md --html-output examples/DASHBOARD.html
python -m agent_context_dashboard examples/reports --format json --output examples/DASHBOARD.json --html-output examples/DASHBOARD.html
```

The HTML dashboard includes the generated timestamp, overall status, summary counts, per-report rows, top warnings/errors, baseline comparison when `--baseline` is used, and SARIF report details when SARIF files are present.

By default, only top-level `*.json` files in the reports directory are read. Use `--recursive` for multi-repo report workspaces where companion tools write under per-repo subdirectories:

```bash
mkdir -p /tmp/reports-workspace/repo-a /tmp/reports-workspace/repo-b
cp examples/reports/lint.json /tmp/reports-workspace/repo-a/lint.json
cp examples/reports/lint.json /tmp/reports-workspace/repo-b/lint.json

python -m agent_context_dashboard /tmp/reports-workspace --recursive --output /tmp/dashboard.md
python -m agent_context_dashboard /tmp/reports-workspace --recursive --format json --output /tmp/dashboard.json
```

Recursive mode records stable source paths relative to the input directory, such as `repo-a/lint.json` and `repo-b/lint.json`, so repeated filenames remain distinct in Markdown, JSON, and baseline comparisons. Common cache, build, and vendor directories such as `.git`, `__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `node_modules`, `venv`, `.venv`, `dist`, and `build` are skipped.

Use `--strict` when automation should fail on risky, blocked, error, or unknown normalized reports, or on any warnings:

```bash
python -m agent_context_dashboard examples/reports --strict
python -m agent_context_dashboard examples/reports --format json --strict --output /tmp/dashboard.json
```

Without `--strict`, the CLI exits 0 after successful IO and JSON parsing even when the dashboard contains risks or unknown schemas.

Compare against a previous dashboard JSON with `--baseline`. The baseline must be a JSON dashboard produced by `--format json`:

```bash
python -m agent_context_dashboard examples/reports --format json --output /tmp/baseline-dashboard.json
python -m agent_context_dashboard examples/reports --baseline /tmp/baseline-dashboard.json --output /tmp/dashboard.md
python -m agent_context_dashboard examples/reports --baseline /tmp/baseline-dashboard.json --format json --output /tmp/dashboard.json
python -m agent_context_dashboard examples/reports --baseline /tmp/baseline-dashboard.json --output /tmp/dashboard.md --html-output /tmp/dashboard.html
```

Baseline comparison detects:

- `new_unknown_schema`: current report tool is unknown and the same source/tool key was absent before.
- `new_risk`: current report is risky and the same source/tool key was not risky or was absent before.
- `increased_warnings`: current warning count is higher than the same source/tool key in the baseline.
- `resolved_risk`: the baseline was risky and the current same source/tool key is no longer risky.

Markdown output includes a `## Baseline Comparison` section when `--baseline` is provided. JSON output includes `comparison.summary` and `comparison.items`.

With `--strict`, baseline regressions fail the command. `resolved_risk` items do not fail strict mode:

```bash
python -m agent_context_dashboard examples/reports --baseline /tmp/baseline-dashboard.json --strict
python -m agent_context_dashboard examples/reports --baseline /tmp/baseline-dashboard.json --format json --strict
python -m agent_context_dashboard examples/reports --baseline /tmp/baseline-dashboard.json --strict --html-output /tmp/dashboard.html
```

## Supported Report Schemas

### agent-context-audit

Detected when JSON includes agent-context-audit tool metadata or stable audit fields such as:

- `tool.name: "agent-context-audit"` or `tool_name: "agent-context-audit"`
- `overall_score`
- `grade` / `status`
- `summary`
- optional `findings` / `recommendations`

Legacy report shapes with `repository`, `summary`, and `findings` are also accepted.

### agent-context-lint

Detected when JSON includes the current structured lint shape:

- `scanned_files`
- `issues`
- `summary.average_score`
- `summary.error`, `summary.warn`, `summary.info`

Legacy single-file shapes with `file`, `violations`, and `score` are also accepted.

### agent-instruction-guard

Detected when JSON includes the current guard JSON shape:

- `summary.high`, `summary.medium`, `summary.low`
- `findings` or `issues`
- optional `suppressed`

Legacy allow/deny decision reports with `allow`, `allowed`, `deny`, `denied`, or `blocked` are also accepted.

### SARIF 2.1.0

Detected when JSON has a `runs` list plus `version: "2.1.0"` or SARIF-identifying top-level metadata such as a SARIF `$schema` URL.

SARIF reports are normalized as `sarif` by default. When `runs[].tool.driver.name` contains `agent-instruction-guard`, they are normalized as `agent-instruction-guard` so SARIF output from that companion asset aggregates with guard JSON reports.

Dashboard summaries include total SARIF result count plus error, warning, and note counts. Results with `level` `error` or `warning`, or with a missing or unknown level, count as risky. Results with `level` `note`, `none`, or `pass` do not count as risky.

### Unknown JSON

Unknown schemas are included as `unknown` cards with file metadata and a warning. This keeps new tool outputs visible until a normalizer is added.

## Non-Goals

- No SaaS dashboard, remote upload, telemetry, or token handling.
- No GitHub workflows in this repository.
- No external runtime or test dependencies.
- No attempt to fully validate every upstream tool schema.
- No wide Markdown tables; output should stay readable in READMEs and Feishu documents.

## Local Validation

```bash
python -m unittest
python -m unittest discover -s tests -v
python scripts/selfcheck.py
python -m compileall agent_context_dashboard tests scripts
```

The selfcheck reads `examples/reports`, writes `/tmp/agent-context-dashboard-selfcheck.md`, and asserts key dashboard strings.
