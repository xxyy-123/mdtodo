"""Command line interface for mdtodo."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from . import __version__
from .formatters import (
    render_json,
    render_markdown,
    render_plain,
    render_table,
    summarise,
)
from .parser import DEFAULT_KINDS, MARKDOWN_SUFFIXES, scan_paths

PROG = "mdtodo"

EXIT_OK = 0
EXIT_NO_ITEMS = 1
EXIT_USAGE = 2

ALL_KINDS: tuple[str, ...] = (*DEFAULT_KINDS, "TASK")


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser; split out so tests can introspect it."""
    parser = argparse.ArgumentParser(
        prog=PROG,
        description="Collect TODO/FIXME comments and task-list items from Markdown files.",
        epilog="Example: mdtodo scan docs/ --format table --kind TODO --tag backend",
    )
    parser.add_argument("--version", action="version", version=f"{PROG} {__version__}")

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "paths",
        nargs="*",
        default=["."],
        help="Files or directories to scan (default: current directory).",
    )
    common.add_argument(
        "--kind",
        action="append",
        choices=list(ALL_KINDS),
        dest="kinds",
        metavar="KIND",
        help="Restrict to a marker kind (%s); repeatable." % ", ".join(ALL_KINDS),
    )
    common.add_argument(
        "--tag",
        action="append",
        dest="tags",
        default=[],
        metavar="TAG",
        help="Only keep items carrying TAG; repeatable.",
    )
    common.add_argument("--owner", help="Only keep items assigned to this owner.")
    common.add_argument(
        "--include-checked",
        action="store_true",
        help="Include already-checked task list items.",
    )
    common.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="PATH_OR_GLOB",
        help=(
            "Skip a path or glob; repeatable. A bare name (vendored) skips that "
            "directory anywhere, docs/archive skips that prefix, and patterns "
            "with * ? [ are matched as globs."
        ),
    )
    common.add_argument(
        "--include-code",
        action="store_true",
        help="Also scan inside fenced code blocks and inline code (default: skip).",
    )
    common.add_argument(
        "--suffix",
        action="append",
        dest="suffixes",
        default=None,
        metavar="EXT",
        help="File extensions to treat as Markdown; repeatable.",
    )

    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    scan = sub.add_parser("scan", parents=[common], help="List matching items.")
    scan.add_argument(
        "--format",
        choices=["table", "plain", "json", "markdown"],
        default="table",
        help="Output format (default: table).",
    )
    scan.add_argument("--max-text", type=int, default=60, help="Truncate text at N chars.")

    stats = sub.add_parser("stats", parents=[common], help="Print aggregate counts.")
    stats.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text).",
    )

    report = sub.add_parser("report", parents=[common], help="Emit a Markdown report.")
    report.add_argument("--title", default="TODO report", help="Report heading.")
    report.add_argument("--output", metavar="FILE", help="Write to FILE instead of stdout.")

    sub.add_parser("version", help="Print the version and exit.")
    return parser


def collect(args: argparse.Namespace) -> list:
    """Run the scan and apply the post-scan filters."""
    kinds = tuple(args.kinds) if args.kinds else ALL_KINDS
    items = scan_paths(
        args.paths or ["."],
        kinds=kinds,
        include_checked=args.include_checked,
        exclude=args.exclude,
        suffixes=tuple(args.suffixes) if args.suffixes else MARKDOWN_SUFFIXES,
        ignore_code=not args.include_code,
    )
    if args.tags:
        wanted = {tag.lower() for tag in args.tags}
        items = [item for item in items if wanted & {t.lower() for t in item.tags}]
    if args.owner:
        target = args.owner.lower()
        items = [item for item in items if (item.owner or "").lower() == target]
    return items


def _cmd_scan(args: argparse.Namespace) -> int:
    items = collect(args)
    if args.format == "json":
        print(render_json(items))
    elif args.format == "plain":
        text = render_plain(items)
        print(text if text else "No items found.")
    elif args.format == "markdown":
        print(render_markdown(items), end="")
    else:
        print(render_table(items, max_text=args.max_text))
    return EXIT_OK if items else EXIT_NO_ITEMS


def _cmd_stats(args: argparse.Namespace) -> int:
    summary = summarise(collect(args))
    if args.format == "json":
        print(json.dumps(summary.as_dict(), indent=2, ensure_ascii=False))
        return EXIT_OK if summary.total else EXIT_NO_ITEMS
    print(f"Files scanned : {summary.files}")
    print(f"Total items   : {summary.total}")
    if summary.by_kind:
        print("By kind       : " + ", ".join(f"{k}={v}" for k, v in summary.by_kind.items()))
    if summary.by_owner:
        print("By owner      : " + ", ".join(f"{k}={v}" for k, v in summary.by_owner.items()))
    if summary.by_tag:
        print("By tag        : " + ", ".join(f"#{k}={v}" for k, v in summary.by_tag.items()))
    print(f"Overdue       : {summary.overdue}")
    print(f"Due today     : {summary.due_today}")
    return EXIT_OK if summary.total else EXIT_NO_ITEMS


def _cmd_report(args: argparse.Namespace) -> int:
    items = collect(args)
    document = render_markdown(items, title=args.title)
    if args.output:
        Path(args.output).write_text(document, encoding="utf-8")
        print(f"Wrote {len(items)} item(s) to {args.output}")
    else:
        print(document, end="")
    return EXIT_OK if items else EXIT_NO_ITEMS


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point used by both ``python -m mdtodo`` and the console script."""
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.command is None:
        parser.print_help()
        return EXIT_USAGE
    if args.command == "version":
        print(f"{PROG} {__version__}")
        return EXIT_OK

    handlers = {"scan": _cmd_scan, "stats": _cmd_stats, "report": _cmd_report}
    handler = handlers.get(args.command)
    if handler is None:  # pragma: no cover - argparse guards this
        parser.error(f"unknown command {args.command!r}")
        return EXIT_USAGE
    return handler(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
