"""Value types and code enumerations shared by every layer.

Everything here is a frozen dataclass with slots or a ``StrEnum``, so values
are immutable and codes serialize as plain strings. This module imports
nothing else from the package.

Every explanation the library gives is a code plus structured data. There are
no sentences: the application writes the message. Removing or renaming a code
is a breaking change, adding one is a minor change.
"""

from __future__ import annotations

import calendar
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Generic, TypeVar

__all__ = [
    "Change",
    "ChangeCode",
    "Cleaned",
    "Confidence",
    "DataValue",
    "DayMonth",
    "ErrorCode",
    "FileFormat",
    "Issue",
    "IssueCode",
    "Kind",
    "LineType",
    "ReadNote",
    "ReadReport",
    "Reason",
    "ReasonCode",
    "SkipCode",
    "Table",
]

DataValue = str | int | float | bool
"""A scalar carried in the ``data`` of a code: a share, a count, a name."""

T = TypeVar("T")

_LEAP_YEAR = 2000
"""A leap year, so that 29 February is accepted as a day and month."""


class Kind(StrEnum):
    """What a column or a value holds."""

    TEXT = "text"
    NAME = "name"
    INTEGER = "integer"
    DECIMAL = "decimal"
    MONEY = "money"
    BOOLEAN = "boolean"
    DATE = "date"
    DAY_MONTH = "day_month"
    TIME = "time"
    DATETIME = "datetime"
    PHONE = "phone"
    EMAIL = "email"
    CPF = "cpf"
    CNPJ = "cnpj"
    POSTAL_CODE = "postal_code"
    CATEGORY = "category"


