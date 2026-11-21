"""Value types of the profile layer."""

from __future__ import annotations

from dataclasses import dataclass

from rowsift.types import Kind, SkipCode

__all__ = ["ColumnProfile", "Profile", "RunnerUp", "SkippedRow", "TopValue"]


@dataclass(frozen=True, slots=True)
class SkippedRow:
    """A row of the table that is not a data row, and why.

    ``index`` is the 0-based position of the row in ``Table.rows``.
    """

    index: int
    code: SkipCode


@dataclass(frozen=True, slots=True)
class RunnerUp:
    """The kind that came closest to the one a column was given, and its share."""

    kind: Kind
    share: float


@dataclass(frozen=True, slots=True)
class TopValue:
    """A value of a low-cardinality column and how many times it appears."""

    value: str
    count: int


@dataclass(frozen=True, slots=True)
class ColumnProfile:
    """What one column holds.

    Attributes:
        index: 0-based position of the column in the table.
        header: the header cell as written, or ``""`` when the cell is empty or
            the table has no header.
        normalized_header: the header folded for matching (see
            ``normalize_header``), unique among the columns. An empty header and
            a table with no header give ``column_<position>``, with the position
            counted from 1.
        kind: the most specific kind that at least ``kind_threshold`` of the
            non-empty sampled values fit, or ``text``.
        kind_share: the share of the non-empty sampled values that fit ``kind``.
            ``0.0`` for a column with no filled cell.
        runner_up: the closest other kind with a share above zero, or ``None``.
        filled: the number of data rows where the cell is not empty.
        distinct: the number of distinct non-empty values among the data rows.
        low_cardinality: whether the column holds a small set of repeated values.
        top_values: for a low-cardinality column, each value with its count, in
            descending order of count. Empty otherwise.
        samples: up to ``sample_count`` distinct values, masked by ``kind``
            unless ``mask_samples`` is off.
    """

    index: int
    header: str
    normalized_header: str
    kind: Kind
    kind_share: float
    runner_up: RunnerUp | None
    filled: int
    distinct: int
    low_cardinality: bool
    top_values: tuple[TopValue, ...]
    samples: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Profile:
    """The structure of a table: where the data is and what each column holds.

    Attributes:
        header_row: index in ``Table.rows`` of the header, or ``None`` when the
            table has no header.
        data_start: index of the first row after the header, ``0`` with no header.
        data_rows: the number of rows that count as data.
        skipped_rows: every row that is not a header and not data, with its code,
            in table order.
        columns: one profile per column, in table order.
    """

    header_row: int | None
    data_start: int
    data_rows: int
    skipped_rows: tuple[SkippedRow, ...]
    columns: tuple[ColumnProfile, ...]
