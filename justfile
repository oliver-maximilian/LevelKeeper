default:
    @just --list

# venv with dev dependencies
init:
    python3 -m venv .venv
    .venv/bin/pip install -e ".[dev]"

# start via docker compose
run:
    docker compose up -d --build

# tests
test:
    .venv/bin/pytest

# format
format:
    .venv/bin/ruff format .

# lint
lint:
    .venv/bin/ruff check .

# tag the next version (git cliff)
[no-cd]
bump-version push="":
    #!/usr/bin/env bash
    export VERSION="$( git cliff --bumped-version )"
    git tag -m "$VERSION" "$VERSION"
    git log HEAD~1..HEAD

    if [[ "{{push}}" = "push" ]]; then
        git push origin $VERSION
    fi

# changelog since the last tag
[no-cd]
changelog:
    git cliff --latest > CHANGELOG.md
