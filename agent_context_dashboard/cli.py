from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .render import render_markdown
from .reports import DashboardError, load_reports


def build_dashboard(input_dir: Path, output: Path | None) -> str:
    cards = load_reports(input_dir)
    markdown = render_markdown(cards)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(markdown, encoding="utf-8")
    return markdown


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    command = getattr(args, "command", None)
    if command == "version":
        print(__version__)
        return 0

    try:
        markdown = build_dashboard(args.input_dir, args.output)
    except DashboardError as exc:
        print(f"agent-context-dashboard: error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"agent-context-dashboard: error: {exc}", file=sys.stderr)
        return 2

    if args.output is None:
        print(markdown)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-context-dashboard",
        description="Generate a local Markdown health dashboard from agent context JSON reports.",
    )
    parser.add_argument("input_dir", nargs="?", type=Path, help="Directory containing JSON reports.")
    parser.add_argument("-o", "--output", type=Path, help="Write dashboard Markdown to this file.")
    parser.add_argument("--version", action="store_true", help="Print the package version and exit.")

    original_parse_args = parser.parse_args

    def parse_args(args: list[str] | None = None, namespace: argparse.Namespace | None = None) -> argparse.Namespace:
        raw = list(sys.argv[1:] if args is None else args)
        if raw and raw[0] == "build":
            raw.pop(0)
        if raw and raw[0] == "version":
            return argparse.Namespace(command="version")
        parsed = original_parse_args(raw, namespace)
        if parsed.version:
            parsed.command = "version"
            return parsed
        if parsed.input_dir is None:
            parser.error("input_dir is required")
        parsed.command = "build"
        return parsed

    parser.parse_args = parse_args  # type: ignore[method-assign]
    return parser
