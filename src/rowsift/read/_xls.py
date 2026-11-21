"""XLS workbooks, read with the ``excel`` extra."""

from __future__ import annotations

import datetime
import io
import re
from collections.abc import Iterator
from typing import Any

from rowsift.errors import MissingExtraError, RowsiftError, UnsupportedFileError
from rowsift.read._cells import cell_text
from rowsift.read._grid import Grid, RowCollector, fill_merged, select_sheets
from rowsift.read._limits import ReadLimits
from rowsift.read._workbook import WorkbookResult

__all__ = ["read_xls"]


_QUOTED = re.compile(r'"[^"]*"|\\.|\[(?![hms])[^\]]*\]', re.IGNORECASE)


def _is_time_only(book: Any, cell: Any) -> bool:
    """Whether the number format of a date cell shows hours, minutes or seconds only."""
    try:
        xf = book.xf_list[cell.xf_index]
        pattern: str = book.format_map[xf.format_key].format_str
    except (AttributeError, IndexError, KeyError):
        return False
    shown = _QUOTED.sub("", pattern).lower()
    return not any(letter in shown for letter in "yd") and "mmm" not in shown


def _cell_value(xlrd: Any, book: Any, cell: Any) -> object:
    kind = cell.ctype
    if kind == xlrd.XL_CELL_DATE:
        value: float = cell.value
        if value >= 1 and _is_time_only(book, cell):
            # A duration such as [h]:mm:ss: the serial counts days, not a date.
            return datetime.timedelta(days=value)
        moment: datetime.datetime = xlrd.xldate.xldate_as_datetime(value, book.datemode)
        # A value below one day is a time of day: the serial has no date part.
        return moment.time() if value < 1 else moment
    if kind == xlrd.XL_CELL_BOOLEAN:
        return bool(cell.value)
    if kind == xlrd.XL_CELL_ERROR:
        return xlrd.error_text_from_code.get(cell.value, "")
    if kind in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK):
        return None
    return cell.value


def _areas(worksheet: Any) -> Iterator[tuple[int, int, int, int]]:
    # xlrd gives bounds as (first row, last row + 1, first column, last column + 1).
    for first_row, end_row, first_col, end_col in worksheet.merged_cells:
        yield first_row, first_col, end_row - 1, end_col - 1


def _rows(xlrd: Any, book: Any, worksheet: Any, limits: ReadLimits) -> Grid:
    collector = RowCollector(limits, trim_trailing_rows=True)
    for row_index in range(worksheet.nrows):
        cells = worksheet.row(row_index)
        collector.add(cell_text(_cell_value(xlrd, book, cell)) for cell in cells)
    return collector.finish()


def read_xls(data: bytes, sheet: str | int | None, limits: ReadLimits) -> WorkbookResult:
    """Read an XLS workbook into a grid of cell text.

    Formulas give the result the file stored and are never evaluated. Merged
    areas repeat the value of their top-left cell, clipped to the data. An
    encrypted workbook is unsupported.

    Raises:
        LimitExceededError: if the rows, the columns or a cell go beyond the limits.
        MissingExtraError: if the ``excel`` extra is not installed.
        UnsupportedFileError: if the workbook cannot be read, or the sheet does
            not exist (``sheet_not_found``).
    """
    try:
        import xlrd
    except ImportError:
        raise MissingExtraError("excel") from None
    try:
        book = xlrd.open_workbook(file_contents=data, formatting_info=True, logfile=io.StringIO())
    except (MemoryError, RecursionError):
        raise
    except Exception:
        raise UnsupportedFileError() from None
    try:
        titles: list[str] = list(book.sheet_names())
        candidates = select_sheets(titles, sheet)
        first_empty: Grid | None = None
        for index in candidates:
            worksheet = book.sheet_by_index(index)
            try:
                grid = _rows(xlrd, book, worksheet, limits)
                if not grid.rows:
                    first_empty = first_empty or grid
                    continue
                changed = fill_merged(grid.rows, _areas(worksheet))
            except RowsiftError:
                raise
            except (MemoryError, RecursionError):
                raise
            except Exception:
                raise UnsupportedFileError() from None
            return WorkbookResult(grid, titles[index], tuple(titles), merged_filled=changed)
        if first_empty is None:
            return WorkbookResult(Grid([], False), None, tuple(titles), merged_filled=False)
        return WorkbookResult(
            first_empty, titles[candidates[0]], tuple(titles), merged_filled=False
        )
    finally:
        book.release_resources()
