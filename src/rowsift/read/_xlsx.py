"""XLSX workbooks, read with the ``excel`` extra."""

from __future__ import annotations

import io
import re
import zipfile
from collections.abc import Iterator
from typing import Any

from rowsift.errors import LimitExceededError, MissingExtraError, RowsiftError, UnsupportedFileError
from rowsift.read._cells import cell_text
from rowsift.read._grid import Grid, RowCollector, fill_merged, select_sheets
from rowsift.read._limits import ReadLimits
from rowsift.read._workbook import WorkbookResult

__all__ = ["check_archive", "read_xlsx"]

# `mergeCell` elements sit after the cell data. The attribute holds a cell range.
_MERGE_CELL = re.compile(
    rb'<(?:\w+:)?mergeCell\s[^>]*?\bref="([A-Za-z]+[0-9]+(?::[A-Za-z]+[0-9]+)?)"'
)


def check_archive(data: bytes, limits: ReadLimits) -> None:
    """Refuse an archive whose declared uncompressed size is beyond the limit.

    Only the central directory is read: no part is expanded. The declared size
    also bounds what the ZIP reader gives back for a part, so an archive that
    understates a size cannot expand past it.

    Raises:
        LimitExceededError: with ``max_decompressed_bytes``.
        UnsupportedFileError: if the archive directory cannot be read.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            declared = sum(info.file_size for info in archive.infolist())
    except (zipfile.BadZipFile, OSError, ValueError, NotImplementedError):
        raise UnsupportedFileError() from None
    if declared > limits.max_decompressed_bytes:
        raise LimitExceededError("max_decompressed_bytes", limits.max_decompressed_bytes)


def _merged_areas(data: bytes, part: str) -> Iterator[tuple[int, int, int, int]]:
    from openpyxl.utils.cell import range_boundaries

    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        xml = archive.read(part.lstrip("/"))
    for match in _MERGE_CELL.finditer(xml):
        bounds = range_boundaries(match.group(1).decode("ascii"))
        first_col, first_row, last_col, last_row = (int(bound or 1) for bound in bounds)
        yield first_row - 1, first_col - 1, last_row - 1, last_col - 1


def _part_of(worksheet: Any) -> str:
    # openpyxl has no public accessor for the archive part of a sheet. The
    # attribute is covered by a test and the dependency is pinned to one major version.
    part: str = worksheet._worksheet_path
    return part


def _rows(worksheet: Any, limits: ReadLimits) -> Grid:
    # The declared dimension is often wrong or reaches far past the data.
    worksheet.reset_dimensions()
    collector = RowCollector(limits, trim_trailing_rows=True)
    for values in worksheet.iter_rows(values_only=True):
        collector.add(cell_text(value) for value in values)
    return collector.finish()


def read_xlsx(data: bytes, sheet: str | int | None, limits: ReadLimits) -> WorkbookResult:
    """Read an XLSX workbook into a grid of cell text.

    Formulas give the result the file stored and are never evaluated. Merged
    areas repeat the value of their top-left cell, clipped to the data.

    Raises:
        LimitExceededError: if the archive, the rows, the columns or a cell go
            beyond the limits.
        MissingExtraError: if the ``excel`` extra is not installed.
        UnsupportedFileError: if the workbook cannot be read, or the sheet does
            not exist (``sheet_not_found``).
    """
    check_archive(data, limits)
    try:
        from openpyxl import load_workbook
    except ImportError:
        raise MissingExtraError("excel") from None
    try:
        workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True, keep_links=False)
    except (MemoryError, RecursionError):
        raise
    except Exception:
        raise UnsupportedFileError() from None
    try:
        titles = [worksheet.title for worksheet in workbook.worksheets]
        candidates = select_sheets(titles, sheet)
        first_empty: Grid | None = None
        for index in candidates:
            worksheet = workbook[titles[index]]
            try:
                grid = _rows(worksheet, limits)
                if not grid.rows:
                    first_empty = first_empty or grid
                    continue
                changed = fill_merged(grid.rows, _merged_areas(data, _part_of(worksheet)))
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
        workbook.close()
