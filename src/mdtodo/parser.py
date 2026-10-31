"""Core parsing logic for mdtodo.

The parser is intentionally dependency-free: it walks Markdown files, finds
TODO-like markers and task-list checkboxes, and turns each hit into a
``TodoItem`` record. Nothing here touches the filesystem's *content* beyond
reading text, which keeps the module easy to unit-test.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator, Sequence

__all__ = [
    "TodoItem",
    "ALL_KINDS",
    "DEFAULT_KINDS",
    "MARKDOWN_SUFFIXES",
    "parse_line",
    "scan_text",
    "iter_markdown_files",
    "scan_paths",
]

#: Colon-style markers we recognise inside a line of Markdown.
DEFAULT_KINDS: tuple[str, ...] = ("TODO", "FIXME", "HACK", "XXX")

#: Everything :func:`parse_line` looks for by default: markers plus checkboxes.
ALL_KINDS: tuple[str, ...] = (*DEFAULT_KINDS, "TASK")

#: File extensions we treat as Markdown unless the caller overrides them.
MARKDOWN_SUFFIXES: tuple[str, ...] = (".md", ".markdown", ".mdown", ".mkd")

# ``- [ ] text`` / ``* [x] text`` / ``1. [ ] text``
TASK_LIST_RE = re.compile(
    r"""^
    (?P<indent>[ \t]{0,8})          # leading indentation
    (?:[-*+]|\d{1,9}[.)])           # bullet or ordered-list marker
    [ \t]+
    \[(?P<state>[ xX])\]            # checkbox, empty or checked
    [ \t]+
    (?P<body>.*?)
    \s*$
    """,
    re.VERBOSE,
)

# ``TODO: text`` / ``TODO(alice): text`` / ``TODO（全角冒号）
MARKER_RE = re.compile(
    r"""
    \b(?P<kind>TODO|FIXME|HACK|XXX)   # the marker keyword
    (?:\((?P<owner>[^()]*)\))?        # optional (owner)
    \s*[:：]                          # ASCII or full-width colon
    \s*
    (?P<body>.*?)                     # the description
    \s*$
    """,
    re.VERBOSE | re.IGNORECASE,
)

TAG_RE = re.compile(r"(?:^|(?<=\s))#(?P<tag>[A-Za-z0-9_][A-Za-z0-9_./-]*)")
DUE_RE = re.compile(r"@due\((?P<due>\d{4}-\d{1,2}-\d{1,2})\)")

# Wrappers that commonly surround a marker in Markdown source.
HTML_COMMENT_RE = re.compile(r"<!--|-->")


@dataclass(frozen=True)
class TodoItem:
    """A single TODO-ish hit inside a Markdown file."""

    path: str
    line: int
    kind: str
    text: str
    owner: str | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)
    due: str | None = None
    checked: bool = False

    @property
    def is_task(self) -> bool:
        """True for checkbox task-list items rather than bare markers."""
        return self.kind.upper() == "TASK"

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-serialisable representation."""
        return {
            "path": self.path,
            "line": self.line,
            "kind": self.kind,
            "text": self.text,
            "owner": self.owner,
            "tags": list(self.tags),
            "due": self.due,
            "checked": self.checked,
        }


def _clean(text: str) -> str:
    """Strip wrapping noise (comment markers, bold/italic) from a snippet."""
    text = HTML_COMMENT_RE.sub("", text)
    text = text.strip()
    # ``**TODO:** do it`` -> ``do it`` style cleanup happens on the body only,
    # but strip stray emphasis left over from the marker itself.
    text = text.strip("*_` ")
    return re.sub(r"\s{2,}", " ", text).strip()


def _extract_meta(text: str) -> tuple[str, tuple[str, ...], str | None]:
    """Pull ``#tags`` and ``@due(...)`` out of *text*.

    Returns ``(cleaned_text, tags, due)`` where the tags and due marker have
    been removed from the description so output columns stay readable.
    """
    tags: list[str] = []

    def _take_tag(match: re.Match[str]) -> str:
        tag = match.group("tag")
        if tag not in tags:
            tags.append(tag)
        return ""

    due_match = DUE_RE.search(text)
    due = None
    if due_match:
        due = _normalise_date(due_match.group("due"))
        text = DUE_RE.sub("", text, count=1)

    text = TAG_RE.sub(_take_tag, text)
    text = _clean(text)
    return text, tuple(tags), due


def _normalise_date(raw: str) -> str:
    """Normalise ``2026-1-5`` to ``2026-01-05``."""
    year, month, day = (int(part) for part in raw.split("-"))
    return f"{year:04d}-{month:02d}-{day:02d}"


