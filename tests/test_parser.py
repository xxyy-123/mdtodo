"""Tests for :mod:`mdtodo.parser`."""

from __future__ import annotations

import unittest
from pathlib import Path

from support import temp_workspace

from mdtodo.parser import (
    ALL_KINDS,
    DEFAULT_KINDS,
    TodoItem,
    iter_markdown_files,
    mask_code,
    parse_line,
    scan_paths,
    scan_text,
)


class ParseLineTests(unittest.TestCase):
    def test_simple_marker(self) -> None:
        parsed = parse_line("TODO: rewrite the retry loop")
        self.assertIsNotNone(parsed)
        kind, text, owner, tags, due, checked = parsed
        self.assertEqual(kind, "TODO")
        self.assertEqual(text, "rewrite the retry loop")
        self.assertIsNone(owner)
        self.assertEqual(tags, ())
        self.assertIsNone(due)
        self.assertFalse(checked)

    def test_owner_in_parentheses(self) -> None:
        parsed = parse_line("FIXME(alice): race on shutdown")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed[0], "FIXME")
        self.assertEqual(parsed[1], "race on shutdown")
        self.assertEqual(parsed[2], "alice")

    def test_owner_trailing(self) -> None:
        parsed = parse_line("TODO: fix the parser (bob)")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed[2], "bob")
        self.assertEqual(parsed[1], "fix the parser")

    def test_metadata_extraction(self) -> None:
        parsed = parse_line("HACK: temporary shim #infra #deploy @due(2026-1-5)")
        self.assertIsNotNone(parsed)
        _, text, _, tags, due, _ = parsed
        self.assertEqual(tags, ("infra", "deploy"))
        self.assertEqual(due, "2026-01-05")
        self.assertEqual(text, "temporary shim")
        self.assertNotIn("#", text)

    def test_full_width_colon(self) -> None:
        parsed = parse_line("TODO\uff1a\u4e2d\u6587\u5192\u53f7\u4e5f\u8981\u652f\u6301")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed[0], "TODO")
        self.assertEqual(parsed[1], "\u4e2d\u6587\u5192\u53f7\u4e5f\u8981\u652f\u6301")

    def test_prose_without_colon_is_ignored(self) -> None:
        self.assertIsNone(parse_line("Keep a TODO list somewhere handy."))
        self.assertIsNone(parse_line("The word TODO appears here."))

    def test_unknown_kind_filtered_out(self) -> None:
        self.assertIsNone(parse_line("NOTE: not a tracked marker"))

    def test_custom_kind_filter(self) -> None:
        self.assertIsNone(parse_line("FIXME: x", kinds=("TODO",)))
        self.assertIsNotNone(parse_line("FIXME: x", kinds=("FIXME",)))

    def test_unchecked_task(self) -> None:
        parsed = parse_line("- [ ] add pagination #api")
        self.assertIsNotNone(parsed)
        kind, text, _, tags, _, checked = parsed
        self.assertEqual(kind, "TASK")
        self.assertEqual(text, "add pagination")
        self.assertEqual(tags, ("api",))
        self.assertFalse(checked)

    def test_checked_task_hidden_by_default(self) -> None:
        self.assertIsNone(parse_line("- [x] finished thing"))
        parsed = parse_line("- [x] finished thing", include_checked=True)
        self.assertIsNotNone(parsed)
        self.assertTrue(parsed[5])

    def test_task_with_marker_uses_marker_kind(self) -> None:
        parsed = parse_line("- [ ] TODO: hook up metrics")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed[0], "TODO")
        self.assertEqual(parsed[1], "hook up metrics")

    def test_task_with_filtered_marker_is_skipped(self) -> None:
        self.assertIsNone(parse_line("- [ ] FIXME: y", kinds=("TASK",)))

    def test_ordered_and_star_bullets(self) -> None:
        for bullet in ("1. [ ] first", "* [ ] star", "+ [ ] plus"):
            with self.subTest(bullet=bullet):
                parsed = parse_line(bullet)
                self.assertIsNotNone(parsed)
                self.assertEqual(parsed[0], "TASK")

    def test_empty_body_rejected(self) -> None:
        self.assertIsNone(parse_line("TODO:"))
        self.assertIsNone(parse_line("TODO:   "))


