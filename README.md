# agent-context-dashboard

`agent-context-dashboard` is a zero-dependency Python CLI that aggregates local JSON outputs from agent context toolchains into one Markdown asset health dashboard.

It is built for maintainers and consultants operating multiple AI-agent context or instruction repositories who need a quick portfolio summary without SaaS, hosted services, or external packages.

## What It Does

- Reads JSON report files from a directory.
- Normalizes known schemas from `agent-context-audit`, `agent-context-lint`, and `agent-instruction-guard`.
- Keeps unknown JSON visible as warning cards instead of dropping it.
- Generates a README/Feishu-friendly Markdown dashboard with summary counts, report cards, risks, warnings, and next actions.

## Install From Source

```bash
git clone <repo-url>
cd agent-context-dashboard
python -m pip install .
```

For local development without installing:

```bash
python -m agent_context_dashboard examples/reports --output examples/DASHBOARD.md
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
```

If `--output` is omitted, the dashboard is printed to stdout.

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
python scripts/selfcheck.py
python -m compileall agent_context_dashboard tests scripts
```

The selfcheck reads `examples/reports`, writes `/tmp/agent-context-dashboard-selfcheck.md`, and asserts key dashboard strings.
