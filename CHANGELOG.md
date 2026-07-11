# Changelog

## [0.1.0] - 2026-07-11

### Bug Fixes

- Make just changelog work with initial tag and shebang recipe


### Build

- Add ruff for linting and formatting

- Add justfile for init, run, test, format, lint, changelog


### CI

- Run pytest on push and pull request

- Check ruff format and lint on push and pull request

- Generate changelog and GitHub release with git-cliff on tag push


### Documentation

- Add README

- Split README into docs/ and tighten paragraph wrapping


### Features

- Add config loading with TOML/ENV support and threshold parsing

- Add IMAP client wrapper with modified UTF-7 decoding

- Add archive storage with atomic write and checksum verification

- Add NAS mount check via marker file

- Add persistent state store for monthly reporting

- Add SMTP notifier and mail templates

- Add lockfile to prevent overlapping runs

- Add core archiver run loop

- Add logging setup, scheduler and CLI entrypoint

- Add Docker packaging and compose setup


### Miscellaneous

- Scaffold python project with pyproject and ignore files


### Styling

- Apply ruff format and lint fixes


### Testing

- Add unit test suite