class ScanTextTests(unittest.TestCase):
    SAMPLE = "\n".join(
        [
            "# Notes",
            "",
            "TODO: first thing",
            "Some prose here.",
            "- [ ] second thing #ui",
            "- [x] already done",
            "FIXME(carol): third thing @due(2026-02-01)",
        ]
    )

    def test_line_numbers_are_one_based(self) -> None:
        items = list(scan_text(self.SAMPLE, "notes.md"))
        self.assertEqual([item.line for item in items], [3, 5, 7])

    def test_kinds_and_path(self) -> None:
        items = list(scan_text(self.SAMPLE, "notes.md"))
        self.assertEqual([item.kind for item in items], ["TODO", "TASK", "FIXME"])
        self.assertTrue(all(item.path == "notes.md" for item in items))

    def test_include_checked(self) -> None:
        items = list(scan_text(self.SAMPLE, "notes.md", include_checked=True))
        self.assertEqual(len(items), 4)

    def test_windows_line_endings(self) -> None:
        items = list(scan_text("TODO: a\r\nTODO: b\r\n", "w.md"))
        self.assertEqual([item.text for item in items], ["a", "b"])


class AsDictTests(unittest.TestCase):
    def test_round_trip_shape(self) -> None:
        item = TodoItem(
            path="a.md",
            line=2,
            kind="TODO",
            text="do it",
            owner="alice",
            tags=("x",),
            due="2026-01-01",
        )
        data = item.as_dict()
        self.assertEqual(data["tags"], ["x"])
        self.assertEqual(data["owner"], "alice")
        self.assertFalse(data["checked"])

    def test_is_task(self) -> None:
        self.assertTrue(TodoItem("a", 1, "TASK", "x").is_task)
        self.assertFalse(TodoItem("a", 1, "TODO", "x").is_task)


class FileScanTests(unittest.TestCase):
    def test_scan_paths_finds_markdown_only(self) -> None:
        with temp_workspace() as tmp:
            root = Path(tmp)
            (root / "a.md").write_text("TODO: alpha\n", encoding="utf-8")
            (root / "b.txt").write_text("TODO: ignored\n", encoding="utf-8")
            (root / "sub").mkdir()
            (root / "sub" / "c.markdown").write_text("FIXME: beta\n", encoding="utf-8")
            items = scan_paths([root])
            self.assertEqual([i.text for i in items], ["alpha", "beta"])
            self.assertEqual(items[0].kind, "TODO")

    def test_skips_noise_directories(self) -> None:
        with temp_workspace() as tmp:
            root = Path(tmp)
            (root / "node_modules").mkdir()
            (root / "node_modules" / "x.md").write_text("TODO: nope\n", encoding="utf-8")
            (root / "keep.md").write_text("TODO: yes\n", encoding="utf-8")
            items = scan_paths([root])
            self.assertEqual([i.text for i in items], ["yes"])

    def test_exclude_glob(self) -> None:
        with temp_workspace() as tmp:
            root = Path(tmp)
            (root / "CHANGELOG.md").write_text("TODO: skip me\n", encoding="utf-8")
            (root / "README.md").write_text("TODO: keep me\n", encoding="utf-8")
            items = scan_paths([root], exclude=["CHANGELOG.md"])
            self.assertEqual([i.text for i in items], ["keep me"])

    def test_results_sorted(self) -> None:
        with temp_workspace() as tmp:
            root = Path(tmp)
            (root / "z.md").write_text("TODO: zed\n", encoding="utf-8")
            (root / "a.md").write_text("TODO: aye\n", encoding="utf-8")
            items = scan_paths([root])
            self.assertEqual([i.text for i in items], ["aye", "zed"])

    def test_single_file_root(self) -> None:
        with temp_workspace() as tmp:
            target = Path(tmp) / "one.md"
            target.write_text("TODO: solo\n", encoding="utf-8")
            self.assertEqual([i.text for i in scan_paths([target])], ["solo"])

    def test_iter_markdown_files_custom_suffix(self) -> None:
        with temp_workspace() as tmp:
            root = Path(tmp)
            (root / "a.rst").write_text("TODO: x\n", encoding="utf-8")
            found = list(iter_markdown_files([root], suffixes=(".rst",)))
            self.assertEqual([p.name for p in found], ["a.rst"])


