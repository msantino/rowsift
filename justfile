# rowsift
#
# `just verify` is the only gate: CI runs exactly this recipe.

set shell := ["bash", "-euo", "pipefail", "-c"]

_default:
    @just --list

# Install the project and its development tools into .venv.
setup:
    uv sync

# Lint, format check, type check, tests, text check and package build.
verify: lint typecheck test test-core check-text build

# Ruff lint and format check.
lint:
    uv run ruff check .
    uv run ruff format --check .

# Apply the formatter and the safe lint fixes.
fmt:
    uv run ruff format .
    uv run ruff check --fix .

# Strict mypy over src and tests.
typecheck:
    uv run mypy

# Run the test suite. Extra arguments go to pytest: `just test -k header`.
test *args:
    uv run pytest {{args}}

# Run the test suite in a separate environment with no optional dependency, so
# the tests that need an extra are skipped and everything else is proven to work
# on the core alone. The documented examples run there too.
test-core *args:
    #!/usr/bin/env bash
    set -euo pipefail
    export UV_PROJECT_ENVIRONMENT=.venv-core
    uv sync --quiet --no-install-package openpyxl --no-install-package xlrd \
        --no-install-package phonenumbers --no-install-package types-openpyxl
    uv run --no-sync pytest {{args}}

# No em dash in any tracked text file.
check-text:
    uv run python scripts/check_text.py

# Build the sdist and the wheel into dist/.
build:
    rm -rf dist
    uv build

# Install the built wheel alone into a clean environment and run the pipeline on a CSV.
smoke-core: build
    #!/usr/bin/env bash
    set -euo pipefail
    work="$(mktemp -d)"; trap 'rm -rf "$work"' EXIT
    uv venv --quiet "$work/venv"
    wheel="$(ls dist/*.whl)"
    uv pip install --quiet --python "$work/venv/bin/python" "$wheel"
    "$work/venv/bin/python" -I scripts/smoke_install.py core

# Install the built wheel with every extra into a clean environment and use them.
smoke-extras: build
    #!/usr/bin/env bash
    set -euo pipefail
    work="$(mktemp -d)"; trap 'rm -rf "$work"' EXIT
    uv venv --quiet "$work/venv"
    wheel="$(ls dist/*.whl)"
    uv pip install --quiet --python "$work/venv/bin/python" "$PWD/$wheel[all]"
    "$work/venv/bin/python" -I scripts/smoke_install.py extras
