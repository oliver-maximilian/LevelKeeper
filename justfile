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

# integration tests against a real Dovecot in docker
test-integration:
    #!/usr/bin/env sh
    set -eu
    docker compose -f tests/integration/docker-compose.yml up -d
    trap 'docker compose -f tests/integration/docker-compose.yml down' EXIT
    until nc -z 127.0.0.1 14300; do sleep 1; done
    .venv/bin/pytest tests/integration

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

# print the upcoming changelog (stdout only)
changelog:
    git cliff --unreleased --bump
