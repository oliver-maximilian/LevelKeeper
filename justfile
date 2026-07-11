default:
    @just --list

# create a virtualenv and install the project with dev dependencies
init:
    python3 -m venv .venv
    .venv/bin/pip install -e ".[dev]"

# start levelkeeper via docker compose (internal scheduler)
run:
    docker compose up -d

# run the test suite
test:
    .venv/bin/pytest

# format the codebase
format:
    .venv/bin/ruff format .

# lint the codebase
lint:
    .venv/bin/ruff check .

# preview the changelog; push=true tags HEAD and pushes only the tag (release workflow does the rest)
changelog push="false":
    git cliff --config cliff.toml --bump -o CHANGELOG.md
    if [ "{{ push }}" = "true" ]; then
    version=$(git cliff --config cliff.toml --bumped-version)
    git tag "$version"
    git push origin "$version"
    echo "pushed tag $version"
    fi
