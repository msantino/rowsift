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
verify: lint typecheck test check-text build

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

# No em dash in any tracked text file.
check-text:
    uv run python scripts/check_text.py

# Build the sdist and the wheel into dist/.
build:
    uv build
