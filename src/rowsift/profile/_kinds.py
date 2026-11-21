"""Kind inference: which kind most of a column's values fit."""

from __future__ import annotations

import re
from collections.abc import Iterable

from rowsift import clean
from rowsift.clean import CleanOptions, mask
from rowsift.profile._types import RunnerUp
from rowsift.types import ChangeCode, Kind

__all__ = ["display", "infer_kind", "looks_like_data"]

# Most specific first. At equal footing the earlier kind wins, so a column of
# CPFs is a cpf and not an integer, and phones beat integers.
_ORDER: tuple[Kind, ...] = (
    Kind.CPF,
    Kind.CNPJ,
    Kind.EMAIL,
    Kind.PHONE,
    Kind.DATETIME,
    Kind.DATE,
    Kind.DAY_MONTH,
    Kind.TIME,
    Kind.BOOLEAN,
    Kind.POSTAL_CODE,
    Kind.MONEY,
    Kind.INTEGER,
    Kind.DECIMAL,
)

# What a header cell never looks like. A boolean word is a plausible header.
_DATA_KINDS = tuple(kind for kind in _ORDER if kind is not Kind.BOOLEAN)

# Kinds that identify a person. A value of a column of another kind that fits one of
# them is masked as that kind, so a mixed column does not show it in clear.
_PERSONAL: tuple[Kind, ...] = (Kind.CPF, Kind.CNPJ, Kind.EMAIL, Kind.PHONE)
_HIDDEN = "***"

# No value of any kind is longer than an e-mail address can be, so a longer cell is
# never run through the cleaners. It bounds the cost of a column of long text.
_MAX_VALUE_CHARS = 254
# Personal data inside free text: an e-mail address, or a run of 10 or more digits
# that a phone number or a tax id would make, written with the usual separators.
_EMBEDDED = re.compile(r"@|[0-9](?:[ .()\-]?[0-9]){9}")

_POSTAL_SHAPE = re.compile(r"[0-9]{5}-?[0-9]{3}")
_CURRENCY = re.compile(r"R\$|US\$|BRL|USD|EUR|[$€£]", re.IGNORECASE)

# A cleaner may accept a value by a route that says nothing about the column:
# these changes mark a fit that is not evidence for the kind.
_NOT_EVIDENCE: dict[Kind, frozenset[ChangeCode]] = {
    Kind.DATE: frozenset({ChangeCode.SERIAL_DATE_CONVERTED}),
    Kind.DATETIME: frozenset({ChangeCode.SERIAL_DATE_CONVERTED, ChangeCode.TIME_DEFAULTED}),
    Kind.DAY_MONTH: frozenset({ChangeCode.YEAR_DISCARDED}),
    Kind.POSTAL_CODE: frozenset({ChangeCode.LEADING_ZEROS_RESTORED}),
}


def fits(text: str, kind: Kind, options: CleanOptions) -> bool:
    """Whether ``text`` is a value of ``kind`` that the column can be said to hold.

    A spreadsheet serial number is not a date here, a bare date is not a
    datetime, a full date is not a day and month, and a postal code that lost
    its leading zero is not a postal code: each would turn a column of plain
    numbers or dates into something else. Money needs a currency symbol and a
    postal code is written as 8 digits, with or without one hyphen.
    """
    if len(text) > _MAX_VALUE_CHARS:
        return False
    if kind is Kind.EMAIL:
        if "@" not in text:
            return False
    elif kind is not Kind.BOOLEAN and not any("0" <= char <= "9" for char in text):
        return False  # every other kind is written with at least one digit
    if kind is Kind.MONEY and not _CURRENCY.search(text):
        return False
    if kind is Kind.POSTAL_CODE and not _POSTAL_SHAPE.fullmatch(text.strip()):
        return False  # the cleaner tolerates any separator, a date of 8 digits would pass
    result = clean.value(text, kind, options)
    if result.issue is not None or result.value is None:
        return False
    blocked = _NOT_EVIDENCE.get(kind, frozenset())
    return not any(change.code in blocked for change in result.changes)


def looks_like_data(text: str, options: CleanOptions) -> bool:
    """Whether a cell holds a value that a header would not: a number, date, id and so on."""
    return any(fits(text, kind, options) for kind in _DATA_KINDS)


def infer_kind(
    values: Iterable[str], threshold: float, options: CleanOptions
) -> tuple[Kind, float, RunnerUp | None]:
    """The kind of a column from its non-empty values, with its share and runner-up.

    The kind is the first of the candidates, most specific first, that at least
    ``threshold`` of ``values`` fit. When none does it is ``text``, which every
    value fits. The runner-up is the other candidate with the highest share
    above zero, the more specific one on a tie.

    ``0`` and ``1`` are boolean literals and ``boolean`` comes before ``integer``,
    so a column holding only 0 and 1 is a ``boolean``, and the kind turns
    ``integer`` as soon as another number appears. The ``integer`` share and the
    runner-up report the other reading.
    """
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    total = sum(counts.values())
    if total == 0:
        return Kind.TEXT, 0.0, None
    shares: dict[Kind, float] = {}
    for kind in _ORDER:
        fitting = sum(count for value, count in counts.items() if fits(value, kind, options))
        shares[kind] = fitting / total
    chosen = next((kind for kind in _ORDER if shares[kind] >= threshold), None)
    others = [kind for kind in _ORDER if kind is not chosen and shares[kind] > 0]
    best = max(others, key=lambda kind: shares[kind], default=None)
    runner_up = RunnerUp(best, shares[best]) if best is not None else None
    if chosen is None:
        return Kind.TEXT, 1.0, runner_up
    return chosen, shares[chosen], runner_up


def _accepted(text: str, kind: Kind, options: CleanOptions) -> bool:
    """Whether the cleaner of ``kind`` takes ``text``, whatever route it takes."""
    if len(text) > _MAX_VALUE_CHARS:
        return False
    result = clean.value(text, kind, options)
    return result.issue is None and result.value is not None


def display(text: str, kind: Kind, options: CleanOptions) -> str:
    """``text`` as it is safe to show, given the kind of its column.

    A column of a personal kind (phone, CPF, CNPJ, e-mail, name) masks each
    value by that kind, and a value that does not have the shape of the kind is
    replaced by a fixed placeholder, so neither its length nor its words show.

    In any other column each value is judged by itself. A value that fits a
    personal kind is masked as that kind, so a column that fell short of the
    threshold, or mixes phones with notes, does not show the phones in clear. A
    value with an e-mail address or a run of 10 or more digits inside it is the
    placeholder. In a ``text`` column every other value is returned as written;
    in a column of a typed kind (a date, an integer) a value the kind does not
    take is the placeholder too, so a stray name is not shown.

    A person's name in a ``text`` column is not recognized: ``profile`` never
    infers ``name``, because no rule tells a name from free text with certainty.
    """
    if kind is Kind.NAME:
        return mask(text, kind)
    if kind in _PERSONAL:
        return mask(text, kind) if fits(text, kind, options) else _HIDDEN
    embedded = _EMBEDDED.search(text) is not None
    if kind is not Kind.TEXT and not embedded and _accepted(text, kind, options):
        return text
    personal = next((k for k in _PERSONAL if fits(text, k, options)), None)
    if personal is not None:
        return mask(text, personal)
    if embedded:
        return _HIDDEN
    return text if kind is Kind.TEXT else _HIDDEN
