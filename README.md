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
- Exports a standalone static HTML asset hub landing page with stable sections, deterministic health/trend badges, and local-only badge snippets for sharing multiple report assets.
- Writes a Markdown package-publish and portfolio landing page from hub metadata for README, Feishu, or local release handoff use.
- Compares current output against a previous JSON dashboard to surface regressions.
- Includes score trend deltas from one or more `agent-context-audit compare` JSON files.

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
python -m agent_context_dashboard examples/reports --compare examples/compare.json --hub examples/ASSET_HUB.html
python -m agent_context_dashboard examples/multi-repo-reports --recursive --compare examples/multi-repo-compare.json --hub examples/ASSET_HUB.html --badge-snippets examples/BADGES.md --portfolio examples/PORTFOLIO.md
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
python -m agent_context_dashboard build examples/reports --compare examples/compare.json --hub examples/ASSET_HUB.html
python -m agent_context_dashboard build examples/multi-repo-reports --recursive --compare examples/multi-repo-compare.json --hub examples/MULTI_REPO_ASSET_HUB.html --badge-snippets examples/MULTI_REPO_BADGES.md --portfolio examples/MULTI_REPO_PORTFOLIO.md
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

The HTML dashboard includes the generated timestamp, overall status, summary counts, per-report rows, top warnings/errors, baseline comparison when `--baseline` is used, score trends when `--compare` is used, and SARIF report details when SARIF files are present.

Use `--hub` to write a standalone static HTML asset hub landing page. This is intended for GitHub issue comments, release artifacts, local handoff folders, or README-linked snapshots where maintainers want one shareable page summarizing many agent-tool report files:

```bash
python -m agent_context_dashboard examples/reports --compare examples/compare.json --hub examples/ASSET_HUB.html
python -m agent_context_dashboard examples/reports --format json --output examples/DASHBOARD.json --hub examples/ASSET_HUB.html
```

The hub page includes stable anchors for `Overview`, `Asset Matrix`, `Trend Signals`, `Badge Snippets`, `Verification Commands`, and `Source Reports`. It also renders deterministic header badges for overall health and compare-score trend state. When hub export is requested with JSON output, the JSON dashboard includes a `hub` object with the hub path, generated timestamp, input count, badge data under `hub.badges`, and snippet data under `hub.snippets`. The generated page is a local static artifact; it does not require GitHub Actions, SaaS callbacks, telemetry, tokens, or repository workflow permissions.

See `examples/ASSET_HUB.md` for a synthetic hub export command and expected section list.

Use `--badge-snippets` to write a standalone Markdown file containing embeddable Markdown and HTML snippets for the generated Health and Trend badges:

```bash
python -m agent_context_dashboard examples/reports --compare examples/compare.json --hub examples/ASSET_HUB.html --badge-snippets examples/BADGES.md
python -m agent_context_dashboard examples/multi-repo-reports --recursive --compare examples/multi-repo-compare.json --hub examples/MULTI_REPO_ASSET_HUB.html --badge-snippets examples/MULTI_REPO_BADGES.md
```

The snippets are static text/HTML that link to the hub page. They do not use remote badge image services or callbacks. Hub HTML exports also include a `Badge Snippets` section, and JSON dashboards produced with `--hub` include the same data under `hub.snippets`.

Use `--portfolio` to write a Markdown package-publish and portfolio landing page from the same hub metadata used by the hub JSON object:

```bash
python -m agent_context_dashboard examples/reports --compare examples/compare.json --hub examples/ASSET_HUB.html --portfolio examples/PORTFOLIO.md --output examples/DASHBOARD.md
python -m agent_context_dashboard examples/multi-repo-reports --recursive --compare examples/multi-repo-compare.json --hub examples/MULTI_REPO_ASSET_HUB.html --badge-snippets examples/MULTI_REPO_BADGES.md --portfolio examples/MULTI_REPO_PORTFOLIO.md --output examples/MULTI_REPO_DASHBOARD.md
```

The portfolio page is Markdown and deterministic for the same normalized reports, compare inputs, hub path, and generated timestamp. It includes package publish commands, hub badge summaries, README snippets, report asset inventory, risk notes, and a local publish checklist. It does not call package registries, remote badge services, GitHub Actions, SaaS callbacks, telemetry, or token-backed APIs. JSON dashboards produced with `--portfolio` include a `portfolio` object with the output path, format, generated timestamp, and `source: "hub_metadata"`.

By default, only top-level `*.json` files in the reports directory are read. Use `--recursive` for multi-repo report workspaces where companion tools write under per-repo subdirectories:

```bash
mkdir -p /tmp/reports-workspace/repo-a /tmp/reports-workspace/repo-b
cp examples/reports/lint.json /tmp/reports-workspace/repo-a/lint.json
cp examples/reports/lint.json /tmp/reports-workspace/repo-b/lint.json

python -m agent_context_dashboard /tmp/reports-workspace --recursive --output /tmp/dashboard.md
python -m agent_context_dashboard /tmp/reports-workspace --recursive --format json --output /tmp/dashboard.json
python -m agent_context_dashboard examples/multi-repo-reports --recursive --compare examples/multi-repo-compare.json --hub /tmp/multi-repo-hub.html --badge-snippets /tmp/multi-repo-badges.md --output /tmp/multi-repo-dashboard.md
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

Include trend deltas from `agent-context-audit compare` JSON with repeatable `--compare` inputs:

```bash
agent-context-audit compare /tmp/audit-before.json /tmp/audit-after.json --write /tmp/audit-compare.json
python -m agent_context_dashboard examples/reports --compare /tmp/audit-compare.json --output /tmp/dashboard.md
python -m agent_context_dashboard examples/reports --compare /tmp/audit-compare.json --format json --output /tmp/dashboard.json
python -m agent_context_dashboard examples/reports --compare /tmp/audit-compare.json --html-output /tmp/dashboard.html
python -m agent_context_dashboard examples/reports --compare /tmp/repo-a-compare.json --compare /tmp/repo-b-compare.json --output /tmp/dashboard.md
```

Markdown and HTML output include a `Score Trends` section with baseline score, current score, score delta, changed/added/removed file counts, improved/regressed file counts, and rule issue delta. JSON output includes:

- `compare_summary`: aggregate entry counts, total score delta, file counts, and rule issue delta.
- `compare_entries`: one entry per compare input with `source`, `baseline_score`, `current_score`, `score_delta`, `changed_file_count`, `added_file_count`, `removed_file_count`, `files_improved_count`, `files_regressed_count`, and `rule_issue_delta`.

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
python -m agent_context_dashboard examples/reports --compare examples/compare.json --hub /tmp/agent-context-dashboard-hub.html --badge-snippets /tmp/agent-context-dashboard-badges.md --portfolio /tmp/agent-context-dashboard-portfolio.md --output /tmp/agent-context-dashboard.md
```

The selfcheck reads `examples/reports` and `examples/multi-repo-reports`, writes temporary Markdown/HTML/snippet/portfolio artifacts under `/tmp`, and asserts key dashboard, hub, badge, portfolio, and recursive multi-repo strings.
