from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .models import ReportCard
from .render import render_json, render_markdown
from .reports import DashboardError, load_reports


def build_dashboard(input_dir: Path, output: Path | None, output_format: str = "markdown") -> str:
    cards = load_reports(input_dir)
    dashboard = render_json(cards) if output_format == "json" else render_markdown(cards)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(dashboard, encoding="utf-8")
    return dashboard


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    command = getattr(args, "command", None)
    if command == "version":
        print(__version__)
        return 0

    try:
        cards = load_reports(args.input_dir)
        dashboard = render_json(cards) if args.format == "json" else render_markdown(cards)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(dashboard, encoding="utf-8")
    except DashboardError as exc:
        print(f"agent-context-dashboard: error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"agent-context-dashboard: error: {exc}", file=sys.stderr)
        return 2

    if args.output is None:
        print(dashboard, end="" if dashboard.endswith("\n") else "\n")
    if args.strict and _has_strict_failures(cards):
        return 1
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-context-dashboard",
        description="Generate a local Markdown health dashboard from agent context JSON reports.",
    )
    parser.add_argument("input_dir", nargs="?", type=Path, help="Directory containing JSON reports.")
    parser.add_argument("-o", "--output", type=Path, help="Write dashboard output to this file.")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown", help="Dashboard output format.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when normalized reports include risks, blocked/error/unknown status, or warnings.",
    )
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


def _has_strict_failures(cards: list[ReportCard]) -> bool:
    strict_statuses = {"blocked", "error", "risky", "unknown"}
    for card in cards:
        if card.is_risky or card.warning_count:
            return True
        if card.tool == "unknown" or card.status.lower() in strict_statuses:
            return True
    return False
