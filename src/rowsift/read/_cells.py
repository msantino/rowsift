"""The stable rules that turn a workbook cell value into text."""

from __future__ import annotations

import datetime
from decimal import Decimal

__all__ = ["cell_text"]


# Every integer up to 2**53 is exact in a float.
_EXACT_INTEGER = 2**53
# Half a millisecond: the float error of a spreadsheet serial that is absorbed.
_FLOAT_ERROR = datetime.timedelta(microseconds=500)
_ZERO = datetime.timedelta(0)


def _float_text(value: float) -> str:
    if value != value or value in (float("inf"), float("-inf")):
        return str(value)
    if value.is_integer() and abs(value) <= _EXACT_INTEGER:
        return str(int(value))
    # Past 2**53 a float no longer holds every digit of the integer it prints as,
    # so only the first 15 significant digits are kept.
    text = format(value, ".15g")
    if "e" in text:
        # Plain digits, never scientific notation, so a long number stays readable.
        return format(Decimal(text), "f")
    return text


def _duration_text(value: datetime.timedelta) -> str:
    # The same half millisecond of float error is absorbed as for a time of day.
    magnitude = abs(value) + _FLOAT_ERROR
    total = int(magnitude.total_seconds())
    sign = "-" if value < _ZERO and total > 0 else ""
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{sign}{hours:02d}:{minutes:02d}:{seconds:02d}"


def _to_second(value: datetime.datetime) -> datetime.datetime:
    # Spreadsheet serials are floats: a stored 13:45:30 comes back a hair off.
    # Only that error is absorbed (half a millisecond, upward), then the fraction
    # is cut. A value within half a millisecond below a second boundary reads as
    # that boundary, so it can carry into the next second, minute or day. The
    # last representable datetime has nothing after it and is only cut.
    if value > datetime.datetime.max - _FLOAT_ERROR:
        return value.replace(microsecond=0)
    return (value + _FLOAT_ERROR).replace(microsecond=0)


def cell_text(value: object) -> str:
    """Text of one workbook cell value.

    A date is ``YYYY-MM-DD`` and a date with a time of day is
    ``YYYY-MM-DDTHH:MM:SS``. A whole number has no decimal part, a decimal
    number has at most 15 significant digits and never uses scientific
    notation (a whole number beyond 2**53 keeps its first 15 significant digits),
    a boolean is ``true`` or ``false`` and an empty cell is an empty string. A
    datetime at exactly midnight is the date alone, a time of day is
    ``HH:MM:SS`` and a duration is ``HH:MM:SS`` with hours that may pass 24.
    Fractions of a second are cut, after absorbing half a millisecond of float
    error upward: a value within half a millisecond below a second boundary reads
    as that boundary, so a time of day of 23:59:59.9995 or later wraps to
    ``00:00:00`` and a datetime carries into the next day. A value of any other
    type is converted with ``str``. An integer of more than 4300 digits raises
    ``ValueError`` (the limit of ``str`` on an ``int``), which the workbook readers
    report as an unsupported file.
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return value
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return _float_text(value)
    if isinstance(value, datetime.datetime):
        value = _to_second(value)
        if value.time() == datetime.time(0):
            return value.date().isoformat()
        return value.isoformat()
    if isinstance(value, datetime.date):
        return value.isoformat()
    if isinstance(value, datetime.time):
        moment = datetime.datetime.combine(datetime.date(2000, 1, 1), value)
        return _to_second(moment).time().isoformat()
    if isinstance(value, datetime.timedelta):
        return _duration_text(value)
    return str(value)
