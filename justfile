default:
    @just --list

# create a virtualenv and install the project with dev dependencies
init:
    python3 -m venv .venv
    .venv/bin/pip install -e ".[dev]"

# start levelkeeper via docker compose (internal scheduler)
run:
    docker compose up -d --build

# run the test suite
test:
    .venv/bin/pytest

# format the codebase
format:
    .venv/bin/ruff format .

# lint the codebase
lint:
    .venv/bin/ruff check .

# preview the changelog (stdout only, nothing written/committed); `just changelog true`
# tags HEAD and pushes only the tag - the release workflow generates the changelog
# for GitHub Releases from that tag, it is never committed to the repo
changelog push="false":
    #!/usr/bin/env sh
    set -eu
    git-cliff --config cliff.toml --bump --unreleased
    if [ "{{ push }}" = "true" ]; then
        version=$(git-cliff --config cliff.toml --bumped-version)
        git tag "$version"
        git push origin "$version"
        echo "pushed tag $version"
    fi
