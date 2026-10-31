# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0]

### Added

- `--include-code` to scan inside fenced code blocks and inline code spans.
- `--exclude` now accepts plain paths as well as globs: a bare name such as
  `vendored` skips that path component at any depth, `docs/archive` skips that
  prefix relative to the scanned root, and patterns containing `*`, `?` or `[`
  are still matched as globs. Closes
  [#1](https://github.com/xxyy-123/mdtodo/issues/1).
- `py.typed` marker so type checkers pick up the inline annotations.

### Changed

- Fenced code blocks and inline code spans are skipped by default. A Markdown
  file that documents these markers no longer reports its own examples; this
  repository now scans clean.
- Exclusion happens while walking the tree, so skipped directories are never
  read.

## [0.1.0]

### Added

- `scan`, `stats` and `report` subcommands with table, plain, JSON and Markdown
  output, plus filtering by kind, tag and owner.
- Owner (`TODO(alice):` or a trailing parenthetical), tag (`#word`) and due date
  (`@due(YYYY-M-D)`) metadata, with full-width colon support.
- Exit codes `0` / `1` / `2` for use as a CI gate.
- `unittest` suite running on Linux, Windows and macOS via GitHub Actions.
