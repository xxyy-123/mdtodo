"""Output renderers for :mod:`mdtodo`.

Each formatter takes the same list of :class:`~mdtodo.parser.TodoItem` objects
and returns a string. Keeping rendering separate from parsing means the CLI
never has to know about ANSI codes or table alignment.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable, Sequence

from .parser import TodoItem

__all__ = [
    "render_json",
    "render_markdown",
    "render_plain",
    "render_table",
    "summarise",
]

#: Order used when grouping by kind in the Markdown report.
KIND_ORDER: tuple[str, ...] = ("FIXME", "TODO", "HACK", "XXX", "TASK")


def _truncate(text: str, width: int) -> str:
    if width <= 0 or len(text) <= width:
        return text
    if width <= 3:
        return text[:width]
    return text[: width - 3].rstrip() + "..."


def _days_until(due: str, today: date | None = None) -> int | None:
    """Days from *today* until *due*; negative means overdue."""
    try:
        target = datetime.strptime(due, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None
    reference = today or date.today()
    return (target - reference).days


def render_plain(items: Iterable[TodoItem]) -> str:
    """One item per line as ``path:line [KIND] text``."""
    lines: list[str] = []
    for item in items:
        parts = [f"{item.path}:{item.line}", f"[{item.kind}]"]
        if item.owner:
            parts.append(f"({item.owner})")
        parts.append(item.text)
        if item.tags:
            parts.append(" ".join(f"#{tag}" for tag in item.tags))
        if item.due:
            parts.append(f"due:{item.due}")
        lines.append(" ".join(parts))
    return "\n".join(lines)


def render_table(items: Sequence[TodoItem], *, max_text: int = 60) -> str:
    """Fixed-width columns; truncates long descriptions."""
    if not items:
        return "No items found."
    headers = ("LOCATION", "KIND", "OWNER", "TEXT", "DUE")
    rows: list[tuple[str, ...]] = []
    for item in items:
        rows.append(
            (
                f"{item.path}:{item.line}",
                item.kind,
                item.owner or "-",
                _truncate(item.text, max_text),
                item.due or "-",
            )
        )
    widths = [
        max(len(headers[index]), *(len(row[index]) for row in rows))
        for index in range(len(headers))
    ]
    lines = [
        "  ".join(
            head.ljust(width) for head, width in zip(headers, widths)
        ).rstrip()
    ]
    lines.append("  ".join("-" * width for width in widths))
    for row in rows:
        lines.append(
            "  ".join(cell.ljust(width) for cell, width in zip(row, widths)).rstrip()
        )
    return "\n".join(lines)


def render_markdown(
    items: Sequence[TodoItem],
    *,
    title: str = "TODO report",
    today: date | None = None,
) -> str:
    """Group items by kind into a Markdown document with checkbox entries."""
    stamp = (today or date.today()).isoformat()
    out: list[str] = [f"# {title}", "", f"Generated on {stamp} by mdtodo.", ""]
    if not items:
        out.append("_No open items. Nice._")
        return "\n".join(out) + "\n"

    grouped: dict[str, list[TodoItem]] = {kind: [] for kind in KIND_ORDER}
    for item in items:
        grouped.setdefault(item.kind, []).append(item)

    counts = ", ".join(
        f"{kind}: {len(bucket)}" for kind, bucket in grouped.items() if bucket
    )
    out.extend([f"**{len(items)} item(s)** - {counts}", ""])

    for kind in list(KIND_ORDER) + sorted(set(grouped) - set(KIND_ORDER)):
        bucket = grouped.get(kind) or []
        if not bucket:
            continue
        out.append(f"## {kind} ({len(bucket)})")
        out.append("")
        for item in bucket:
            box = "x" if item.checked else " "
            line = f"- [{box}] {item.text} - `{item.path}:{item.line}`"
            if item.owner:
                line += f" @{item.owner}"
            if item.tags:
                line += " " + " ".join(f"`#{tag}`" for tag in item.tags)
            if item.due:
                remaining = _days_until(item.due, today)
                if remaining is None:
                    line += f" (due {item.due})"
                elif remaining < 0:
                    line += f" (overdue {abs(remaining)}d, due {item.due})"
                elif remaining == 0:
                    line += f" (due today, {item.due})"
                else:
                    line += f" (due in {remaining}d, {item.due})"
            out.append(line)
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def render_json(items: Sequence[TodoItem], *, indent: int | None = 2) -> str:
    """Machine-readable output."""
    return json.dumps([item.as_dict() for item in items], indent=indent, ensure_ascii=False)


@dataclass(frozen=True)
class Summary:
    """Aggregate counts used by ``mdtodo stats``."""

    total: int
    by_kind: dict[str, int]
    by_owner: dict[str, int]
    by_tag: dict[str, int]
    overdue: int
    due_today: int
    files: int

    def as_dict(self) -> dict[str, object]:
        return {
            "total": self.total,
            "by_kind": self.by_kind,
            "by_owner": self.by_owner,
            "by_tag": self.by_tag,
            "overdue": self.overdue,
            "due_today": self.due_today,
            "files": self.files,
        }


def summarise(items: Sequence[TodoItem], *, today: date | None = None) -> Summary:
    """Count items by kind, owner, tag and due-date status."""
    by_kind: dict[str, int] = {}
    by_owner: dict[str, int] = {}
    by_tag: dict[str, int] = {}
    overdue = 0
    due_today = 0
    today = today or date.today()

    for item in items:
        by_kind[item.kind] = by_kind.get(item.kind, 0) + 1
        key = item.owner or "(unassigned)"
        by_owner[key] = by_owner.get(key, 0) + 1
        for tag in item.tags:
            by_tag[tag] = by_tag.get(tag, 0) + 1
        if item.due:
            remaining = _days_until(item.due, today)
            if remaining is None:
                continue
            if remaining < 0:
                overdue += 1
            elif remaining == 0:
                due_today += 1

    files = len({item.path for item in items})
    return Summary(
        total=len(items),
        by_kind=dict(sorted(by_kind.items())),
        by_owner=dict(sorted(by_owner.items(), key=lambda kv: (-kv[1], kv[0]))),
        by_tag=dict(sorted(by_tag.items(), key=lambda kv: (-kv[1], kv[0]))),
        overdue=overdue,
        due_today=due_today,
        files=files,
    )
