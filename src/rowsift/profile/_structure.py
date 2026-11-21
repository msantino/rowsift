"""Where the header is, and which rows are data."""

from __future__ import annotations

import re
from dataclasses import dataclass

from rowsift.clean import CleanOptions
from rowsift.profile._headers import normalize_header
from rowsift.profile._kinds import looks_like_data
from rowsift.profile._options import ProfileOptions
from rowsift.profile._types import SkippedRow
from rowsift.types import SkipCode

__all__ = ["Structure", "find_structure"]

_TOTAL_WORDS = frozenset(
    {"total", "totais", "subtotal", "total geral", "grand total", "soma", "sum"}
)
_MIN_FILLED_SHARE = 0.5  # of the widest of the first rows: a header fills more
_MAX_DATA_SHARE = 0.2  # of a header's cells that may look like data
_MIN_DISTINCT_SHARE = 0.5  # of a header's cells that must differ: a header may repeat a name
_DATA_COLUMN_SHARE = 0.5  # of the cells below that make a column "data-shaped"
_ROWS_BELOW = 20
_WIDTH_ROWS = 20  # non-empty rows that set the widest row, whatever the scan window
_YEAR = re.compile(r"(?:19|20)[0-9]{2}")


@dataclass(frozen=True, slots=True)
class Structure:
    """Header position, first data row, skipped rows and the indexes of the data rows."""

    header_row: int | None
    data_start: int
    skipped: tuple[SkippedRow, ...]
    data: tuple[int, ...]


def _filled(row: tuple[str, ...]) -> list[str]:
    return [cell.strip() for cell in row if cell.strip()]


def _numbers_below(below: list[tuple[str, ...]], column: int, options: CleanOptions) -> bool:
    """Whether most of the filled cells under a column are numbers."""
    under = [r[column].strip() for r in below if r[column].strip()]
    numbers = sum(looks_like_data(v, options) for v in under)
    return bool(under) and numbers >= _DATA_COLUMN_SHARE * len(under)


def _is_header(
    rows: tuple[tuple[str, ...], ...],
    position: int,
    non_empty: list[int],
    widest: int,
    options: CleanOptions,
) -> bool:
    """Whether the ``position``-th non-empty row reads as a header."""
    row = rows[non_empty[position]]
    cells = _filled(row)
    if len(cells) <= _MIN_FILLED_SHARE * widest:
        return False
    below = [rows[i] for i in non_empty[position + 1 : position + 1 + _ROWS_BELOW]]
    data_like = {
        i: looks_like_data(cell.strip(), options) for i, cell in enumerate(row) if cell.strip()
    }
    # A year is a label when the rows under it are data: a pivot layout (Name, 2023, 2024).
    labels = [
        i
        for i, flag in data_like.items()
        if flag and _YEAR.fullmatch(row[i].strip()) and _numbers_below(below, i, options)
    ]
    if len(labels) < len(data_like) and len(labels) == sum(data_like.values()):
        data_like = {i: flag and i not in labels for i, flag in data_like.items()}
    if sum(data_like.values()) > _MAX_DATA_SHARE * len(cells):
        return False
    if len({cell.casefold() for cell in cells}) < _MIN_DISTINCT_SHARE * len(cells):
        return False
    for column, cell in enumerate(row):
        if not cell.strip() or data_like[column]:
            continue
        under = [r[column].strip() for r in below if r[column].strip()]
        if under and (
            sum(looks_like_data(v, options) for v in under) >= _DATA_COLUMN_SHARE * len(under)
        ):
            return True
    # A table of text only has no column to tell a header apart by shape. Its first
    # row is the header when none of its cells comes back below it.
    if position == 0:
        return all(
            cell.strip().casefold() not in {r[column].strip().casefold() for r in below}
            for column, cell in enumerate(row)
            if cell.strip()
        )
    return False


# A total word, then a colon or hyphen, then a count: "Total: 25", "Subtotal - 3".
_TOTAL_WITH_COUNT = re.compile(r"\s*(?P<word>[^\d:\-]+?)\s*[:\-]\s*\d[\d.,]*\s*")


def _is_total(row: tuple[str, ...]) -> bool:
    """Whether the first filled cell is a total word, alone or followed by a count.

    ``Total`` and ``Total: 25`` qualify. The count needs a colon or a hyphen
    after the word, so a label such as ``Total 2024`` is data. Only the ASCII
    colon and hyphen separate: ``Total - 2024`` is a total row, while
    ``Total`` followed by an en dash and a count, and ``Total: -5`` are data. A total word
    followed by anything but a count (``Total de vendas``) does not qualify.
    """
    first = next((cell for cell in row if cell.strip()), "")
    if normalize_header(first) in _TOTAL_WORDS:
        return True
    match = _TOTAL_WITH_COUNT.fullmatch(first)
    return match is not None and normalize_header(match["word"]) in _TOTAL_WORDS


def find_structure(rows: tuple[tuple[str, ...], ...], options: ProfileOptions) -> Structure:
    """Find the header and classify every row as header, data or skipped."""
    non_empty = [i for i, row in enumerate(rows) if _filled(row)]
    window = non_empty[: options.header_scan_rows]
    widest = max(
        (len(_filled(rows[i])) for i in non_empty[: max(options.header_scan_rows, _WIDTH_ROWS)]),
        default=0,
    )
    header_row: int | None = None
    for position, index in enumerate(window):
        if _is_header(rows, position, non_empty, widest, options.clean):
            header_row = index
            break

    skipped: dict[int, SkipCode] = {}
    data_start = 0 if header_row is None else header_row + 1
    for index, row in enumerate(rows[:data_start]):
        if index == header_row:
            continue
        skipped[index] = SkipCode.EMPTY if not _filled(row) else SkipCode.BEFORE_HEADER

    last = len(rows)
    while last > data_start and (not _filled(rows[last - 1]) or _is_total(rows[last - 1])):
        last -= 1
        skipped[last] = SkipCode.EMPTY if not _filled(rows[last]) else SkipCode.TOTAL_ROW

    repeated = (
        tuple(normalize_header(cell) for cell in rows[header_row])
        if header_row is not None
        else None
    )
    for index in range(data_start, last):
        row = rows[index]
        if not _filled(row):
            skipped[index] = SkipCode.EMPTY
        elif repeated and any(repeated) and tuple(normalize_header(c) for c in row) == repeated:
            skipped[index] = SkipCode.REPEATED_HEADER

    data = tuple(i for i in range(data_start, len(rows)) if i not in skipped)
    ordered = tuple(SkippedRow(i, skipped[i]) for i in sorted(skipped))
    return Structure(header_row, data_start, ordered, data)
