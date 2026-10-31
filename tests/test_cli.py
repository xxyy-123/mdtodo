"""Tests for :mod:`mdtodo.cli`."""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import unittest
from pathlib import Path

from support import temp_workspace

from mdtodo.cli import EXIT_NO_ITEMS, EXIT_OK, EXIT_USAGE, build_parser, main


def run_cli(*argv: str) -> tuple[int, str, str]:
    """Invoke ``main`` and capture its streams."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


class CliTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._ctx = temp_workspace()
        self.root = Path(self._ctx.__enter__())
        (self.root / "notes.md").write_text(
            "# Notes\n\nTODO: first thing #docs\nFIXME(bob): second thing\n- [ ] third thing #api\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self._ctx.__exit__(None, None, None)


class ScanCommandTests(CliTestCase):
    def test_table_output(self) -> None:
        code, out, _ = run_cli("scan", str(self.root))
        self.assertEqual(code, EXIT_OK)
        self.assertIn("TODO", out)
        self.assertIn("first thing", out)

    def test_plain_output(self) -> None:
        code, out, _ = run_cli("scan", str(self.root), "--format", "plain")
        self.assertEqual(code, EXIT_OK)
        self.assertIn("[TODO]", out)
        self.assertEqual(len(out.strip().splitlines()), 3)

    def test_json_output_is_parseable(self) -> None:
        code, out, _ = run_cli("scan", str(self.root), "--format", "json")
        self.assertEqual(code, EXIT_OK)
        payload = json.loads(out)
        self.assertEqual(len(payload), 3)
        self.assertEqual(payload[0]["kind"], "TODO")

    def test_markdown_output(self) -> None:
        code, out, _ = run_cli("scan", str(self.root), "--format", "markdown")
        self.assertEqual(code, EXIT_OK)
        self.assertTrue(out.startswith("# TODO report"))

    def test_kind_filter(self) -> None:
        code, out, _ = run_cli("scan", str(self.root), "--format", "json", "--kind", "TODO")
        self.assertEqual(code, EXIT_OK)
        payload = json.loads(out)
        self.assertEqual([item["kind"] for item in payload], ["TODO"])

    def test_tag_filter(self) -> None:
        code, out, _ = run_cli("scan", str(self.root), "--format", "json", "--tag", "api")
        self.assertEqual(code, EXIT_OK)
        payload = json.loads(out)
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["kind"], "TASK")

    def test_owner_filter(self) -> None:
        code, out, _ = run_cli("scan", str(self.root), "--format", "json", "--owner", "BOB")
        self.assertEqual(code, EXIT_OK)
        payload = json.loads(out)
        self.assertEqual([item["owner"] for item in payload], ["bob"])

    def test_no_match_exit_code(self) -> None:
        code, _, _ = run_cli("scan", str(self.root), "--kind", "XXX")
        self.assertEqual(code, EXIT_NO_ITEMS)

    def test_empty_directory(self) -> None:
        with temp_workspace() as empty:
            code, out, _ = run_cli("scan", empty)
            self.assertEqual(code, EXIT_NO_ITEMS)
            self.assertIn("No items found.", out)

    def test_truncation_flag(self) -> None:
        code, out, _ = run_cli("scan", str(self.root), "--max-text", "5")
        self.assertEqual(code, EXIT_OK)
        self.assertIn("...", out)

    def test_include_checked(self) -> None:
        (self.root / "done.md").write_text("- [x] finished\n", encoding="utf-8")
        code, out, _ = run_cli("scan", str(self.root), "--format", "json")
        self.assertEqual(code, EXIT_OK)
        before = len(json.loads(out))
        code, out, _ = run_cli(
            "scan", str(self.root), "--format", "json", "--include-checked"
        )
        self.assertEqual(len(json.loads(out)), before + 1)


class StatsCommandTests(CliTestCase):
    def test_text_output(self) -> None:
        code, out, _ = run_cli("stats", str(self.root))
        self.assertEqual(code, EXIT_OK)
        self.assertIn("Total items   : 3", out)
        self.assertIn("Files scanned : 1", out)

    def test_json_output(self) -> None:
        code, out, _ = run_cli("stats", str(self.root), "--format", "json")
        self.assertEqual(code, EXIT_OK)
        payload = json.loads(out)
        self.assertEqual(payload["total"], 3)
        self.assertEqual(payload["by_kind"]["TODO"], 1)


class ReportCommandTests(CliTestCase):
    def test_stdout(self) -> None:
        code, out, _ = run_cli("report", str(self.root), "--title", "Sprint 1")
        self.assertEqual(code, EXIT_OK)
        self.assertIn("# Sprint 1", out)

    def test_output_file(self) -> None:
        target = self.root / "OUT.md"
        code, out, _ = run_cli("report", str(self.root), "--output", str(target))
        self.assertEqual(code, EXIT_OK)
        self.assertTrue(target.exists())
        self.assertIn("# TODO report", target.read_text(encoding="utf-8"))
        self.assertIn("Wrote 3 item(s)", out)


class MetaTests(CliTestCase):
    def test_no_command_prints_help(self) -> None:
        code, out, _ = run_cli()
        self.assertEqual(code, EXIT_USAGE)
        self.assertIn("COMMAND", out)

    def test_version_command(self) -> None:
        code, out, _ = run_cli("version")
        self.assertEqual(code, EXIT_OK)
        self.assertIn("mdtodo 0.1.0", out)

    def test_bad_option_exits_two(self) -> None:
        with self.assertRaises(SystemExit) as ctx:
            with contextlib.redirect_stderr(io.StringIO()):
                main(["scan", "--format", "nope"])
        self.assertEqual(ctx.exception.code, 2)

    def test_parser_has_subcommands(self) -> None:
        parser = build_parser()
        subparsers = [
            action
            for action in parser._actions
            if action.__class__.__name__ == "_SubParsersAction"
        ]
        self.assertEqual(len(subparsers), 1)
        self.assertEqual(
            set(subparsers[0].choices), {"scan", "stats", "report", "version"}
        )


if __name__ == "__main__":
    unittest.main()