class Confidence(StrEnum):
    """How sure a mapping suggestion is."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class FileFormat(StrEnum):
    """The format a file was detected as, from its content."""

    CSV = "csv"
    XLSX = "xlsx"
    XLS = "xls"


class LineType(StrEnum):
    """Whether a phone number is a mobile or a landline."""

    MOBILE = "mobile"
    LANDLINE = "landline"


class ChangeCode(StrEnum):
    """A transformation that altered the meaning-bearing content of a value."""

    NINTH_DIGIT_INSERTED = "ninth_digit_inserted"
    MULTIPLE_VALUES = "multiple_values"
    TWO_DIGIT_YEAR_EXPANDED = "two_digit_year_expanded"
    YEAR_DISCARDED = "year_discarded"
    LEADING_ZEROS_RESTORED = "leading_zeros_restored"
    SEPARATOR_INFERRED = "separator_inferred"
    CASE_CHANGED = "case_changed"
    SERIAL_DATE_CONVERTED = "serial_date_converted"
    TIME_DEFAULTED = "time_defaulted"


class IssueCode(StrEnum):
    """Why a value could not be normalized, or why a row was rejected."""

    TOO_SHORT = "too_short"
    TRUNCATED = "truncated"
    INVALID_AREA_CODE = "invalid_area_code"
    NOT_MOBILE = "not_mobile"
    INVALID_DATE = "invalid_date"
    NOT_A_DATE = "not_a_date"
    NOT_A_NUMBER = "not_a_number"
    INVALID_CHECK_DIGIT = "invalid_check_digit"
    INVALID_EMAIL = "invalid_email"
    NOT_IN_ALLOWED_VALUES = "not_in_allowed_values"
    REQUIRED_MISSING = "required_missing"
    INVALID_PHONE = "invalid_phone"
    INVALID_LENGTH = "invalid_length"
    NOT_A_TIME = "not_a_time"
    NOT_A_BOOLEAN = "not_a_boolean"


class ReasonCode(StrEnum):
    """Why a column was, or was not, suggested for a field."""

    HEADER_MATCHES_ALIAS = "header_matches_alias"
    HEADER_CONTAINS_ALIAS = "header_contains_alias"
    CONTENT_FITS_KIND = "content_fits_kind"
    CONTENT_CONFLICTS_WITH_KIND = "content_conflicts_with_kind"
    ONLY_CANDIDATE = "only_candidate"
    REQUIRED_FIELD_UNMATCHED = "required_field_unmatched"
    SAVED_MAPPING = "saved_mapping"
    SAVED_HEADER_MISSING = "saved_header_missing"
    SET_BY_CALLER = "set_by_caller"


class SkipCode(StrEnum):
    """Why a row is not a data row."""

    EMPTY = "empty"
    BEFORE_HEADER = "before_header"
    REPEATED_HEADER = "repeated_header"
    TOTAL_ROW = "total_row"


class ReadNote(StrEnum):
    """Something the reader did that the caller may want to know about."""

    BOM_REMOVED = "bom_removed"
    MERGED_CELLS_FILLED = "merged_cells_filled"
    TRAILING_EMPTY_COLUMNS_DROPPED = "trailing_empty_columns_dropped"
    UNTERMINATED_QUOTE = "unterminated_quote"


class ErrorCode(StrEnum):
    """The code carried by every exception the library raises on purpose."""

    UNSUPPORTED_FILE = "unsupported_file"
    SHEET_NOT_FOUND = "sheet_not_found"
    PASSWORD_PROTECTED = "password_protected"
    LIMIT_EXCEEDED = "limit_exceeded"
    MISSING_EXTRA = "missing_extra"
    DECODING_FAILED = "decoding_failed"


_DATA_TYPES = (str, int, float, bool)


def _freeze(data: Mapping[str, DataValue]) -> Mapping[str, DataValue]:
    """A read-only copy of ``data``, so a code cannot be altered after the fact.

    Raises:
        TypeError: if a key is not text or a value is not a str, int, float or bool.
    """
    copied = dict(data)
    for key, value in copied.items():
        if type(key) is not str:
            raise TypeError("data keys must be str")
        if not isinstance(value, _DATA_TYPES):
            raise TypeError("data values must be str, int, float or bool")
    return MappingProxyType(copied)


def _hash_data(code: StrEnum, data: Mapping[str, DataValue]) -> int:
    return hash((code, frozenset(data.items())))


@dataclass(frozen=True, slots=True)
class Change:
    """A transformation applied to a value, as a code plus its data.

    ``data`` is copied into a read-only mapping, and the value is hashable.
    Data values compare as Python compares numbers, so ``1``, ``1.0`` and
    ``True`` are equal.

    Raises:
        ValueError: if ``code`` is not a ``ChangeCode``.
        TypeError: if ``data`` holds a key that is not text or a non-scalar value.
    """

    code: ChangeCode
    data: Mapping[str, DataValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", ChangeCode(self.code))
        object.__setattr__(self, "data", _freeze(self.data))

    def __hash__(self) -> int:
        return _hash_data(self.code, self.data)

    def __reduce__(self) -> tuple[Any, tuple[Any, ...]]:
        return (type(self), (self.code, dict(self.data)))


@dataclass(frozen=True, slots=True)
class Issue:
    """The reason a value failed, as a code plus its data.

    ``data`` is copied into a read-only mapping, and the value is hashable.
    Data values compare as Python compares numbers, so ``1``, ``1.0`` and
    ``True`` are equal.

    Raises:
        ValueError: if ``code`` is not an ``IssueCode``.
        TypeError: if ``data`` holds a key that is not text or a non-scalar value.
    """

    code: IssueCode
    data: Mapping[str, DataValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", IssueCode(self.code))
        object.__setattr__(self, "data", _freeze(self.data))

    def __hash__(self) -> int:
        return _hash_data(self.code, self.data)

    def __reduce__(self) -> tuple[Any, tuple[Any, ...]]:
        return (type(self), (self.code, dict(self.data)))


@dataclass(frozen=True, slots=True)
class Reason:
    """Why a column was, or was not, suggested for a field, as a code plus its data.

    ``data`` is copied into a read-only mapping, and the value is hashable.
    Data values compare as Python compares numbers, so ``1``, ``1.0`` and
    ``True`` are equal.

    Raises:
        ValueError: if ``code`` is not a ``ReasonCode``.
        TypeError: if ``data`` holds a key that is not text or a non-scalar value.
    """

    code: ReasonCode
    data: Mapping[str, DataValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", ReasonCode(self.code))
        object.__setattr__(self, "data", _freeze(self.data))

    def __hash__(self) -> int:
        return _hash_data(self.code, self.data)

    def __reduce__(self) -> tuple[Any, tuple[Any, ...]]:
        return (type(self), (self.code, dict(self.data)))


@dataclass(frozen=True, slots=True)
class Cleaned(Generic[T]):  # PEP 695 syntax needs Python 3.12, the floor is 3.11
    """The outcome of cleaning one value.

    A non-empty input gives either a ``value`` or an ``issue``. An empty input
    gives neither, and no changes. ``changes`` lists what was altered on the way.

    Raises:
        ValueError: if both ``value`` and ``issue`` are set, or if there are
            changes and neither is set.
    """

    value: T | None = None
    changes: tuple[Change, ...] = ()
    issue: Issue | None = None

    def __post_init__(self) -> None:
        if self.value is not None and self.issue is not None:
            raise ValueError("a Cleaned carries a value or an issue, never both")
        if self.value is None and self.issue is None and self.changes:
            raise ValueError("changes need a value or an issue")


@dataclass(frozen=True, slots=True)
class DayMonth:
    """A day and a month with no year, such as a birthday.

    29 February is valid. No year is ever invented.

    Raises:
        TypeError: if the day or the month is not an ``int`` (a ``bool`` is not).
        ValueError: if the day does not exist in the month.
    """

    day: int
    month: int

    def __post_init__(self) -> None:
        for part in (self.day, self.month):
            if type(part) is not int:
                raise TypeError("day and month must be int")
        if not 1 <= self.month <= 12:
            raise ValueError("month must be between 1 and 12")
        if not 1 <= self.day <= calendar.monthrange(_LEAP_YEAR, self.month)[1]:
            raise ValueError("day does not exist in the month")


@dataclass(frozen=True, slots=True, kw_only=True)
class ReadReport:
    """How a file was read. Every field is passed by keyword.

    ``encoding`` and ``delimiter`` are ``None`` for workbooks. ``sheet`` is
    ``None`` for delimited text. ``sheets`` lists the names available.

    Raises:
        TypeError: if a count is not an ``int`` (a ``bool`` is not).
        ValueError: if a count is negative.
    """

    format: FileFormat
    encoding: str | None = None
    delimiter: str | None = None
    sheet: str | None = None
    sheets: tuple[str, ...] = ()
    row_count: int
    column_count: int
    notes: tuple[ReadNote, ...] = ()

    def __post_init__(self) -> None:
        for count in (self.row_count, self.column_count):
            if type(count) is not int:
                raise TypeError("row_count and column_count must be int")
            if count < 0:
                raise ValueError("row_count and column_count must not be negative")


@dataclass(frozen=True, slots=True)
class Table:
    """A grid of text cells and the report of how it was read.

    Every cell is text, with an empty string for an empty cell. Every row has
    ``report.column_count`` cells and there are ``report.row_count`` rows: the
    reader pads short rows.

    Raises:
        TypeError: if ``rows`` is not a tuple of tuples of ``str``.
        ValueError: if the rows are not rectangular or disagree with the report.
    """

    rows: tuple[tuple[str, ...], ...]
    report: ReadReport

    def __post_init__(self) -> None:
        if type(self.rows) is not tuple or any(
            type(row) is not tuple or any(type(cell) is not str for cell in row)
            for row in self.rows
        ):
            raise TypeError("rows must be a tuple of tuples of str")
        if len(self.rows) != self.report.row_count:
            raise ValueError("the number of rows must equal report.row_count")
        if any(len(row) != self.report.column_count for row in self.rows):
            raise ValueError("every row must have report.column_count cells")
        if not self.rows and self.report.column_count:
            raise ValueError("a table with no rows has no columns")
