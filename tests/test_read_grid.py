import pytest

from rowsift import ReadLimits, read
from rowsift.errors import LimitExceededError, UnsupportedFileError
from rowsift.read._grid import RowCollector, fill_merged, select_sheets
from rowsift.types import ErrorCode, ReadNote
from tests.read_helpers import fixture


def test_ragged_rows() -> None:
    table = read(fixture("grid", "ragged_rows.csv"))
    assert {len(row) for row in table.rows} == {4}
    assert table.rows[1] == ("1", "2", "", "")
    assert table.report.column_count == 4


def test_trailing_columns_that_are_empty_in_every_row_are_dropped_and_noted() -> None:
    table = read(fixture("grid", "trailing_empty_columns.csv"))
    assert table.report.column_count == 2
    assert table.report.notes == (ReadNote.TRAILING_EMPTY_COLUMNS_DROPPED,)


def test_an_empty_file_is_an_empty_table() -> None:
    table = read(b"")
    assert table.rows == ()
    assert table.report.row_count == 0
    assert table.report.column_count == 0


def test_blank_lines_in_text_are_rows_of_empty_cells() -> None:
    table = read(b"a;b\n\n1;2\n")
    assert table.rows == (("a", "b"), ("", ""), ("1", "2"))


def test_the_collector_keeps_inner_empty_rows_and_drops_trailing_ones_on_request() -> None:
    collector = RowCollector(ReadLimits(), trim_trailing_rows=True)
    for row in (["a"], [""], ["b"], [""], [""]):
        collector.add(row)
    assert collector.finish().rows == [["a"], [""], ["b"]]


def test_the_collector_keeps_trailing_empty_rows_otherwise() -> None:
    collector = RowCollector(ReadLimits(), trim_trailing_rows=False)
    for row in (["a"], [""]):
        collector.add(row)
    assert collector.finish().rows == [["a"], [""]]


def test_merged_area_clipped_to_a_grid_that_is_smaller() -> None:
    rows = [["x", ""], ["", ""]]
    assert fill_merged(rows, [(0, 0, 50, 50)]) is True
    assert rows == [["x", "x"], ["x", "x"]]


def test_a_merged_area_with_no_value_changes_nothing() -> None:
    rows = [["", ""]]
    assert fill_merged(rows, [(0, 0, 0, 1)]) is False


def test_merged_areas_that_overlap_beyond_the_grid_are_unsupported() -> None:
    rows = [["x", "y"], ["z", "w"]]
    with pytest.raises(UnsupportedFileError):
        fill_merged(rows, [(0, 0, 1, 1)] * 2)


def test_selecting_a_sheet_by_name_or_index() -> None:
    assert select_sheets(["a", "b"], "b") == [1]
    assert select_sheets(["a", "b"], 0) == [0]
    assert select_sheets(["a", "b"], None) == [0, 1]


@pytest.mark.parametrize("sheet", ["Missing", 2, -1])
def test_an_unknown_sheet_is_sheet_not_found(sheet: str | int) -> None:
    with pytest.raises(UnsupportedFileError) as caught:
        select_sheets(["a", "b"], sheet)
    assert caught.value.code is ErrorCode.SHEET_NOT_FOUND


def test_a_cell_over_the_limit_is_refused_by_the_collector() -> None:
    collector = RowCollector(ReadLimits(max_cell_chars=3), trim_trailing_rows=False)
    with pytest.raises(LimitExceededError) as caught:
        collector.add(["abcd"])
    assert caught.value.limit == "max_cell_chars"
