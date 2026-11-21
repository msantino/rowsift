"""Scoring one column against one field, from the header and from the content."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from rowsift.map._fields import Field
from rowsift.profile import ColumnProfile, normalize_header
from rowsift.types import Confidence, Kind, Reason, ReasonCode

__all__ = ["Candidate", "HeaderMatch", "alias_table", "is_line_header", "score_column"]

SPECIFIC_KINDS = frozenset(
    {
        Kind.PHONE,
        Kind.EMAIL,
        Kind.CPF,
        Kind.CNPJ,
        Kind.POSTAL_CODE,
        Kind.DATE,
        Kind.DAY_MONTH,
        Kind.TIME,
        Kind.DATETIME,
    }
)
"""Kinds a column can only take by what its values look like. A column of one of
these kinds relates to a field of the same kind even when the header says nothing."""

ACCEPTS: dict[Kind, frozenset[Kind]] = {
    Kind.TEXT: frozenset(Kind) - {Kind.TEXT},
    Kind.NAME: frozenset({Kind.TEXT, Kind.CATEGORY}),
    Kind.CATEGORY: frozenset({Kind.TEXT, Kind.NAME, Kind.INTEGER, Kind.BOOLEAN}),
    Kind.INTEGER: frozenset({Kind.BOOLEAN}),
    Kind.DECIMAL: frozenset({Kind.INTEGER}),
    Kind.MONEY: frozenset({Kind.DECIMAL, Kind.INTEGER}),
    Kind.DATE: frozenset({Kind.DATETIME}),
    Kind.DATETIME: frozenset({Kind.DATE}),
    Kind.DAY_MONTH: frozenset({Kind.DATE}),
}
"""For a field kind, the other column kinds whose values the cleaner can still read.
A text field reads every kind, since any cell is text."""

_EXACT_POINTS = 4
_CONTAINS_POINTS = 2
_FIT_EXACT_POINTS = 2
_FIT_ACCEPTED_POINTS = 1
_CONFLICT_POINTS = -1


class HeaderMatch(Enum):
    """How a header relates to the aliases of a field."""

    NONE = auto()
    CONTAINS = auto()
    EXACT = auto()


class _Content(Enum):
    NEUTRAL = auto()
    FITS = auto()
    CONFLICTS = auto()


@dataclass(frozen=True, slots=True)
class Candidate:
    """One column as a candidate for one field.

    Candidates are ordered by the higher score, then the larger share, then the
    longer alias. ``confidence`` and ``reasons`` are what the choice carries if
    the candidate wins.
    """

    column: int
    score: int
    share: float
    alias_tokens: int
    confidence: Confidence
    reasons: tuple[Reason, ...]


def alias_table(field: Field) -> tuple[str, ...]:
    """The folded aliases of a field: its declared aliases and its key."""
    folded = (normalize_header(alias) for alias in (*field.aliases, field.key))
    return tuple(dict.fromkeys(alias for alias in folded if alias))


_MAX_DELIMITERS_IN_HEADER = 2
"""A header with more delimiter characters than this is a whole line read as one
cell, not a name, so it matches no alias."""

_HEADER_DELIMITERS = frozenset(";,|\t")


def is_line_header(column: ColumnProfile) -> bool:
    """Whether the header is a whole line read as one cell rather than a name."""
    return sum(char in _HEADER_DELIMITERS for char in column.header) > _MAX_DELIMITERS_IN_HEADER


def _header_match(column: ColumnProfile, aliases: tuple[str, ...]) -> tuple[HeaderMatch, str, int]:
    """The best match of the header against the aliases: kind, alias, alias tokens."""
    if not column.header or not column.normalized_header or is_line_header(column):
        return HeaderMatch.NONE, "", 0
    header = column.normalized_header
    header_tokens = set(header.split())
    best = (HeaderMatch.NONE, "", 0)
    for alias in aliases:
        tokens = alias.split()
        if alias == header:
            return HeaderMatch.EXACT, alias, len(tokens)
        if set(tokens) <= header_tokens and len(tokens) > best[2]:
            best = (HeaderMatch.CONTAINS, alias, len(tokens))
    return best


def _content(column: ColumnProfile, field: Field) -> tuple[_Content, float, bool]:
    """Whether the content fits the field: verdict, share, and whether the kind is equal."""
    if column.filled == 0:
        return _Content.NEUTRAL, 0.0, False
    if column.kind is field.kind:
        return _Content.FITS, column.kind_share, True
    if column.kind in ACCEPTS.get(field.kind, frozenset()):
        return _Content.FITS, column.kind_share, False
    runner = column.runner_up
    share = runner.share if runner is not None and runner.kind is field.kind else 0.0
    return _Content.CONFLICTS, share, False


def score_column(
    column: ColumnProfile,
    field: Field,
    aliases: tuple[str, ...],
    *,
    has_header: bool,
    kind_is_unique: bool,
) -> Candidate | None:
    """Score a column for a field, or ``None`` when nothing relates them.

    A header signal is an alias equal to the header (exact) or all of whose words
    appear in it (contains). A content signal is the column kind fitting the
    field kind. A column whose header is a whole line (see ``is_line_header``)
    is a candidate for no field. ``high`` needs an exact header and fitting content. With no
    header signal, only a column whose kind is the field kind, and a kind that
    values alone can reveal, is a candidate: ``medium`` when it is the only
    column and the only field of that kind, ``low`` otherwise.

    ``has_header`` is false for a profile with no header row, where headers carry
    no meaning. ``kind_is_unique`` says whether the field is the only declared
    field of its kind and the column the only column of that kind.
    """
    if has_header and is_line_header(column):
        return None
    match, alias, alias_tokens = (
        _header_match(column, aliases) if has_header else (HeaderMatch.NONE, "", 0)
    )
    content, share, exact_kind = _content(column, field)
    fits = Reason(
        ReasonCode.CONTENT_FITS_KIND, {"kind": str(column.kind), "share": round(share, 4)}
    )
    conflicts = Reason(
        ReasonCode.CONTENT_CONFLICTS_WITH_KIND,
        {
            "column_kind": str(column.kind),
            "field_kind": str(field.kind),
            "share": round(share, 4),
        },
    )

    if match is HeaderMatch.NONE:
        if content is not _Content.FITS or not exact_kind or field.kind not in SPECIFIC_KINDS:
            return None
        confidence = Confidence.MEDIUM if kind_is_unique else Confidence.LOW
        return Candidate(column.index, _FIT_EXACT_POINTS, share, 0, confidence, (fits,))

    exact = match is HeaderMatch.EXACT
    header_reason = Reason(
        ReasonCode.HEADER_MATCHES_ALIAS if exact else ReasonCode.HEADER_CONTAINS_ALIAS,
        {"alias": alias},
    )
    score = _EXACT_POINTS if exact else _CONTAINS_POINTS
    if content is _Content.FITS:
        score += _FIT_EXACT_POINTS if exact_kind else _FIT_ACCEPTED_POINTS
        confidence = Confidence.HIGH if exact else Confidence.MEDIUM
        return Candidate(
            column.index, score, share, alias_tokens, confidence, (header_reason, fits)
        )
    if content is _Content.NEUTRAL:
        confidence = Confidence.MEDIUM if exact else Confidence.LOW
        return Candidate(column.index, score, 0.0, alias_tokens, confidence, (header_reason,))
    score += _CONFLICT_POINTS
    return Candidate(
        column.index, score, share, alias_tokens, Confidence.LOW, (header_reason, conflicts)
    )
