# Agent Notes

This repository is intentionally zero-dependency Python.

- Do not add GitHub workflows, SaaS callbacks, telemetry, or token-dependent tests.
- Keep the CLI usable from source with `python -m agent_context_dashboard`.
- Prefer `unittest` and standard-library modules only.
- Sample data must stay synthetic and must not contain secrets or token-looking strings.
- Generated dashboard examples should be Markdown and README/Feishu friendly.
