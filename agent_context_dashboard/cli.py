from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .compare import ComparisonResult, compare_to_baseline, load_baseline, load_compare_trends
from .models import ReportCard
from .render import (
    render_badge_snippets,
    render_html,
    render_hub_html,
    render_json,
    render_markdown,
    render_portfolio_markdown,
)
from .reports import DashboardError, load_reports
from .trend import load_trend, render_trend_json, render_trend_markdown


def build_dashboard(
    input_dir: Path,
    output: Path | None,
    output_format: str = "markdown",
    baseline: Path | None = None,
    recursive: bool = False,
    html_output: Path | None = None,
    compare: list[Path] | None = None,
    hub: Path | None = None,
    badge_snippets: Path | None = None,
    portfolio: Path | None = None,
) -> str:
    cards = load_reports(input_dir, recursive=recursive)
    comparison = compare_to_baseline(cards, load_baseline(baseline)) if baseline else None
    compare_trends = load_compare_trends(compare)
    generated_at = datetime.now(timezone.utc)
    dashboard = (
        render_json(
            cards,
            generated_at=generated_at,
            comparison=comparison,
            compare_trends=compare_trends,
            hub_path=hub.as_posix() if hub else None,
            portfolio_path=portfolio.as_posix() if portfolio else None,
            input_dir=input_dir.as_posix(),
        )
        if output_format == "json"
        else render_markdown(cards, generated_at=generated_at, comparison=comparison, compare_trends=compare_trends)
    )
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(dashboard, encoding="utf-8")
    if html_output:
        html_output.parent.mkdir(parents=True, exist_ok=True)
        html_output.write_text(
            render_html(cards, generated_at=generated_at, comparison=comparison, compare_trends=compare_trends),
            encoding="utf-8",
        )
    if hub:
        hub.parent.mkdir(parents=True, exist_ok=True)
        hub.write_text(
            render_hub_html(
                cards,
                generated_at=generated_at,
                comparison=comparison,
                compare_trends=compare_trends,
                input_dir=input_dir.as_posix(),
            ),
            encoding="utf-8",
        )
    if badge_snippets:
        badge_snippets.parent.mkdir(parents=True, exist_ok=True)
        badge_snippets.write_text(
            render_badge_snippets(
                cards,
                generated_at=generated_at,
                comparison=comparison,
                compare_trends=compare_trends,
                hub_href=hub.as_posix() if hub else None,
            ),
            encoding="utf-8",
        )
    if portfolio:
        portfolio.parent.mkdir(parents=True, exist_ok=True)
        portfolio.write_text(
            render_portfolio_markdown(
                cards,
                generated_at=generated_at,
                comparison=comparison,
                compare_trends=compare_trends,
                hub_path=hub.as_posix() if hub else None,
                input_dir=input_dir.as_posix(),
            ),
            encoding="utf-8",
        )
    return dashboard


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    command = getattr(args, "command", None)
    if command == "version":
        print(__version__)
        return 0

    try:
        if command == "trend":
            trend = load_trend(args.baseline_dashboard, args.current_dashboard)
            dashboard = render_trend_json(trend) if args.format == "json" else render_trend_markdown(trend)
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(dashboard, encoding="utf-8")
            else:
                print(dashboard, end="" if dashboard.endswith("\n") else "\n")
            return 0

        cards = load_reports(args.input_dir, recursive=args.recursive)
        comparison = compare_to_baseline(cards, load_baseline(args.baseline)) if args.baseline else None
        compare_trends = load_compare_trends(args.compare)
        generated_at = datetime.now(timezone.utc)
        dashboard = (
            render_json(
                cards,
                generated_at=generated_at,
                comparison=comparison,
                compare_trends=compare_trends,
                hub_path=args.hub.as_posix() if args.hub else None,
                portfolio_path=args.portfolio.as_posix() if args.portfolio else None,
                input_dir=args.input_dir.as_posix(),
            )
            if args.format == "json"
            else render_markdown(cards, generated_at=generated_at, comparison=comparison, compare_trends=compare_trends)
        )
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(dashboard, encoding="utf-8")
        if args.html_output:
            args.html_output.parent.mkdir(parents=True, exist_ok=True)
            args.html_output.write_text(
                render_html(cards, generated_at=generated_at, comparison=comparison, compare_trends=compare_trends),
                encoding="utf-8",
            )
        if args.hub:
            args.hub.parent.mkdir(parents=True, exist_ok=True)
            args.hub.write_text(
                render_hub_html(
                    cards,
                    generated_at=generated_at,
                    comparison=comparison,
                    compare_trends=compare_trends,
                    input_dir=args.input_dir.as_posix(),
                ),
                encoding="utf-8",
            )
        if args.badge_snippets:
            args.badge_snippets.parent.mkdir(parents=True, exist_ok=True)
            args.badge_snippets.write_text(
                render_badge_snippets(
                    cards,
                    generated_at=generated_at,
                    comparison=comparison,
                    compare_trends=compare_trends,
                    hub_href=args.hub.as_posix() if args.hub else None,
                ),
                encoding="utf-8",
            )
        if args.portfolio:
            args.portfolio.parent.mkdir(parents=True, exist_ok=True)
            args.portfolio.write_text(
                render_portfolio_markdown(
                    cards,
                    generated_at=generated_at,
                    comparison=comparison,
                    compare_trends=compare_trends,
                    hub_path=args.hub.as_posix() if args.hub else None,
                    input_dir=args.input_dir.as_posix(),
                ),
                encoding="utf-8",
            )
    except DashboardError as exc:
        print(f"agent-context-dashboard: error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"agent-context-dashboard: error: {exc}", file=sys.stderr)
        return 2

    if args.output is None:
        print(dashboard, end="" if dashboard.endswith("\n") else "\n")
    if args.strict and _has_strict_failures(cards, comparison):
        return 1
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-context-dashboard",
        description="Generate local Markdown, JSON, and HTML health dashboards from agent context JSON reports.",
    )
    parser.add_argument("input_dir", nargs="?", type=Path, help="Directory containing JSON reports.")
    parser.add_argument("-o", "--output", type=Path, help="Write dashboard output to this file.")
    parser.add_argument("--html-output", type=Path, help="Also write a static HTML dashboard summary to this file.")
    parser.add_argument("--hub", type=Path, help="Also write a standalone static HTML asset hub landing page.")
    parser.add_argument(
        "--badge-snippets",
        type=Path,
        help="Also write static Markdown and HTML badge snippets for README or release note embedding.",
    )
    parser.add_argument(
        "--portfolio",
        type=Path,
        help="Also write a local Markdown package-publish and portfolio landing page from hub metadata.",
    )
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown", help="Dashboard output format.")
    parser.add_argument("--baseline", type=Path, help="Compare against a prior JSON dashboard produced by --format json.")
    parser.add_argument(
        "--compare",
        type=Path,
        action="append",
        default=[],
        help="Include an agent-context-audit compare JSON file; repeat for multiple trend inputs.",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Recursively discover JSON reports under input_dir, excluding common cache/build/vendor directories.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when normalized reports include risks, blocked/error/unknown status, or warnings.",
    )
    parser.add_argument("--version", action="store_true", help="Print the package version and exit.")

    original_parse_args = parser.parse_args

    def parse_args(args: list[str] | None = None, namespace: argparse.Namespace | None = None) -> argparse.Namespace:
        raw = list(sys.argv[1:] if args is None else args)
        if raw and raw[0] == "trend":
            trend_parser = argparse.ArgumentParser(
                prog="agent-context-dashboard trend",
                description="Compare two JSON dashboards and render deterministic trend deltas.",
            )
            trend_parser.add_argument("baseline_dashboard", type=Path, help="Earlier JSON dashboard from --format json.")
            trend_parser.add_argument("current_dashboard", type=Path, help="Later JSON dashboard from --format json.")
            trend_parser.add_argument("-o", "--output", type=Path, help="Write trend output to this file.")
            trend_parser.add_argument(
                "--format",
                choices=("markdown", "json"),
                default="markdown",
                help="Trend output format.",
            )
            parsed = trend_parser.parse_args(raw[1:], namespace)
            parsed.command = "trend"
            return parsed
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


def _has_strict_failures(cards: list[ReportCard], comparison: ComparisonResult | None = None) -> bool:
    if comparison is not None and comparison.has_regressions:
        return True
    strict_statuses = {"blocked", "error", "risky", "unknown"}
    for card in cards:
        if card.is_risky or card.warning_count:
            return True
        if card.tool == "unknown" or card.status.lower() in strict_statuses:
            return True
    return False
