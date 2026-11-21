"""The public documentation is held to the code: every example runs, every name exists."""

from __future__ import annotations

import importlib
import re
from enum import StrEnum
from pathlib import Path

import pytest

import rowsift
from rowsift import (
    ChangeCode,
    Confidence,
    ErrorCode,
    FileFormat,
    IssueCode,
    Kind,
    LineType,
    ReadNote,
    ReasonCode,
    SkipCode,
)

ROOT = Path(__file__).resolve().parents[1]
PAGES = [ROOT / "README.md", *sorted((ROOT / "docs").glob("*.md"))]
FENCE = re.compile(r"^```python\n(.*?)^```$", re.DOTALL | re.MULTILINE)
DOTTED = re.compile(r"`(rowsift(?:\.[A-Za-z_][A-Za-z0-9_]*)+)`")
CODE_ENUMS: tuple[type[StrEnum], ...] = (
    ChangeCode,
    IssueCode,
    ReasonCode,
    SkipCode,
    ReadNote,
    ErrorCode,
    Kind,
    Confidence,
    FileFormat,
    LineType,
)


def _examples() -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for page in PAGES:
        for number, match in enumerate(FENCE.finditer(page.read_text(encoding="utf-8")), 1):
            found.append((f"{page.name}#{number}", match.group(1)))
    return found


EXAMPLES = _examples()


def test_the_documentation_pages_exist() -> None:
    names = {page.name for page in PAGES}
    assert {
        "README.md",
        "quick-start.md",
        "reading.md",
        "profiling.md",
        "cleaning.md",
        "mapping.md",
        "sifting.md",
        "codes.md",
    } <= names


@pytest.mark.parametrize(("label", "source"), EXAMPLES, ids=[label for label, _ in EXAMPLES])
def test_every_documented_example_runs(label: str, source: str) -> None:
    # `just test-core` runs this with no optional dependency installed: an
    # example that needs an extra must say so on its page, not fail there.
    exec(compile(source, label, "exec"), {"__name__": "documented_example"})


@pytest.mark.parametrize("page", PAGES, ids=[page.name for page in PAGES])
def test_every_documented_name_exists(page: Path) -> None:
    for dotted in DOTTED.findall(page.read_text(encoding="utf-8")):
        parts = dotted.split(".")
        target: object = importlib.import_module(parts[0])
        for part in parts[1:]:
            target = getattr(target, part)


def _sections(text: str) -> dict[str, set[str]]:
    sections: dict[str, set[str]] = {}
    current: set[str] | None = None
    for line in text.splitlines():
        heading = re.match(r"^## `(\w+)`", line)
        if heading:
            current = sections.setdefault(heading.group(1), set())
            continue
        if line.startswith("## "):
            current = None
            continue
        row = re.match(r"^\| `([^`]+)` \|", line)
        if row and current is not None:
            current.add(row.group(1))
    return sections


@pytest.mark.parametrize("enum", CODE_ENUMS, ids=[enum.__name__ for enum in CODE_ENUMS])
def test_the_codes_page_lists_every_code_and_only_those(enum: type[StrEnum]) -> None:
    sections = _sections((ROOT / "docs" / "codes.md").read_text(encoding="utf-8"))
    assert sections[enum.__name__] == {member.value for member in enum}


def test_every_exception_is_on_the_codes_page() -> None:
    text = (ROOT / "docs" / "codes.md").read_text(encoding="utf-8")
    for name in (
        "RowsiftError",
        "UnsupportedFileError",
        "LimitExceededError",
        "MissingExtraError",
        "DecodingError",
    ):
        assert f"`{name}`" in text


def test_the_public_names_are_all_exported() -> None:
    assert len(set(rowsift.__all__)) == len(rowsift.__all__)
    for name in rowsift.__all__:
        assert hasattr(rowsift, name)
