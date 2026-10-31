"""mdtodo - collect TODO comments and task list items from Markdown files."""

from __future__ import annotations

from .parser import (
    DEFAULT_KINDS,
    MARKDOWN_SUFFIXES,
    TodoItem,
    iter_markdown_files,
    parse_line,
    scan_paths,
    scan_text,
)

__version__ = "0.2.0"

__all__ = [
    "DEFAULT_KINDS",
    "MARKDOWN_SUFFIXES",
    "TodoItem",
    "__version__",
    "iter_markdown_files",
    "parse_line",
    "scan_paths",
    "scan_text",
]
