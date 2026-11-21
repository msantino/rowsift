"""The public API is explicit, typed and free of dependencies."""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
import tomllib
from pathlib import Path
from types import ModuleType

import pytest

import rowsift
from rowsift import errors, types

ROOT = Path(__file__).resolve().parents[1]
LAYERS = ("read", "profile", "clean", "map", "sift")


def test_top_level_entry_points() -> None:
    from rowsift import (  # noqa: F401  # the import is the assertion
        Confidence,
        Field,
        Kind,
        apply_saved,
        profile,
        read,
        sift,
        suggest,
    )


@pytest.mark.parametrize("layer", LAYERS)
def test_every_exported_name_of_a_layer_exists(layer: str) -> None:
    module = importlib.import_module(f"rowsift.{layer}")
    assert module.__all__
    for name in module.__all__:
        assert hasattr(module, name)


@pytest.mark.parametrize("module", [errors, types], ids=["errors", "types"])
def test_every_public_name_of_the_shared_modules_is_exported_at_the_top(
    module: ModuleType,
) -> None:
    for name in module.__all__:
        assert name in rowsift.__all__


def test_the_typing_marker_ships() -> None:
    assert (Path(rowsift.__file__).parent / "py.typed").is_file()


def test_catching_everything_with_rowsift_error() -> None:
    raised = [
        errors.UnsupportedFileError(),
        errors.LimitExceededError("max_rows", 1),
        errors.DecodingError(),
        errors.MissingExtraError("excel"),
    ]
    for error in raised:
        with pytest.raises(rowsift.RowsiftError) as caught:
            raise error
        assert isinstance(caught.value.code, rowsift.ErrorCode)
        assert str(caught.value).startswith(caught.value.code.value)


def test_error_messages_carry_no_cell_contents() -> None:
    # Constructors take names and numbers only, so a cell value cannot reach a message.
    assert str(errors.LimitExceededError("max_rows", 1)) == "limit_exceeded: max_rows (allowed 1)"
    assert str(errors.MissingExtraError("excel")) == "missing_extra: install rowsift[excel]"


def test_core_only_declares_no_runtime_dependency_and_offers_the_extras() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert project["dependencies"] == []
    extras = project["optional-dependencies"]
    assert set(extras) == {"excel", "phone", "all"}
    assert set(extras["all"]) == set(extras["excel"]) | set(extras["phone"])


def test_importing_the_package_loads_no_optional_dependency() -> None:
    probe = (
        "import json, sys\n"
        "import rowsift\n"
        "optional = ('openpyxl', 'xlrd', 'phonenumbers')\n"
        "print(json.dumps(sorted(m for m in optional if m in sys.modules)))\n"
    )
    out = subprocess.run(
        [sys.executable, "-I", "-c", probe], check=True, capture_output=True, text=True
    ).stdout
    assert json.loads(out) == []


def test_the_pipeline_reads_profiles_maps_and_sifts_a_csv_for_region_br() -> None:
    # A pipeline check. That the core works with nothing else installed is proven
    # by `just smoke-core`, which runs in a clean environment.
    table = rowsift.read(b"Nome;Celular\nana souza;(11) 91234-5678\n")
    profile = rowsift.profile(table)
    fields = [
        rowsift.Field("name", rowsift.Kind.NAME, required=True),
        rowsift.Field("phone", rowsift.Kind.PHONE, aliases=("Celular",)),
    ]
    mapping = rowsift.suggest(profile, fields)
    result = rowsift.sift(
        table, profile, mapping, fields, options=rowsift.CleanOptions(region="BR")
    )
    assert result.summary.kept == 1
    assert result.rows[0].values["phone"] == "+5511912345678"
