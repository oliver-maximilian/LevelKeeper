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

# set the next version in pyproject.toml, commit it and tag it (`just bump-version push` also pushes)
[no-cd]
bump-version push="":
    #!/usr/bin/env bash
    set -euo pipefail
    if ! git diff --quiet || ! git diff --cached --quiet; then
        echo "working tree not clean, commit or stash first" >&2
        exit 1
    fi
    VERSION="$(git cliff --bumped-version 2>/dev/null)"
    sed -i.bak -E "s/^version = \".*\"/version = \"${VERSION#v}\"/" pyproject.toml
    rm pyproject.toml.bak
    git add pyproject.toml
    git commit -m "chore(release): ${VERSION#v}"
    git tag -m "$VERSION" "$VERSION"
    git log -1 --oneline

    if [[ "{{push}}" = "push" ]]; then
        git push origin main "$VERSION"
    fi

# print the upcoming changelog (stdout only)
changelog:
    git cliff --unreleased --bump
