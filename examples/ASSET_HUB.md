# Synthetic Asset Hub Export

Generate a standalone static HTML hub from the bundled synthetic reports:

```bash
python -m agent_context_dashboard examples/reports --compare examples/compare.json --hub /tmp/agent-context-dashboard-hub.html --output /tmp/agent-context-dashboard.md
```

The generated hub includes these stable sections:

- `Overview`
- `Asset Matrix`
- `Trend Signals`
- `Verification Commands`
- `Source Reports`

The hub header also includes deterministic badges:

- `Health`: derived from normalized report status, warnings, unknown schemas, and baseline regressions.
- `Trend`: derived from compare-score deltas when `--compare` inputs are provided, or `no trend data` otherwise.

The example inputs are synthetic and contain no secrets or token-looking strings.
