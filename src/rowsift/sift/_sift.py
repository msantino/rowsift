"""Apply a mapping to a table."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import replace

from rowsift.clean import CleanOptions
from rowsift.clean import value as clean_value
from rowsift.map import Field, Mapping
from rowsift.profile import Profile
from rowsift.sift._types import FieldSummary, Rejection, SiftedRow, SiftResult, Summary
from rowsift.types import Change, Issue, IssueCode, Table

__all__ = ["sift"]


def sift(
    table: Table,
    profile: Profile,
    mapping: Mapping,
    fields: Sequence[Field],
    *,
    options: CleanOptions | None = None,
    include_extras: bool = True,
) -> SiftResult:
    """Clean the data rows of ``table`` into the declared fields.

    Each data row is cleaned, field by field, with the kind of the field. A row
    is rejected only when a required field is empty (``required_missing``) or
    its value has an issue. An optional field that is empty or has an issue is
    ``None`` in the row, and the issue is recorded on the row. Rows the profile
    skipped (rows above the header, empty rows, repeated headers, totals) are
    not data and are not counted.

    Nothing is modified and nothing is read beyond the arguments, so the same
    arguments give an equal result.

    Args:
        table: the grid from ``read``.
        profile: the profile of ``table``.
        mapping: which column feeds each field, from ``suggest``, ``apply_saved``
            or changed by the caller.
        fields: the declared fields. Each must have a choice in ``mapping``.
        options: the cleaning options of the call. A field's own ``options``
            replace them, and a field's ``one_of`` replaces ``one_of`` in both.
            ``None`` means the defaults.
        include_extras: return the text of the unmapped columns in each row.

    Returns:
        The kept rows, the rejections and the summary.

    Raises:
        ValueError: if two fields share a key, a field has no choice in the
            mapping, the mapping has a choice for no field, a choice points to a
            column the profile does not have, a required field has no column, or
            the profile does not match the table (another column count or a data
            start beyond the rows).
            Raised before any row is processed.
    """
    plan = _plan(profile, mapping, fields)
    if len(profile.columns) != table.report.column_count or profile.data_start > len(table.rows):
        raise ValueError("the profile does not match the table")
    base = options if options is not None else CleanOptions()
    per_field = {item.key: _options_of(item, base) for item in fields}
    extras_columns = _extras_columns(profile, mapping) if include_extras else ()

    rows: list[SiftedRow] = []
    rejected: list[Rejection] = []
    changes_count: dict[str, Counter[str]] = {item.key: Counter() for item in fields}
    issues_count: dict[str, Counter[str]] = {item.key: Counter() for item in fields}
    filled: Counter[str] = Counter()
    data_rows = 0
    rejected_rows = 0

    for index in _data_indexes(table, profile):
        data_rows += 1
        cells = table.rows[index]
        values: dict[str, object] = {}
        changes: dict[str, tuple[Change, ...]] = {}
        issues: dict[str, Issue] = {}
        failures: list[Rejection] = []
        for item, column in plan:
            cleaned = clean_value(
                cells[column] if column is not None else "", item.kind, per_field[item.key]
            )
            values[item.key] = cleaned.value
            if cleaned.value is not None:
                filled[item.key] += 1
            if cleaned.changes:
                changes[item.key] = cleaned.changes
                changes_count[item.key].update(change.code for change in cleaned.changes)
            issue = cleaned.issue
            if issue is None and cleaned.value is None and item.required:
                issue = Issue(IssueCode.REQUIRED_MISSING)
            if issue is None:
                continue
            issues_count[item.key][issue.code] += 1
            if item.required:
                failures.append(Rejection(index + 1, item.key, issue))
            else:
                issues[item.key] = issue
        if failures:
            rejected.extend(failures)
            rejected_rows += 1
            continue
        extras = {profile.columns[c].normalized_header: cells[c] for c in extras_columns}
        rows.append(SiftedRow(index + 1, values, extras, changes, issues))

    summary = Summary(
        data_rows=data_rows,
        kept=len(rows),
        rejected=rejected_rows,
        fields={
            item.key: FieldSummary(
                filled[item.key], changes_count[item.key], issues_count[item.key]
            )
            for item in fields
        },
    )
    return SiftResult(tuple(rows), tuple(rejected), summary)


def _plan(
    profile: Profile, mapping: Mapping, fields: Sequence[Field]
) -> list[tuple[Field, int | None]]:
    keys = [item.key for item in fields]
    if len(set(keys)) != len(keys):
        raise ValueError("two fields share a key")
    choices = {choice.field: choice for choice in mapping.choices}
    for key in keys:
        if key not in choices:
            raise ValueError(f"the mapping has no choice for the field {key!r}")
    for key in choices:
        if key not in keys:
            raise ValueError(f"the mapping has a choice for {key!r}, which is not a declared field")
    plan: list[tuple[Field, int | None]] = []
    for item in fields:
        column = choices[item.key].column
        if column is None and item.required:
            raise ValueError(f"the required field {item.key!r} has no column")
        if column is not None and column >= len(profile.columns):
            raise ValueError(
                f"the field {item.key!r} points to column {column}, which is not in the profile"
            )
        plan.append((item, column))
    return plan


def _options_of(item: Field, base: CleanOptions) -> CleanOptions:
    chosen = item.options if item.options is not None else base
    if item.one_of is not None:
        return replace(chosen, one_of=item.one_of)
    return chosen


def _extras_columns(profile: Profile, mapping: Mapping) -> tuple[int, ...]:
    assigned = {choice.column for choice in mapping.choices if choice.column is not None}
    return tuple(column.index for column in profile.columns if column.index not in assigned)


def _data_indexes(table: Table, profile: Profile) -> list[int]:
    skipped = {row.index for row in profile.skipped_rows}
    return [i for i in range(profile.data_start, len(table.rows)) if i not in skipped]
