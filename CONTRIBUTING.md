# Contributing to mdtodo

Thanks for looking! This is a small project, so the process is short.

## Development setup

```bash
git clone https://github.com/xxyy-123/mdtodo.git
cd mdtodo
pip install -e .
```

No third-party runtime dependencies. `pytest` is an optional convenience listed
under the `dev` extra; the suite itself only needs the standard library.

## Running tests

```bash
python -m unittest discover -s tests -t tests -v
```

The `-t tests` flag matters: the suite imports a local `support` helper, and
that only resolves when `tests/` is the top-level directory.

## Code layout

- `src/mdtodo/parser.py` - regexes, `TodoItem`, directory walking. No I/O beyond
  reading file text.
- `src/mdtodo/formatters.py` - pure functions from `[TodoItem]` to `str`.
- `src/mdtodo/cli.py` - `argparse` wiring, exit codes, no business logic.

If you are adding a new output format, put it in `formatters.py` and keep it a
pure function so it can be tested without touching the filesystem.

## Sending a change

1. Open an issue describing the problem, or comment on an existing one.
2. Fork, branch from `main` (`git switch -c fix/shorter-thing`).
3. Add a test that fails before your change.
4. Make the test pass, run the whole suite.
5. Open a pull request that references the issue (`Closes #12`).

Keep commits scoped to one idea. Squashing on merge is fine.

## Style

- Python 3.9+ syntax; `from __future__ import annotations` at the top of every
  module so the modern type hints stay valid.
- Type hints on every public function.
- No new runtime dependencies without discussing it in an issue first.
- Line length 100.

## Reporting bugs

Include the `mdtodo version` output, the exact command you ran, the Markdown
snippet that misbehaved, and what you expected instead.
