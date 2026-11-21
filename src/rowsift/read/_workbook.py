"""What reading a workbook produced, shared by the XLSX and XLS readers."""

from __future__ import annotations

from rowsift.read._grid import Grid
from rowsift.types import ReadNote

__all__ = ["WorkbookResult"]


class WorkbookResult:
    """The grid of the chosen sheet, its name and the names of every sheet."""

    __slots__ = ("grid", "merged_filled", "sheet", "sheets")

    def __init__(
        self,
        grid: Grid,
        sheet: str | None,
        sheets: tuple[str, ...],
        *,
        merged_filled: bool,
    ) -> None:
        self.grid = grid
        self.sheet = sheet
        self.sheets = sheets
        self.merged_filled = merged_filled

    def notes(self) -> tuple[ReadNote, ...]:
        """The notes of this read, in a fixed order."""
        notes: list[ReadNote] = []
        if self.merged_filled:
            notes.append(ReadNote.MERGED_CELLS_FILLED)
        if self.grid.columns_dropped:
            notes.append(ReadNote.TRAILING_EMPTY_COLUMNS_DROPPED)
        return tuple(notes)
