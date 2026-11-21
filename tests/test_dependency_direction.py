"""The layers form one direction: a layer never imports one to its right.

types <- errors <- clean <- profile <- map <- sift, and read depends only on
types and errors. The package root re-exports everything and is exempt.
"""

import ast
from pathlib import Path

import pytest

import rowsift

# Layer name to the layers it may import. Layers not listed here do not exist yet.
ALLOWED: dict[str, frozenset[str]] = {
    "types": frozenset(),
    "errors": frozenset({"types"}),
    "read": frozenset({"types", "errors"}),
    "clean": frozenset({"types", "errors"}),
    "profile": frozenset({"types", "errors", "clean"}),
    "map": frozenset({"types", "errors", "clean", "profile"}),
    "sift": frozenset({"types", "errors", "clean", "profile", "map"}),
}


def layer_of(relative: Path) -> str | None:
    """The layer a path inside the package belongs to, or None for the root."""
    parts = relative.with_suffix("").parts
    if parts == ("__init__",):
        return None
    return parts[0]


def imported_layers(source: str, relative: Path = Path("x.py")) -> set[str]:
    """Layers of the package that a module's source imports.

    ``relative`` is the module's path inside the package, used to resolve
    relative imports.
    """
    package = list(relative.with_suffix("").parts[:-1])
    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                parts = alias.name.split(".")
                if parts[0] == "rowsift" and len(parts) > 1:
                    found.add(parts[1])
        elif isinstance(node, ast.ImportFrom) and node.level > 0:
            if node.level - 1 > len(package):
                continue  # climbs above the package: not ours to judge
            base = package[: len(package) - (node.level - 1)]
            parts = ["rowsift", *base, *(node.module.split(".") if node.module else [])]
            if len(parts) > 1:
                found.add(parts[1])
            else:
                found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            parts = node.module.split(".")
            if parts[0] != "rowsift":
                continue
            if len(parts) > 1:
                found.add(parts[1])
            else:
                found.update(alias.name for alias in node.names)
    return found


def violations(sources: dict[Path, str]) -> list[str]:
    """Describe every import that points to a layer a module may not use."""
    problems: list[str] = []
    for relative, source in sorted(sources.items()):
        layer = layer_of(relative)
        if layer is None:
            continue
        if layer not in ALLOWED:
            problems.append(f"{relative}: unknown layer {layer!r}, add it to ALLOWED")
            continue
        for target in sorted(imported_layers(source, relative) - {layer}):
            if target not in ALLOWED[layer]:
                problems.append(f"{relative}: {layer} must not import {target}")
    return problems


def test_the_package_respects_the_dependency_direction() -> None:
    root = Path(rowsift.__file__).parent
    sources = {path.relative_to(root): path.read_text() for path in root.rglob("*.py")}
    assert violations(sources) == []


@pytest.mark.parametrize(
    ("path", "source", "expected"),
    [
        ("types.py", "from rowsift.errors import RowsiftError", "types must not import errors"),
        ("clean/phone.py", "from rowsift.profile import x", "clean must not import profile"),
        ("read/csv.py", "import rowsift.clean", "read must not import clean"),
        ("profile/run.py", "from rowsift import map", "profile must not import map"),
        ("clean/phone.py", "from ..profile import x", "clean must not import profile"),
        ("clean/phone.py", "from .. import profile", "clean must not import profile"),
        ("read/csv.py", "from ..clean.dates import y", "read must not import clean"),
        ("map/suggest.py", "from rowsift.sift import sift", "map must not import sift"),
    ],
)
def test_a_wrong_way_import_is_reported(path: str, source: str, expected: str) -> None:
    assert any(expected in line for line in violations({Path(path): source}))


def test_imports_to_the_left_and_inside_a_layer_are_allowed() -> None:
    sources = {
        Path("profile/run.py"): "from rowsift.clean import value\nfrom rowsift.types import Kind",
        Path("clean/phone.py"): "from rowsift.clean import dates\nfrom rowsift.errors import X",
        Path("__init__.py"): "from rowsift.sift import sift",
        Path("profile/other.py"): "from ..clean import value\nfrom . import helpers",
    }
    assert violations(sources) == []


def test_a_module_in_an_unknown_layer_is_reported() -> None:
    assert violations({Path("extras/x.py"): "import os"}) == [
        "extras/x.py: unknown layer 'extras', add it to ALLOWED"
    ]
