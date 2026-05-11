# Synthetic Asset Hub Export

Generate a standalone static HTML hub from the bundled synthetic reports:

```bash
python -m agent_context_dashboard examples/reports --compare examples/compare.json --hub /tmp/agent-context-dashboard-hub.html --output /tmp/agent-context-dashboard.md
```

Generate a multi-repo hub, with companion badge snippets, from the recursive sample workspace:

```bash
python -m agent_context_dashboard examples/multi-repo-reports --recursive --compare examples/multi-repo-compare.json --hub /tmp/agent-context-dashboard-multi-hub.html --badge-snippets /tmp/agent-context-dashboard-badges.md --output /tmp/agent-context-dashboard-multi.md
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

The example inputs are synthetic and contain no secrets or token-looking strings.