class CodeSkippingTests(unittest.TestCase):
    """Markers inside code are examples, not real work items."""

    FENCED = "\n".join(
        [
            "# Docs",
            "",
            "```markdown",
            "TODO: shown as an example",
            "```",
            "",
            "TODO: this one is real",
            "",
            "~~~",
            "FIXME: tilde fence example",
            "~~~",
        ]
    )

    def test_fenced_block_is_skipped(self) -> None:
        items = list(scan_text(self.FENCED, "docs.md"))
        self.assertEqual([item.text for item in items], ["this one is real"])
        self.assertEqual(items[0].line, 7)

    def test_fenced_block_can_be_included(self) -> None:
        items = list(scan_text(self.FENCED, "docs.md", ignore_code=False))
        self.assertEqual(len(items), 3)

    def test_indented_fence_opening(self) -> None:
        text = "  ```\nTODO: example\n  ```\nTODO: real\n"
        items = list(scan_text(text, "a.md"))
        self.assertEqual([item.text for item in items], ["real"])

    def test_unclosed_fence_runs_to_end_of_file(self) -> None:
        text = "```\nTODO: example\nTODO: still example\n"
        self.assertEqual(list(scan_text(text, "a.md")), [])

    def test_inline_code_span_is_skipped(self) -> None:
        text = "Use `TODO: x` to mark work.\nTODO: actual task\n"
        items = list(scan_text(text, "a.md"))
        self.assertEqual([item.text for item in items], ["actual task"])

    def test_inline_code_in_description_is_preserved(self) -> None:
        items = list(scan_text("TODO: call `parse_line` first\n", "a.md"))
        self.assertEqual([item.text for item in items], ["call `parse_line` first"])

    def test_double_backtick_span(self) -> None:
        text = "``TODO: a `tick` inside``\nTODO: real\n"
        items = list(scan_text(text, "a.md"))
        self.assertEqual([item.text for item in items], ["real"])

    def test_task_checkbox_in_fence_is_skipped(self) -> None:
        text = "```\n- [ ] example task\n```\n- [ ] real task\n"
        items = list(scan_text(text, "a.md"))
        self.assertEqual([item.text for item in items], ["real task"])

    def test_fence_lines_keep_line_numbers_aligned(self) -> None:
        masked = mask_code(["```", "TODO: x", "```", "TODO: y"])
        self.assertEqual(len(masked), 4)
        self.assertEqual([len(line) for line in masked], [3, 7, 3, 7])
        self.assertEqual(masked[0].strip(), "")
        self.assertEqual(masked[3], "TODO: y")


class ExcludePatternTests(unittest.TestCase):
    """``--exclude`` accepts plain paths as well as globs."""

    def _tree(self, root: Path) -> None:
        (root / "keep.md").write_text("TODO: keep\n", encoding="utf-8")
        for name in ("vendored", "docs/archive"):
            target = root / name
            target.mkdir(parents=True)
            (target / "old.md").write_text("TODO: old\n", encoding="utf-8")

    def _scanned(self, root: Path, *patterns: str) -> list[str]:
        return [item.text for item in scan_paths([root], exclude=list(patterns))]

    def test_bare_name_excludes_directory_anywhere(self) -> None:
        with temp_workspace() as tmp:
            root = Path(tmp)
            self._tree(root)
            self.assertEqual(self._scanned(root, "vendored"), ["old", "keep"])

    def test_relative_path_excludes_prefix(self) -> None:
        with temp_workspace() as tmp:
            root = Path(tmp)
            self._tree(root)
            self.assertEqual(self._scanned(root, "docs/archive"), ["keep", "old"])

    def test_both_plain_paths_together(self) -> None:
        with temp_workspace() as tmp:
            root = Path(tmp)
            self._tree(root)
            self.assertEqual(self._scanned(root, "vendored", "docs/archive"), ["keep"])

    def test_glob_still_works(self) -> None:
        with temp_workspace() as tmp:
            root = Path(tmp)
            self._tree(root)
            self.assertEqual(
                self._scanned(root, "**/archive/*.md"), ["keep", "old"]
            )

    def test_filename_glob_still_works(self) -> None:
        with temp_workspace() as tmp:
            root = Path(tmp)
            self._tree(root)
            self.assertEqual(self._scanned(root, "keep.md"), ["old", "old"])

    def test_plain_path_does_not_match_substring(self) -> None:
        with temp_workspace() as tmp:
            root = Path(tmp)
            (root / "vendored-notes").mkdir()
            (root / "vendored-notes" / "a.md").write_text("TODO: a\n", encoding="utf-8")
            self.assertEqual(self._scanned(root, "vendored"), ["a"])

    def test_single_file_root_honours_exclude(self) -> None:
        with temp_workspace() as tmp:
            target = Path(tmp) / "one.md"
            target.write_text("TODO: solo\n", encoding="utf-8")
            self.assertEqual(scan_paths([target], exclude=["one.md"]), [])


class DefaultsTests(unittest.TestCase):
    def test_default_kinds_content(self) -> None:
        self.assertEqual(DEFAULT_KINDS, ("TODO", "FIXME", "HACK", "XXX"))

    def test_all_kinds_includes_task(self) -> None:
        self.assertEqual(ALL_KINDS, ("TODO", "FIXME", "HACK", "XXX", "TASK"))


if __name__ == "__main__":
    unittest.main()
