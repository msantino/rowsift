"""XLSX and XLS: cells, sheets, merged areas and the excel extra."""

import io
import sys
import zipfile
from typing import Any

import pytest

from rowsift import ReadLimits, read
from rowsift.errors import (
    LimitExceededError,
    MissingExtraError,
    UnsupportedFileError,
)
from rowsift.types import ErrorCode, FileFormat, ReadNote
from tests.read_helpers import fixture

openpyxl = pytest.importorskip("openpyxl")
pytest.importorskip("xlrd")


def test_numeric_cell_holding_a_phone_number() -> None:
    table = read(fixture("workbook_cells", "phone_as_number.xlsx"))
    assert table.rows[1] == ("11999990001",)


def test_formula_cell() -> None:
    table = read(fixture("workbook_cells", "types.xlsx"))
    assert table.rows[1][6] == "Ana Silva"
    assert table.rows[2][6] == "Bruno Costa"


def test_a_formula_is_never_evaluated() -> None:
    # The stored result of A2&" "&"Silva" is what the file says. The reader gives it back.
    table = read(fixture("workbook_cells", "types.xlsx"))
    assert "&" not in table.rows[1][6]


def test_dates_numbers_and_booleans_become_stable_text() -> None:
    table = read(fixture("workbook_cells", "types.xlsx"))
    assert table.rows[1][2:6] == ("2024-03-15", "2024-03-15T13:45:30", "true", "7.5")
    assert table.rows[2][2:6] == ("2023-12-01", "08:00:00", "false", "3")


def test_a_sheet_dimension_that_reaches_far_past_the_data_is_ignored() -> None:
    table = read(fixture("workbook_cells", "huge_dimension_small_data.xlsx"))
    assert table.rows == (("a", "b"), ("1", "2"))


def test_a_sheet_dimension_that_understates_the_data_is_ignored() -> None:
    table = read(fixture("workbook_cells", "wrong_dimension.xlsx"))
    assert table.rows == (("a", "b"), ("1", "2"), ("3", "4"))


def test_data_on_the_second_sheet() -> None:
    table = read(fixture("sheets", "empty_first_sheet.xlsx"))
    assert table.report.sheet == "People"
    assert table.report.sheets == ("Cover", "People")


def test_a_sheet_chosen_by_name_and_by_index() -> None:
    data = fixture("sheets", "choose_by_name.xlsx")
    assert read(data, sheet="Other").report.sheet == "Other"
    assert read(data, sheet=1).report.sheet == "Other"
    assert read(data, sheet=0).report.sheet == "People"


def test_unknown_sheet() -> None:
    data = fixture("sheets", "choose_by_name.xlsx")
    with pytest.raises(UnsupportedFileError) as caught:
        read(data, sheet="Missing")
    assert caught.value.code is ErrorCode.SHEET_NOT_FOUND
    with pytest.raises(UnsupportedFileError) as by_index:
        read(data, sheet=5)
    assert by_index.value.code is ErrorCode.SHEET_NOT_FOUND


def test_a_text_file_has_no_sheets_to_choose() -> None:
    with pytest.raises(UnsupportedFileError) as caught:
        read(b"a;b\n", sheet=0)
    assert caught.value.code is ErrorCode.SHEET_NOT_FOUND


def test_a_workbook_with_only_empty_sheets_reports_the_first() -> None:
    table = read(fixture("sheets", "all_sheets_empty.xlsx"))
    assert table.rows == ()
    assert table.report.sheet == "One"
    assert table.report.sheets == ("One", "Two")


def test_vertically_merged_group_label() -> None:
    table = read(fixture("merged", "vertical_group_label.xlsx"))
    assert [row[0] for row in table.rows[1:4]] == ["North", "North", "North"]
    assert table.rows[4][0] == "South"
    assert table.report.notes == (ReadNote.MERGED_CELLS_FILLED,)


def test_a_merged_area_never_grows_the_table() -> None:
    table = read(fixture("merged", "area_clipped_to_the_data.xlsx"))
    assert (table.report.row_count, table.report.column_count) == (2, 3)
    assert table.rows[0] == ("Title", "Title", "Title")


def test_the_sheet_part_attribute_the_merge_lookup_relies_on_exists() -> None:
    workbook = openpyxl.load_workbook(
        io.BytesIO(fixture("merged", "vertical_group_label.xlsx")), read_only=True
    )
    worksheet: Any = workbook.worksheets[0]
    assert str(worksheet._worksheet_path).endswith("sheet1.xml")
    workbook.close()


def test_a_legacy_workbook_is_read_with_the_same_rules() -> None:
    table = read(fixture("workbook_cells", "types_legacy.xls"))
    assert table.report.format is FileFormat.XLS
    assert table.rows[1][1:6] == ("11999990001", "2024-03-15", "2024-03-15T13:45:30", "true", "7.5")
    assert table.rows[2][3] == "08:05:00"
    assert [row[0] for row in table.rows[3:]] == ["North", "North", "North"]
    assert table.report.notes == (ReadNote.MERGED_CELLS_FILLED,)


