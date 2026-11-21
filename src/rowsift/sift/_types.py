"""Value types of the sifting layer."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from rowsift.types import Change, Issue

__all__ = ["FieldSummary", "Rejection", "SiftResult", "SiftedRow", "Summary"]


def _frozen(mapping: Mapping[Any, Any]) -> Mapping[Any, Any]:
    return MappingProxyType(dict(mapping))


@dataclass(frozen=True, slots=True)
class SiftedRow:
    """A data row that was kept, with its fields cleaned.

    Attributes:
        number: the 1-based position of the row in the file, counting the rows
            above the header. The first row of the table is ``1``.
        values: the cleaned value of every declared field, keyed by field key.
            A field with no column, an empty cell or an optional value that
            failed holds ``None``.
        extras: the text of every column no field uses, keyed by normalized
            header. Empty when the caller asked for no extras.
        changes: what the cleaners altered, keyed by field key. Only fields with
            at least one change appear.
        issues: why an optional field became ``None``, keyed by field key. Only
            fields that failed appear.
    """

    number: int
    values: Mapping[str, object]
    extras: Mapping[str, str] = field(default_factory=dict)
    changes: Mapping[str, tuple[Change, ...]] = field(default_factory=dict)
    issues: Mapping[str, Issue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("values", "extras", "changes", "issues"):
            object.__setattr__(self, name, _frozen(getattr(self, name)))


@dataclass(frozen=True, slots=True)
class Rejection:
    """Why a row was left out: a required field that failed.

    A row with several failing required fields has one rejection per field.

    Attributes:
        number: the 1-based position of the row in the file.
        field: the key of the required field.
        issue: the issue code and its data. ``required_missing`` when the cell
            was empty.
    """

    number: int
    field: str
    issue: Issue


@dataclass(frozen=True, slots=True)
class FieldSummary:
    """The outcomes of one field over every data row, kept or rejected.

    Attributes:
        filled: how many rows got a value for the field.
        changes: how many times each change code was reported, keyed by the
            code (a ``ChangeCode`` or its string).
        issues: how many rows failed with each issue code, keyed likewise.
    """

    filled: int = 0
    changes: Mapping[str, int] = field(default_factory=dict)
    issues: Mapping[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "changes", _frozen(self.changes))
        object.__setattr__(self, "issues", _frozen(self.issues))


@dataclass(frozen=True, slots=True)
class Summary:
    """Counts of every outcome of a sift.

    Attributes:
        data_rows: the data rows that were cleaned.
        kept: the rows in ``SiftResult.rows``.
        rejected: the rows left out. A row with several failing required fields
            counts once.
        fields: one summary per declared field, in declaration order.
    """

    data_rows: int
    kept: int
    rejected: int
    fields: Mapping[str, FieldSummary]

    def __post_init__(self) -> None:
        object.__setattr__(self, "fields", _frozen(self.fields))


@dataclass(frozen=True, slots=True)
class SiftResult:
    """The outcome of applying a mapping to a table.

    Attributes:
        rows: the kept rows, in file order.
        rejected: the rejections, in file order and then field order.
        summary: the counts.
    """

    rows: tuple[SiftedRow, ...]
    rejected: tuple[Rejection, ...]
    summary: Summary
