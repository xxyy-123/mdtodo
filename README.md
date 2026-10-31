# mdtodo

Collect `TODO` / `FIXME` / `HACK` / `XXX` comments and GitHub-style task-list
checkboxes from Markdown files, then print them as a table, JSON, or a ready to
paste report.

Zero dependencies, Python 3.9+.

## Why

Notes, ADRs and READMEs quietly accumulate `TODO:` lines that nobody ever
reads again. `mdtodo` walks a directory tree, pulls those markers out into one
place, and can group them by owner, tag, or due date so the list is actually
actionable.

## Install

```bash
git clone https://github.com/<you>/mdtodo.git
cd mdtodo
pip install -e .
```

Or run it straight from the checkout without installing:

```bash
python -m mdtodo scan docs/
```

## Usage

```bash
mdtodo scan                    # scan the current directory, table output
mdtodo scan docs/ notes.md     # scan specific paths
mdtodo scan --kind TODO        # only TODO, ignore FIXME/HACK/XXX/TASK
mdtodo scan --tag backend      # only items tagged #backend
mdtodo scan --owner alice      # only items assigned to alice
mdtodo scan --format json      # machine readable
mdtodo stats                   # counts by kind, owner and tag
mdtodo report --output TODO.md # write a Markdown report
```

Exit codes: `0` found something, `1` found nothing, `2` usage error. That makes
it usable as a CI gate — `mdtodo scan --kind FIXME || exit 1` fails the build
when a FIXME sneaks in.

## What it recognises

```markdown
TODO: rewrite the retry loop
FIXME(alice): race condition on shutdown @due(2026-11-15)
HACK: this only works because the API returns sorted keys
XXX: dead code, delete after 2.0

- [ ] add pagination #api #backend
- [x] done item (hidden unless --include-checked)
```

A marker needs a colon (ASCII `:` or full-width `：`), which keeps prose like
"a TODO list" from matching. Owners can be written as `TODO(alice):` or as a
trailing parenthetical, `TODO: fix it (alice)`. Tags are `#word`; due dates are
`@due(YYYY-M-D)` and are normalised to `YYYY-MM-DD`.

## Project layout

| Path | Purpose |
| --- | --- |
| `src/mdtodo/parser.py` | Regexes, `TodoItem`, tree walking |
| `src/mdtodo/formatters.py` | Table / plain / JSON / Markdown renderers |
| `src/mdtodo/cli.py` | `argparse` wiring and exit codes |
| `tests/` | `unittest` suite, no third-party test runner |

## Development

```bash
python -m unittest discover -s tests -v
```

## License

MIT
