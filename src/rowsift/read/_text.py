"""Delimited text: encoding, delimiter and quoting."""

from __future__ import annotations

import codecs
import csv
import io
import re
import threading
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager

from rowsift.errors import DecodingError, LimitExceededError, UnsupportedFileError
from rowsift.read._grid import Grid, RowCollector
from rowsift.read._limits import ReadLimits
from rowsift.types import ReadNote

__all__ = ["DelimitedResult", "decode", "detect_delimiter", "looks_like_text", "read_delimited"]

_NUL_SAMPLE = 8192
_UTF16_NUL_SHARE = 0.3
_DELIMITER_SAMPLE_RECORDS = 100
# The csv module keeps its field size limit for the whole process.
_FIELD_LIMIT_LOCK = threading.Lock()
# Tie-break order when two delimiters split the sample equally well.
_CANDIDATES = (";", "\t", "|", ",")


def _utf16_without_mark(data: bytes) -> str | None:
    """``utf-16-le`` or ``utf-16-be`` when the NUL bytes sit in one parity only."""
    sample = data[:_NUL_SAMPLE]
    size = len(sample) // 2 * 2
    if size < 2:
        return None
    even_nuls = sample[0:size:2].count(0)
    odd_nuls = sample[1:size:2].count(0)
    half = size // 2
    if even_nuls == 0 and odd_nuls >= half * _UTF16_NUL_SHARE:
        return "utf-16-le"
    if odd_nuls == 0 and even_nuls >= half * _UTF16_NUL_SHARE:
        return "utf-16-be"
    return None


def looks_like_text(data: bytes) -> bool:
    """Whether ``data`` has the look of text: no NUL bytes, or the pattern of UTF-16."""
    if data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return True
    if b"\x00" not in data[:_NUL_SAMPLE]:
        return True
    return _utf16_without_mark(data) is not None


def _strict(data: bytes, encoding: str) -> str | None:
    try:
        return data.decode(encoding)
    except UnicodeDecodeError:
        return None


def decode(data: bytes) -> tuple[str, str, bool]:
    """Decode delimited text. Returns the text, the encoding used and whether a mark was removed.

    The order is a byte order mark (UTF-8, UTF-16 LE, UTF-16 BE), UTF-16 without
    a mark when the NUL pattern says so, strict UTF-8, cp1252 and latin-1. The
    NUL pattern comes before UTF-8 because UTF-16 text of Latin characters is
    also valid UTF-8. The mark is removed from the text.

    Raises:
        DecodingError: if a byte order mark promises an encoding the bytes do not follow.
    """
    marks = (
        (codecs.BOM_UTF8, "utf-8"),
        (codecs.BOM_UTF16_LE, "utf-16-le"),
        (codecs.BOM_UTF16_BE, "utf-16-be"),
    )
    for mark, encoding in marks:
        if data.startswith(mark):
            text = _strict(data[len(mark) :], encoding)
            if text is None:
                raise DecodingError()
            return text, encoding, True
    # UTF-16 text is also valid UTF-8, with a NUL beside every character, so the
    # NUL pattern has to be checked before UTF-8 can claim the bytes.
    wide = _utf16_without_mark(data)
    if wide is not None:
        text = _strict(data, wide)
        if text is not None:
            return text, wide, False
    text = _strict(data, "utf-8")
    if text is not None:
        return text, "utf-8", False
    for encoding in ("cp1252", "latin-1"):
        text = _strict(data, encoding)
        if text is not None:
            return text, encoding, False
    raise DecodingError()  # pragma: no cover - latin-1 decodes every byte


@contextmanager
def _field_limit(limits: ReadLimits) -> Iterator[None]:
    """Set the csv field size limit to one past ``max_cell_chars`` for the block.

    The csv module has its own default of 131072 characters, which would refuse
    a cell the caller allows. One past the limit lets the row collector see an
    oversized cell and refuse it with the cell limit it reports. The previous
    value is restored on the way out.
    """
    with _FIELD_LIMIT_LOCK:
        previous = csv.field_size_limit(limits.max_cell_chars + 1)
        try:
            yield
        finally:
            csv.field_size_limit(previous)


