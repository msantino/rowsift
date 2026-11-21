"""The entry point of the profile layer."""

from __future__ import annotations

from collections import Counter
from itertools import islice

from rowsift.profile._headers import column_names
from rowsift.profile._kinds import display, infer_kind
from rowsift.profile._options import ProfileOptions
from rowsift.profile._structure import find_structure
from rowsift.profile._types import ColumnProfile, Profile, TopValue
from rowsift.types import Kind, Table

__all__ = ["profile"]

# Distinct values looked at for samples: a column that masks alike is not read to its end.
_SCAN_LIMIT = 100


def _display(value: str, kind: Kind, options: ProfileOptions) -> str:
    return display(value, kind, options.clean) if options.mask_samples else value


def _samples(counts: Counter[str], kind: Kind, options: ProfileOptions) -> tuple[str, ...]:
    """Up to ``sample_count`` distinct values as shown, in order of first appearance."""
    shown: list[str] = []
    for value in islice(counts, _SCAN_LIMIT):
        if len(shown) >= options.sample_count:
            break
        text = _display(value, kind, options)
        if text not in shown:
            shown.append(text)
    return tuple(shown)


def _top_values(
    ranked: list[tuple[str, int]], kind: Kind, options: ProfileOptions
) -> tuple[TopValue, ...]:
    """Values as shown with their counts: values that show alike are one, counts summed."""
    merged: Counter[str] = Counter()
    for value, count in ranked:
        merged[_display(value, kind, options)] += count
    ordered = sorted(merged.items(), key=lambda item: (-item[1], item[0]))
    return tuple(TopValue(value, count) for value, count in ordered)


def profile(table: Table, options: ProfileOptions | None = None) -> Profile:
    """Describe the structure of ``table`` and what each column holds.

    Finds the header among the first ``options.header_scan_rows`` non-empty
    rows (no header is a valid answer), separates data rows from rows that are
    skipped with a code, and gives each column a kind with the share of values
    that fit it, a runner-up, counts of filled and distinct cells, the
    low-cardinality signal with its values, and masked samples.

    The kind is inferred from the first ``options.sample_rows`` data rows. The
    counts and top values cover every data row. Samples and top values are
    masked by the kind of their column and by the personal kind each value fits,
    and values that show alike once masked are one, unless ``options.mask_samples``
    is off (see ``display`` in the kinds module for the rule).

    Limits, reported and not guessed: a table of text only, with no header, takes
    its first row as the header. A header of years (``2023``, ``2024``) is
    recognized only above numbers, with at least one text cell beside the years.
    A total row is skipped only at the very end of the data, so a footer line
    after it leaves both as data. A cell longer than 254 characters is never a
    typed value. The time spent grows with ``options.sample_rows`` times the
    number of columns, so lowering ``sample_rows`` bounds it.
    Pure: the same table and options give the same profile.

    Raises:
        MissingExtraError: when ``options.clean`` names a region whose phone
            rules need the ``phone`` extra.
    """
    options = options or ProfileOptions()
    rows = table.rows
    structure = find_structure(rows, options)
    headers = list(rows[structure.header_row]) if structure.header_row is not None else None
    width = table.report.column_count
    names = column_names(headers, width)

    columns: list[ColumnProfile] = []
    for index in range(width):
        values = [rows[i][index].strip() for i in structure.data]
        filled = [value for value in values if value]
        kind, share, runner_up = infer_kind(
            [v for v in values[: options.sample_rows] if v], options.kind_threshold, options.clean
        )
        counts = Counter(filled)
        distinct = len(counts)
        low = (
            len(filled) >= options.low_cardinality_min_filled
            and distinct <= options.low_cardinality_max_distinct
            and distinct <= options.low_cardinality_max_share * len(filled)
        )
        ranked = list(counts.items()) if low else []
        columns.append(
            ColumnProfile(
                index=index,
                header=headers[index] if headers is not None else "",
                normalized_header=names[index],
                kind=kind,
                kind_share=share,
                runner_up=runner_up,
                filled=len(filled),
                distinct=distinct,
                low_cardinality=low,
                top_values=_top_values(ranked, kind, options),
                samples=_samples(counts, kind, options),
            )
        )
    return Profile(
        header_row=structure.header_row,
        data_start=structure.data_start,
        data_rows=len(structure.data),
        skipped_rows=structure.skipped,
        columns=tuple(columns),
    )
