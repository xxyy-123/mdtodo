"""Tests for :mod:`mdtodo.formatters`."""

from __future__ import annotations

import json
import unittest
from datetime import date

from mdtodo.formatters import (
    render_json,
    render_markdown,
    render_plain,
    render_table,
    summarise,
)
from mdtodo.parser import TodoItem

TODAY = date(2026, 10, 31)


def make_items() -> list[TodoItem]:
    return [
        TodoItem("docs/a.md", 3, "TODO", "write the intro", owner="alice", tags=("docs",)),
        TodoItem("docs/a.md", 9, "FIXME", "broken anchor", owner="bob"),
        TodoItem("src/b.md", 1, "TASK", "add pagination", tags=("api",), due="2026-11-02"),
        TodoItem("src/b.md", 2, "HACK", "sleep on startup", due="2026-10-01"),
    ]


class RenderPlainTests(unittest.TestCase):
    def test_contains_location_and_kind(self) -> None:
        out = render_plain(make_items())
        self.assertIn("docs/a.md:3 [TODO] (alice) write the intro #docs", out)
        self.assertEqual(len(out.splitlines()), 4)

    def test_empty(self) -> None:
        self.assertEqual(render_plain([]), "")


class RenderTableTests(unittest.TestCase):
    def test_headers_present(self) -> None:
        out = render_table(make_items())
        header = out.splitlines()[0]
        for column in ("LOCATION", "KIND", "OWNER", "TEXT", "DUE"):
            self.assertIn(column, header)

    def test_empty_message(self) -> None:
        self.assertEqual(render_table([]), "No items found.")

    def test_truncation(self) -> None:
        item = TodoItem("a.md", 1, "TODO", "x" * 100)
        out = render_table([item], max_text=20)
        self.assertIn("...", out)
        body = out.splitlines()[-1]
        self.assertLess(len(body), 120)

    def test_missing_owner_renders_dash(self) -> None:
        item = TodoItem("a.md", 1, "TODO", "no owner")
        out = render_table([item])
        self.assertIn("-", out.splitlines()[-1])


class RenderMarkdownTests(unittest.TestCase):
    def test_groups_by_kind_with_counts(self) -> None:
        out = render_markdown(make_items(), today=TODAY)
        self.assertIn("# TODO report", out)
        self.assertIn("## FIXME (1)", out)
        self.assertIn("## HACK (1)", out)
        self.assertIn("## TASK (1)", out)
        self.assertIn("## TODO (1)", out)

    def test_checkboxes_and_locations(self) -> None:
        out = render_markdown(make_items(), today=TODAY)
        self.assertIn("- [ ] write the intro - `docs/a.md:3` @alice", out)

    def test_due_relative_wording(self) -> None:
        out = render_markdown(make_items(), today=TODAY)
        self.assertIn("due in 2d, 2026-11-02", out)
        self.assertIn("overdue 30d, due 2026-10-01", out)

    def test_due_today_wording(self) -> None:
        item = TodoItem("a.md", 1, "TODO", "now", due="2026-10-31")
        out = render_markdown([item], today=TODAY)
        self.assertIn("due today, 2026-10-31", out)

    def test_checked_item_marked(self) -> None:
        item = TodoItem("a.md", 1, "TASK", "done", checked=True)
        out = render_markdown([item], today=TODAY)
        self.assertIn("- [x] done", out)

    def test_empty_report(self) -> None:
        out = render_markdown([], today=TODAY)
        self.assertIn("_No open items. Nice._", out)

    def test_custom_title_and_trailing_newline(self) -> None:
        out = render_markdown(make_items(), title="Sprint 12", today=TODAY)
        self.assertTrue(out.startswith("# Sprint 12\n"))
        self.assertTrue(out.endswith("\n"))


class RenderJsonTests(unittest.TestCase):
    def test_valid_json_list(self) -> None:
        payload = json.loads(render_json(make_items()))
        self.assertEqual(len(payload), 4)
        self.assertEqual(payload[0]["path"], "docs/a.md")
        self.assertEqual(payload[0]["tags"], ["docs"])

    def test_ensure_ascii_false(self) -> None:
        item = TodoItem("a.md", 1, "TODO", "中文任务")
        self.assertIn("中文任务", render_json([item]))


class SummariseTests(unittest.TestCase):
    def test_counts(self) -> None:
        summary = summarise(make_items(), today=TODAY)
        self.assertEqual(summary.total, 4)
        self.assertEqual(summary.files, 2)
        self.assertEqual(summary.by_kind["TODO"], 1)
        self.assertEqual(summary.by_owner["alice"], 1)
        self.assertEqual(summary.by_owner["(unassigned)"], 2)
        self.assertEqual(summary.by_tag["docs"], 1)
        self.assertEqual(summary.overdue, 1)
        self.assertEqual(summary.due_today, 0)

    def test_owner_sorted_by_count(self) -> None:
        items = [
            TodoItem("a.md", 1, "TODO", "x", owner="b"),
            TodoItem("a.md", 2, "TODO", "y", owner="a"),
            TodoItem("a.md", 3, "TODO", "z", owner="a"),
        ]
        summary = summarise(items, today=TODAY)
        self.assertEqual(list(summary.by_owner), ["a", "b"])

    def test_empty(self) -> None:
        summary = summarise([], today=TODAY)
        self.assertEqual(summary.total, 0)
        self.assertEqual(summary.by_kind, {})

    def test_as_dict_keys(self) -> None:
        data = summarise(make_items(), today=TODAY).as_dict()
        self.assertEqual(
            set(data),
            {"total", "by_kind", "by_owner", "by_tag", "overdue", "due_today", "files"},
        )


if __name__ == "__main__":
    unittest.main()