def _ends_inside_quotes(text: str, delimiter: str) -> bool:
    """Whether the text ends in the middle of a quoted field.

    The scan follows the quoting rules of the csv module in its lenient mode: a
    quote opens a quoted field only at the start of a field, a doubled quote
    inside one is a literal quote, and a quote anywhere else is plain text. A
    stray quote earlier in the file therefore does not hide a quote that is
    never closed.
    """
    if '"' not in text:
        return False
    boundary = re.compile(f"[{re.escape(delimiter)}\r\n]")
    size = len(text)
    position = 0
    while position < size:
        if text[position] == '"':
            position += 1
            while True:
                quote = text.find('"', position)
                if quote < 0:
                    return True
                if text.startswith('""', quote):
                    position = quote + 2
                    continue
                position = quote + 1
                break
        found = boundary.search(text, position)
        if found is None:
            return False
        position = found.end()
    return False


def _field_counts(text: str, delimiter: str) -> list[int]:
    counts: list[int] = []
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter)
    try:
        for record in reader:
            if any(cell.strip() for cell in record):
                counts.append(len(record))
                if len(counts) >= _DELIMITER_SAMPLE_RECORDS:
                    break
    except csv.Error:
        pass
    return counts


def detect_delimiter(text: str) -> str | None:
    """The delimiter among ``;`` tab ``|`` and ``,``, or ``None`` for a single column.

    Each candidate splits the first non-empty records, quoted fields respected.
    A candidate needs at least two fields in its most common count. The winner
    is the one with the most records at that count, weighted by the number of
    cells it separates, so a comma inside free text does not beat a semicolon
    that splits every row into many cells. A tie goes to the first of
    ``;`` tab ``|`` ``,``.
    """
    best: str | None = None
    best_score = 0
    for candidate in _CANDIDATES:
        counts = _field_counts(text, candidate)
        if not counts:
            continue
        mode, records = Counter(counts).most_common(1)[0]
        if mode < 2:
            continue
        score = records * (mode - 1)
        if score > best_score:
            best, best_score = candidate, score
    return best


def _unused_character(text: str) -> str:
    for code in range(1, 32):
        character = chr(code)
        if character not in "\r\n" and character not in text:
            return character
    raise UnsupportedFileError()


class DelimitedResult:
    """What reading delimited text produced."""

    __slots__ = ("delimiter", "encoding", "grid", "notes")

    def __init__(
        self,
        grid: Grid,
        encoding: str,
        delimiter: str | None,
        notes: tuple[ReadNote, ...],
    ) -> None:
        self.grid = grid
        self.encoding = encoding
        self.delimiter = delimiter
        self.notes = notes


def read_delimited(data: bytes, limits: ReadLimits) -> DelimitedResult:
    """Read delimited text into a grid of cell text.

    A quoted field that is never closed swallows the rest of the file into one
    cell, so the result carries the ``unterminated_quote`` note. When that
    cell is longer than ``max_cell_chars`` the read raises the cell limit error
    instead, because the limit comes first.

    Raises:
        DecodingError: if a byte order mark promises an encoding the bytes do not
            follow, or the text cannot be split into records.
        LimitExceededError: if the rows, columns or a cell go beyond the limits.
        UnsupportedFileError: if the text cannot be split at all.
    """
    text, encoding, mark_removed = decode(data)
    with _field_limit(limits):
        delimiter = detect_delimiter(text)
        splitter = delimiter if delimiter is not None else _unused_character(text)
        collector = RowCollector(limits, trim_trailing_rows=False)
        reader = csv.reader(io.StringIO(text, newline=""), delimiter=splitter)
        try:
            for record in reader:
                collector.add(record)
        except csv.Error as error:
            if "field larger than field limit" in str(error):
                raise LimitExceededError("max_cell_chars", limits.max_cell_chars) from None
            raise DecodingError() from None
    unterminated = _ends_inside_quotes(text, splitter)
    grid = collector.finish()
    notes = [ReadNote.BOM_REMOVED] if mark_removed else []
    if unterminated:
        notes.append(ReadNote.UNTERMINATED_QUOTE)
    if grid.columns_dropped:
        notes.append(ReadNote.TRAILING_EMPTY_COLUMNS_DROPPED)
    return DelimitedResult(grid, encoding, delimiter, tuple(notes))
