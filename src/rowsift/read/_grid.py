"""Shared bookkeeping that turns rows of cell text into a rectangular grid."""

from __future__ import annotations

from collections.abc import Iterable

from rowsift.errors import LimitExceededError, UnsupportedFileError
from rowsift.read._limits import ReadLimits
from rowsift.types import ErrorCode

__all__ = ["Grid", "RowCollector", "fill_merged", "select_sheets"]


class Grid:
    """The result of collecting rows: padded rows and whether columns were dropped."""

    __slots__ = ("columns_dropped", "rows")

    def __init__(self, rows: list[list[str]], columns_dropped: bool) -> None:
        self.rows = rows
        self.columns_dropped = columns_dropped


class RowCollector:
    """Collect rows one at a time, enforcing the row, column and cell limits.

    Every row is cut at its last non-empty cell, so ``max_columns`` counts
    columns that hold data. With ``trim_trailing_rows`` the rows after the last
    non-empty one are dropped, which is what a workbook needs because its sheet
    dimension often reaches far past the data.
    """

    def __init__(self, limits: ReadLimits, *, trim_trailing_rows: bool) -> None:
        self._limits = limits
        self._trim_trailing_rows = trim_trailing_rows
        self._rows: list[list[str]] = []
        self._pending_empty = 0
        self._raw_width = 0

    def add(self, cells: Iterable[str]) -> None:
        """Add the next row of cell text."""
        row = list(cells)
        self._raw_width = max(self._raw_width, len(row))
        for cell in row:
            if len(cell) > self._limits.max_cell_chars:
                raise LimitExceededError("max_cell_chars", self._limits.max_cell_chars)
        while row and not row[-1]:
            row.pop()
        if len(row) > self._limits.max_columns:
            raise LimitExceededError("max_columns", self._limits.max_columns)
        if not row and self._trim_trailing_rows:
            self._pending_empty += 1
            return
        for _ in range(self._pending_empty):
            self._append([])
        self._pending_empty = 0
        self._append(row)

    def _append(self, row: list[str]) -> None:
        if len(self._rows) >= self._limits.max_rows:
            raise LimitExceededError("max_rows", self._limits.max_rows)
        self._rows.append(row)

    def finish(self) -> Grid:
        """Pad every row to the widest one and report whether columns were dropped."""
        if not self._trim_trailing_rows:
            for _ in range(self._pending_empty):
                self._append([])
            self._pending_empty = 0
        width = max((len(row) for row in self._rows), default=0)
        for row in self._rows:
            row.extend([""] * (width - len(row)))
        return Grid(self._rows, columns_dropped=self._raw_width > width)


def fill_merged(rows: list[list[str]], areas: Iterable[tuple[int, int, int, int]]) -> bool:
    """Give every cell of each merged area the value of its top-left cell.

    ``areas`` are ``(first_row, first_column, last_row, last_column)``, zero
    based and inclusive. An area is clipped to the grid, so an area that runs
    past the data never grows the table. Returns whether any cell changed.

    Raises:
        UnsupportedFileError: if the areas, taken together, cover more cells than
            the grid holds, which only overlapping areas can do.
    """
    height = len(rows)
    width = len(rows[0]) if rows else 0
    budget = height * width
    changed = False
    for first_row, first_col, last_row, last_col in areas:
        last_row = min(last_row, height - 1)
        last_col = min(last_col, width - 1)
        if first_row > last_row or first_col > last_col:
            continue
        budget -= (last_row - first_row + 1) * (last_col - first_col + 1)
        if budget < 0:
            raise UnsupportedFileError()
        value = rows[first_row][first_col]
        if not value:
            continue
        for row_index in range(first_row, last_row + 1):
            row = rows[row_index]
            for col_index in range(first_col, last_col + 1):
                if row[col_index] != value:
                    row[col_index] = value
                    changed = True
    return changed


def select_sheets(names: list[str], sheet: str | int | None) -> list[int]:
    """Indexes of the sheets to try, in order.

    With no ``sheet`` every sheet is a candidate, so the first non-empty one
    wins. A name or a zero-based index selects exactly one.

    Raises:
        UnsupportedFileError: with the code ``sheet_not_found`` if the name or the
            index does not exist.
    """
    if sheet is None:
        return list(range(len(names)))
    if isinstance(sheet, str):
        if sheet in names:
            return [names.index(sheet)]
    elif 0 <= sheet < len(names):
        return [sheet]
    raise UnsupportedFileError(ErrorCode.SHEET_NOT_FOUND)