def test_a_legacy_duration_keeps_its_hours() -> None:
    table = read(fixture("workbook_cells", "duration_legacy.xls"))
    assert [row[0] for row in table.rows[1:]] == ["37:45:30", "08:05:00", "2024-03-15T13:45:30"]


def test_a_legacy_workbook_with_data_on_the_second_sheet() -> None:
    table = read(fixture("sheets", "empty_first_sheet_legacy.xls"))
    assert table.report.sheet == "Data"
    assert table.report.sheets == ("Cover", "Data")
    assert table.report.encoding is None


def test_a_legacy_workbook_with_an_unknown_sheet() -> None:
    with pytest.raises(UnsupportedFileError) as caught:
        read(fixture("sheets", "empty_first_sheet_legacy.xls"), sheet="Missing")
    assert caught.value.code is ErrorCode.SHEET_NOT_FOUND


def test_a_compound_file_that_is_no_workbook_is_unsupported() -> None:
    with pytest.raises(UnsupportedFileError):
        read(bytes.fromhex("d0cf11e0a1b11ae1") + b"\x00" * 600)


def test_a_workbook_part_that_is_not_xml_is_unsupported() -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("xl/workbook.xml", "not xml at all")
    with pytest.raises(UnsupportedFileError) as caught:
        read(buffer.getvalue())
    assert str(caught.value) == "unsupported_file"


def test_workbook_without_the_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "openpyxl", None)
    with pytest.raises(MissingExtraError) as caught:
        read(fixture("workbook_cells", "types.xlsx"))
    assert caught.value.extra == "excel"


def test_legacy_workbook_without_the_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "xlrd", None)
    with pytest.raises(MissingExtraError) as caught:
        read(fixture("workbook_cells", "types_legacy.xls"))
    assert caught.value.extra == "excel"


def test_text_needs_no_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "openpyxl", None)
    monkeypatch.setitem(sys.modules, "xlrd", None)
    assert read(b"a;b\n").rows == (("a", "b"),)


def test_compressed_workbook_that_expands_beyond_the_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = fixture("limits", "declares_two_gigabytes.xlsx")
    assert len(data) < 5_000

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("a part was expanded")

    monkeypatch.setattr(zipfile.ZipFile, "open", forbidden)
    monkeypatch.setattr(zipfile.ZipFile, "read", forbidden)
    # Without the parser importable, only the guard can raise this error.
    monkeypatch.setitem(sys.modules, "openpyxl", None)
    with pytest.raises(LimitExceededError) as caught:
        read(data)
    assert caught.value.limit == "max_decompressed_bytes"
    assert caught.value.allowed == 100 * 1024 * 1024


def test_the_decompression_limit_is_a_parameter() -> None:
    data = fixture("workbook_cells", "types.xlsx")
    with pytest.raises(LimitExceededError) as caught:
        read(data, limits=ReadLimits(max_decompressed_bytes=100))
    assert caught.value.limit == "max_decompressed_bytes"


def _workbook(rows: list[list[str]]) -> bytes:
    book = openpyxl.Workbook(write_only=True)
    sheet = book.create_sheet("Data")
    for row in rows:
        sheet.append(row)
    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()


def test_too_many_rows_in_a_workbook() -> None:
    data = _workbook([["x"]] * 11)
    with pytest.raises(LimitExceededError) as caught:
        read(data, limits=ReadLimits(max_rows=10))
    assert caught.value.limit == "max_rows"
    assert len(read(data, limits=ReadLimits(max_rows=11)).rows) == 11


def test_too_many_columns_in_a_workbook() -> None:
    data = _workbook([["a", "b", "c"]])
    with pytest.raises(LimitExceededError) as caught:
        read(data, limits=ReadLimits(max_columns=2))
    assert caught.value.limit == "max_columns"


def test_a_cell_that_is_too_long_in_a_workbook() -> None:
    data = _workbook([["a" * 11]])
    with pytest.raises(LimitExceededError) as caught:
        read(data, limits=ReadLimits(max_cell_chars=10))
    assert caught.value.limit == "max_cell_chars"


def test_too_many_rows_in_a_legacy_workbook() -> None:
    with pytest.raises(LimitExceededError) as caught:
        read(fixture("workbook_cells", "types_legacy.xls"), limits=ReadLimits(max_rows=2))
    assert caught.value.limit == "max_rows"


@pytest.mark.parametrize("error", [MemoryError, RecursionError])
def test_a_resource_failure_is_not_reported_as_an_unsupported_file(
    monkeypatch: pytest.MonkeyPatch, error: type[BaseException]
) -> None:
    openpyxl = pytest.importorskip("openpyxl")
    xlrd = pytest.importorskip("xlrd")

    def fail(*args: object, **kwargs: object) -> None:
        raise error

    data_xlsx = fixture("workbook_cells", "types.xlsx")
    data_xls = fixture("workbook_cells", "types_legacy.xls")
    monkeypatch.setattr(openpyxl, "load_workbook", fail)
    with pytest.raises(error):
        read(data_xlsx)
    monkeypatch.setattr(xlrd, "open_workbook", fail)
    with pytest.raises(error):
        read(data_xls)
