"""The entry point of the reading layer."""

from __future__ import annotations

from rowsift.errors import LimitExceededError
from rowsift.read._detect import detect_format
from rowsift.read._grid import select_sheets
from rowsift.read._limits import ReadLimits
from rowsift.read._text import read_delimited
from rowsift.read._workbook import WorkbookResult
from rowsift.read._xls import read_xls
from rowsift.read._xlsx import read_xlsx
from rowsift.types import FileFormat, ReadReport, Table

__all__ = ["read"]


def read(
    data: bytes | bytearray | memoryview,
    *,
    filename: str | None = None,
    sheet: str | int | None = None,
    limits: ReadLimits | None = None,
) -> Table:
    """Read the bytes of a spreadsheet into a grid of text cells.

    The format comes from the content: an XLSX workbook, an XLS workbook or
    delimited text. XLSX and XLS need the ``excel`` extra. Every cell is text,
    short rows are padded and trailing columns that are empty in every row are
    dropped. Formulas give the result the file stored and are never evaluated.
    The ``report`` of the table says how the file was read.

    Args:
        data: the bytes of the file (``bytes``, ``bytearray`` or ``memoryview``).
        filename: accepted for the caller's convenience. It never changes the
            result, because the format is decided by the content.
        sheet: the sheet of a workbook, by name or zero-based index. By default
            the first sheet that holds data. A file of delimited text has no
            sheets, so asking for one raises ``sheet_not_found``.
        limits: the bounds to enforce. ``ReadLimits()`` when omitted.

    Returns:
        The table and its report.

    Raises:
        LimitExceededError: if the input, the rows, the columns, a cell or the
            decompressed size of a workbook go beyond the limits.
        MissingExtraError: if a workbook is read without the ``excel`` extra.
        UnsupportedFileError: if the bytes are no supported format, the sheet
            does not exist (``sheet_not_found``) or the workbook is encrypted
            with a password (``password_protected``).
        DecodingError: if a byte order mark promises an encoding the bytes do not
            follow, or the delimited text cannot be split into records.
        TypeError: if an argument has the wrong type.
    """
    if not isinstance(data, bytes | bytearray | memoryview):
        raise TypeError("data must be bytes")
    if filename is not None and not isinstance(filename, str):
        raise TypeError("filename must be a str or None")
    if sheet is not None and (isinstance(sheet, bool) or not isinstance(sheet, str | int)):
        raise TypeError("sheet must be a str, an int or None")
    if limits is None:
        limits = ReadLimits()
    elif not isinstance(limits, ReadLimits):
        raise TypeError("limits must be a ReadLimits")
    if memoryview(data).nbytes > limits.max_bytes:
        raise LimitExceededError("max_bytes", limits.max_bytes)
    content = bytes(data)

    file_format = detect_format(content) if content else FileFormat.CSV
    if file_format is FileFormat.CSV:
        if sheet is not None:
            select_sheets([], sheet)
        text = read_delimited(content, limits)
        rows = tuple(tuple(row) for row in text.grid.rows)
        report = ReadReport(
            format=FileFormat.CSV,
            encoding=text.encoding,
            delimiter=text.delimiter,
            row_count=len(rows),
            column_count=len(rows[0]) if rows else 0,
            notes=text.notes,
        )
        return Table(rows, report)
    workbook: WorkbookResult
    if file_format is FileFormat.XLSX:
        workbook = read_xlsx(content, sheet, limits)
    else:
        workbook = read_xls(content, sheet, limits)
    rows = tuple(tuple(row) for row in workbook.grid.rows)
    report = ReadReport(
        format=file_format,
        sheet=workbook.sheet,
        sheets=workbook.sheets,
        row_count=len(rows),
        column_count=len(rows[0]) if rows else 0,
        notes=workbook.notes(),
    )
    return Table(rows, report)
