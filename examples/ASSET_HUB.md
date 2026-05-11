# Synthetic Asset Hub Export

Generate a standalone static HTML hub from the bundled synthetic reports:

```bash
python -m agent_context_dashboard examples/reports --compare examples/compare.json --hub /tmp/agent-context-dashboard-hub.html --output /tmp/agent-context-dashboard.md
```

Generate a multi-repo hub, with companion badge snippets, from the recursive sample workspace:

```bash
python -m agent_context_dashboard examples/multi-repo-reports --recursive --compare examples/multi-repo-compare.json --hub /tmp/agent-context-dashboard-multi-hub.html --badge-snippets /tmp/agent-context-dashboard-badges.md --output /tmp/agent-context-dashboard-multi.md
```

Generate a package-publish and portfolio landing page from the same hub metadata:

```bash
python -m agent_context_dashboard examples/multi-repo-reports --recursive --compare examples/multi-repo-compare.json --hub /tmp/agent-context-dashboard-multi-hub.html --badge-snippets /tmp/agent-context-dashboard-badges.md --portfolio /tmp/agent-context-dashboard-portfolio.md --output /tmp/agent-context-dashboard-multi.md
```

The generated hub includes these stable sections:

- `Overview`
- `Asset Matrix`
- `Trend Signals`
- `Badge Snippets`
- `Verification Commands`
- `Source Reports`

The hub header also includes deterministic badges:

- `Health`: derived from normalized report status, warnings, unknown schemas, and baseline regressions.
- `Trend`: derived from compare-score deltas when `--compare` inputs are provided, or `no trend data` otherwise.

`--badge-snippets` writes a Markdown file containing local-only Markdown and HTML snippets that link to the hub page. The snippets do not call remote badge services.

`--portfolio` writes a Markdown landing page for package publishing and portfolio handoff. It is derived from hub metadata and includes package commands, badge summaries, README snippets, report assets, risk notes, and a publish checklist. It does not call registries, remote badge services, GitHub workflows, SaaS callbacks, telemetry, or token-backed APIs.

The example inputs are synthetic and contain no secrets or token-looking strings.
