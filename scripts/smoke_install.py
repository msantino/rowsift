"""Exercise an installed rowsift from outside the source tree.

Usage: smoke_install.py core|extras

``core`` runs in an environment with only the wheel installed: the pipeline
works on a CSV, and the optional dependencies are absent, so a workbook and a
phone number of another region raise ``MissingExtraError``. ``extras`` runs
where ``rowsift[all]`` is installed: a workbook is read and a phone number of
another region is cleaned, both through the real libraries.
"""

from __future__ import annotations

import importlib.util
import io
import sys
import zipfile
from collections.abc import Callable

import rowsift
from rowsift import CleanOptions, Field, Kind, MissingExtraError, clean

CSV = b"Nome;Celular\nana souza;(11) 91234-5678\n"


def _pipeline() -> None:
    table = rowsift.read(CSV)
    profile = rowsift.profile(table)
    fields = [
        Field("name", Kind.NAME, required=True),
        Field("phone", Kind.PHONE, aliases=("Celular",)),
    ]
    mapping = rowsift.suggest(profile, fields)
    result = rowsift.sift(table, profile, mapping, fields, options=CleanOptions(region="BR"))
    assert result.summary.kept == 1, result.summary
    assert result.rows[0].values["phone"] == "+5511912345678"


def _workbook_bytes() -> bytes:
    """The smallest archive that passes for a workbook, enough to reach the extra check."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("xl/workbook.xml", "<workbook/>")
    return buffer.getvalue()


def _minimal_xlsx() -> bytes:
    """A real one-sheet workbook holding two rows, written with openpyxl."""
    import openpyxl

    book = openpyxl.Workbook()
    sheet = book.active
    assert sheet is not None
    sheet.append(["Name", "Phone"])
    sheet.append(["Ana Souza", "2125550123"])
    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()


def _missing_extra(call: Callable[[], object]) -> str:
    """The extra named by the ``MissingExtraError`` the call raises."""
    try:
        call()
    except MissingExtraError as error:
        return error.extra
    raise AssertionError("the call did not need an extra")


def _core() -> None:
    for name in ("openpyxl", "xlrd", "phonenumbers"):
        assert importlib.util.find_spec(name) is None, f"{name} is installed in the core check"
    _pipeline()
    assert _missing_extra(lambda: rowsift.read(_workbook_bytes())) == "excel"
    assert _missing_extra(lambda: clean.phone("2125550123", CleanOptions(region="US"))) == "phone"


def _extras() -> None:
    for name in ("openpyxl", "xlrd", "phonenumbers"):
        assert importlib.util.find_spec(name) is not None, f"{name} is missing"
    _pipeline()
    cleaned = clean.phone("(212) 555-0123", CleanOptions(region="US"))
    assert cleaned.value == "+12125550123", cleaned
    assert cleaned.issue is None, cleaned
    table = rowsift.read(_minimal_xlsx())
    assert [list(row) for row in table.rows[:2]] == [["Name", "Phone"], ["Ana Souza", "2125550123"]]


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in ("core", "extras"):
        print("usage: smoke_install.py core|extras", file=sys.stderr)
        return 2
    {"core": _core, "extras": _extras}[argv[1]]()
    print(f"rowsift {rowsift.__version__}: {argv[1]} install ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