def parse_line(
    line: str,
    *,
    kinds: Sequence[str] = ALL_KINDS,
    include_checked: bool = False,
) -> tuple[str, str, str | None, tuple[str, ...], str | None, bool] | None:
    """Parse one line of Markdown.

    Returns ``(kind, text, owner, tags, due, checked)`` or ``None`` when the
    line holds no recognised item. ``kind`` is ``"TASK"`` for a bare checkbox
    and the marker keyword when a checkbox also carries one.
    """
    wanted = {kind.upper() for kind in kinds}
    checked = False
    body: str | None = None
    owner: str | None = None
    kind: str | None = None

    task = TASK_LIST_RE.match(line)
    if task:
        checked = task.group("state").strip().lower() == "x"
        if checked and not include_checked:
            return None
        body = task.group("body")
        rest = body or ""
        marker = MARKER_RE.search(rest)
        if marker and marker.group("kind").upper() in wanted:
            kind = marker.group("kind").upper()
            owner = (marker.group("owner") or "").strip() or None
            body = marker.group("body")
        elif marker:
            # A checkbox line that carries an explicit marker which the caller
            # filtered out; treat it as that marker, not as a bare task.
            return None
        elif "TASK" in wanted:
            kind = "TASK"
    else:
        marker = MARKER_RE.search(line)
        if marker is None or marker.group("kind").upper() not in wanted:
            return None
        kind = marker.group("kind").upper()
        owner = (marker.group("owner") or "").strip() or None
        body = marker.group("body")

    if kind is None:
        return None
    body = (body or "").strip()

    # Metadata first: ``@due(2026-1-5)`` must not be mistaken for a trailing
    # owner parenthetical, which is why this runs before the owner probe.
    text, tags, due = _extract_meta(body)

    # Support an owner that trails the description: ``TODO: fix it (alice)``
    if owner is None:
        trailing = re.search(r"\((?P<owner>[A-Za-z0-9_.\-]{1,40})\)\s*$", text)
        if trailing:
            owner = trailing.group("owner")
            text = text[: trailing.start()].rstrip()

    if not text and not tags:
        return None
    return kind, text, owner, tags, due, checked


def scan_text(
    text: str,
    path: str,
    *,
    kinds: Sequence[str] = ALL_KINDS,
    include_checked: bool = False,
) -> Iterator[TodoItem]:
    """Yield every :class:`TodoItem` found in *text*."""
    for number, raw in enumerate(text.splitlines(), start=1):
        parsed = parse_line(raw, kinds=kinds, include_checked=include_checked)
        if parsed is None:
            continue
        kind, body, owner, tags, due, checked = parsed
        yield TodoItem(
            path=path,
            line=number,
            kind=kind,
            text=body,
            owner=owner,
            tags=tags,
            due=due,
            checked=checked,
        )


def iter_markdown_files(
    roots: Iterable[str | Path],
    *,
    suffixes: Sequence[str] = MARKDOWN_SUFFIXES,
    exclude: Sequence[str] = (),
) -> Iterator[Path]:
    """Yield Markdown files under *roots*, skipping *exclude* glob patterns."""
    lowered = {suffix.lower() for suffix in suffixes}
    for root in roots:
        root_path = Path(root)
        if root_path.is_file():
            yield root_path
            continue
        for candidate in sorted(root_path.rglob("*")):
            if not candidate.is_file():
                continue
            if candidate.suffix.lower() not in lowered:
                continue
            parts = set(candidate.parts)
            if parts & {".git", "node_modules", ".venv", "__pycache__", ".mypy_cache"}:
                continue
            if any(candidate.match(pattern) for pattern in exclude):
                continue
            yield candidate


def scan_paths(
    roots: Iterable[str | Path],
    *,
    kinds: Sequence[str] = ALL_KINDS,
    include_checked: bool = False,
    exclude: Sequence[str] = (),
    suffixes: Sequence[str] = MARKDOWN_SUFFIXES,
) -> list[TodoItem]:
    """Scan *roots* and return all items sorted by path then line number."""
    items: list[TodoItem] = []
    for path in iter_markdown_files(roots, suffixes=suffixes, exclude=exclude):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        try:
            display = path.as_posix()
        except Exception:  # pragma: no cover - defensive
            display = str(path)
        items.extend(
            scan_text(
                text,
                display,
                kinds=kinds,
                include_checked=include_checked,
            )
        )
    items.sort(key=lambda item: (item.path, item.line))
    return items
