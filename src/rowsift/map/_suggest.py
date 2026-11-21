"""Suggest a column for each declared field."""

from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Sequence

from rowsift.map._fields import Field
from rowsift.map._score import ACCEPTS, Candidate, alias_table, is_line_header, score_column
from rowsift.map._types import Alternative, Choice, Mapping
from rowsift.profile import ColumnProfile, Profile
from rowsift.types import Confidence, Kind, Reason, ReasonCode

__all__ = ["check_fields", "fingerprint_of", "suggest"]


def check_fields(fields: Sequence[Field]) -> None:
    """Raise ``ValueError`` naming the first key declared twice."""
    seen: set[str] = set()
    for field in fields:
        if field.key in seen:
            raise ValueError(f"duplicate field key {field.key!r}")
        seen.add(field.key)


def fingerprint_of(profile: Profile) -> str:
    """SHA-256 in hexadecimal of the normalized headers, joined by a newline."""
    joined = "\n".join(column.normalized_header for column in profile.columns)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def _order(item: tuple[int, Candidate]) -> tuple[int, float, int, int, int]:
    field_index, candidate = item
    return (
        -candidate.score,
        -candidate.share,
        -candidate.alias_tokens,
        candidate.column,
        field_index,
    )


def suggest(profile: Profile, fields: Sequence[Field]) -> Mapping:
    """Suggest a column for each declared field.

    Each column is scored against each field from two signals: the header (an
    alias equal to it, or an alias all of whose words it contains) and the
    content (the column kind and its share against the field kind). Confidence
    is ``high`` only when the header equals an alias and the content fits the
    kind, ``medium`` with one strong signal and the other neutral, ``low``
    otherwise. A column whose header says nothing is suggested only when its
    kind is one that values alone reveal (a phone, an e-mail, a date and so on)
    and equals the field kind.

    A column feeds at most one field. Candidates are taken from the highest
    score down, ties going to the larger share, the longer alias, the leftmost
    column and the earlier field. A field that loses a column takes its next
    best candidate, and lists the columns it did not get in ``alternatives``.
    A required field that nothing relates to takes the one remaining column its
    kind accepts, with confidence ``low`` and the reason ``only_candidate``, and
    has no column and the reason ``required_field_unmatched`` when there is not
    exactly one.

    A profile with no header row ignores headers: only content signals count.

    Args:
        profile: the profile of the table.
        fields: the fields to fill. The library has no predefined field.

    Returns:
        A ``Mapping`` with one ``Choice`` per field, in declaration order, the
        indexes of the columns no field uses, and the header fingerprint.

    Raises:
        ValueError: if two fields have the same key.
    """
    check_fields(fields)
    has_header = profile.header_row is not None
    kind_fields = Counter(field.kind for field in fields)
    kind_columns = Counter(column.kind for column in profile.columns)

    candidates: list[tuple[int, Candidate]] = []
    for field_index, field in enumerate(fields):
        aliases = alias_table(field)
        unique = kind_fields[field.kind] == 1 and kind_columns[field.kind] == 1
        for column in profile.columns:
            found = score_column(
                column, field, aliases, has_header=has_header, kind_is_unique=unique
            )
            if found is not None:
                candidates.append((field_index, found))
    candidates.sort(key=_order)

    taken_fields: dict[int, Candidate] = {}
    taken_columns: set[int] = set()
    for field_index, candidate in candidates:
        if field_index in taken_fields or candidate.column in taken_columns:
            continue
        taken_fields[field_index] = candidate
        taken_columns.add(candidate.column)

    fallback = _only_candidates(profile.columns, fields, taken_fields, taken_columns)
    choices = []
    for field_index, field in enumerate(fields):
        alternatives = tuple(
            Alternative(c.column, c.confidence)
            for i, c in candidates
            if i == field_index
            and (field_index not in taken_fields or c.column != taken_fields[field_index].column)
        )
        won = taken_fields.get(field_index)
        if won is not None:
            choices.append(Choice(field.key, won.column, won.confidence, won.reasons, alternatives))
        elif field_index in fallback:
            choices.append(
                Choice(
                    field.key, fallback[field_index][0], Confidence.LOW, fallback[field_index][1]
                )
            )
        else:
            reasons = (Reason(ReasonCode.REQUIRED_FIELD_UNMATCHED),) if field.required else ()
            choices.append(Choice(field.key, None, None, reasons, alternatives))

    used = {choice.column for choice in choices if choice.column is not None}
    unmapped = tuple(column.index for column in profile.columns if column.index not in used)
    return Mapping(tuple(choices), unmapped, fingerprint_of(profile))


_TEXT_FALLBACK = frozenset({Kind.TEXT, Kind.NAME, Kind.CATEGORY, Kind.INTEGER})


def _fallback_kinds(kind: Kind) -> frozenset[Kind]:
    """Column kinds a required field may take as the only candidate.

    A text field accepts every kind when a header matches, but as a fallback with
    no header signal it takes only text-like columns, so a lone date column is
    never guessed into it.
    """
    if kind is Kind.TEXT:
        return _TEXT_FALLBACK
    return frozenset({kind, *ACCEPTS.get(kind, frozenset())})


def _only_candidates(
    columns: tuple[ColumnProfile, ...],
    fields: Sequence[Field],
    taken_fields: dict[int, Candidate],
    taken_columns: set[int],
) -> dict[int, tuple[int, tuple[Reason, ...]]]:
    """For required fields left unmatched, the single remaining column they accept."""
    result: dict[int, tuple[int, tuple[Reason, ...]]] = {}
    used = set(taken_columns)
    for field_index, field in enumerate(fields):
        if field_index in taken_fields or not field.required:
            continue
        accepted = _fallback_kinds(field.kind)
        remaining = [
            c
            for c in columns
            if c.index not in used and c.filled and c.kind in accepted and not is_line_header(c)
        ]
        if len(remaining) != 1:
            continue
        column = remaining[0]
        used.add(column.index)
        fits = Reason(
            ReasonCode.CONTENT_FITS_KIND,
            {"kind": str(column.kind), "share": round(column.kind_share, 4)},
        )
        result[field_index] = (column.index, (fits, Reason(ReasonCode.ONLY_CANDIDATE)))
    return result
