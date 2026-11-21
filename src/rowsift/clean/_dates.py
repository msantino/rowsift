"""Date, day and month, time and datetime cleaners."""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass

from rowsift.clean._common import change, fail, fold
from rowsift.clean._options import CleanOptions
from rowsift.types import Change, ChangeCode, Cleaned, DayMonth, IssueCode

__all__ = ["date", "datetime", "day_month", "time"]

_MONTHS: dict[str, int] = {}
for _number, _names in enumerate(
    (
        ("janeiro", "jan", "january"),
        ("fevereiro", "fev", "feb", "february"),
        ("marco", "mar", "march"),
        ("abril", "abr", "apr", "april"),
        ("maio", "mai", "may"),
        ("junho", "jun", "june"),
        ("julho", "jul", "july"),
        ("agosto", "ago", "aug", "august"),
        ("setembro", "set", "sep", "sept", "september"),
        ("outubro", "out", "oct", "october"),
        ("novembro", "nov", "november"),
        ("dezembro", "dez", "dec", "december"),
    ),
    start=1,
):
    for _name in _names:
        _MONTHS[_name] = _number

_ASCII_DIGITS = "0123456789"
_SERIAL_MIN = 10_000  # 1927-05-18. Smaller numbers are far more likely to be something else.
_SERIAL_MAX = 2_958_465  # 9999-12-31
_SERIAL_EPOCH = dt.date(1899, 12, 30)  # valid for every serial after the 1900 leap-year bug

_YMD = re.compile(r"([0-9]{4})([/.\-])([0-9]{1,2})\2([0-9]{1,2})")
_NUMERIC = re.compile(r"([0-9]{1,2})([/.\-])([0-9]{1,2})\2([0-9]{2}|[0-9]{4})")
_NUMERIC_NO_YEAR = re.compile(r"([0-9]{1,2})([/.\-])([0-9]{1,2})")
_WORDS_ALLOWED = re.compile(r"[a-z0-9 ,./\-]+")
_TOKEN = re.compile(r"[a-z]+|[0-9]+")
_SERIAL = re.compile(r"[0-9]+(?:\.[0-9]+)?")
_TIME = re.compile(
    r"(?P<hour>[0-9]{1,2})(?:(?::(?P<minute>[0-9]{2})(?::(?P<second>[0-9]{2})(?:\.(?P<fraction>[0-9]{1,6}))?)?)"
    r"|h(?P<hminute>[0-9]{2})?|(?=\s*[ap]\.?m\.?\Z))\s*(?P<meridiem>[ap]\.?m\.?)?",
    re.IGNORECASE,
)
_TRAILING_TIME = re.compile(
    r"^(?P<date>.*?)(?:\s+|T)"
    r"(?P<time>[0-9]{1,2}(?::[0-9]{2}.*|h[0-9]{0,2}\s*|\s*[ap]\.?m\.?\s*))$",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class _Parts:
    """A date read from text: ``year`` is ``None`` when the text has none."""

    day: int
    month: int
    year: int | None
    expanded_from: int | None = None


def _expand_year(two_digits: int, pivot: int) -> int:
    return 2000 + two_digits if two_digits <= pivot else 1900 + two_digits


def _parse_parts(text: str, options: CleanOptions) -> _Parts | None:
    """Day, month and year from numeric, ISO or month-name text. ``None`` if no shape fits."""
    ymd = _YMD.fullmatch(text)
    if ymd:
        return _Parts(int(ymd.group(4)), int(ymd.group(3)), int(ymd.group(1)))
    numeric = _NUMERIC.fullmatch(text)
    if numeric:
        first, second, year_text = int(numeric.group(1)), int(numeric.group(3)), numeric.group(4)
        day, month = (first, second) if options.date_order == "dmy" else (second, first)
        if len(year_text) == 2:
            year = _expand_year(int(year_text), options.two_digit_year_pivot)
            return _Parts(day, month, year, expanded_from=int(year_text))
        return _Parts(day, month, int(year_text))
    short = _NUMERIC_NO_YEAR.fullmatch(text)
    if short:
        first, second = int(short.group(1)), int(short.group(3))
        day, month = (first, second) if options.date_order == "dmy" else (second, first)
        return _Parts(day, month, None)
    return _parse_words(text, options)


def _parse_words(text: str, options: CleanOptions) -> _Parts | None:
    if any(char.isdigit() and char not in _ASCII_DIGITS for char in text):
        return None  # fold() would turn other scripts' digits into ASCII ones
    folded = fold(text)
    if not _WORDS_ALLOWED.fullmatch(folded):
        return None
    tokens = [t for t in _TOKEN.findall(folded) if t not in ("de", "of")]
    shapes = "".join("m" if t in _MONTHS else "n" if t.isdigit() else "?" for t in tokens)
    if "?" in shapes:
        return None
    year_token: str | None
    if shapes in ("nm", "nmn"):
        day_token, month_token = tokens[0], tokens[1]
        year_token = tokens[2] if shapes == "nmn" else None
    elif shapes in ("mn", "mnn"):
        month_token, day_token = tokens[0], tokens[1]
        year_token = tokens[2] if shapes == "mnn" else None
    else:
        return None
    if len(day_token) > 2:
        return None
    year: int | None
    expanded: int | None
    if year_token is None:
        year, expanded = None, None
    elif len(year_token) == 4:
        year, expanded = int(year_token), None
    elif len(year_token) == 2:
        year = _expand_year(int(year_token), options.two_digit_year_pivot)
        expanded = int(year_token)
    else:
        return None
    return _Parts(int(day_token), _MONTHS[month_token], year, expanded)


def _build(parts: _Parts) -> dt.date | None:
    assert parts.year is not None
    try:
        return dt.date(parts.year, parts.month, parts.day)
    except ValueError:
        return None


def _serial(text: str, *, allow_fraction: bool) -> tuple[dt.date, float] | None:
    """A spreadsheet serial number as a date and the fraction of the day."""
    if not _SERIAL.fullmatch(text):
        return None
    whole, _, fraction = text.partition(".")
    if len(whole) > len(str(_SERIAL_MAX)):
        return None  # also keeps int() away from absurdly long digit runs
    if fraction.strip("0") and not allow_fraction:
        return None
    number = int(whole)
    if not _SERIAL_MIN <= number <= _SERIAL_MAX:
        return None
    return _SERIAL_EPOCH + dt.timedelta(days=number), float("0." + fraction) if fraction else 0.0


def _date_from_text(text: str, options: CleanOptions) -> Cleaned[dt.date]:
    serial = _serial(text, allow_fraction=False)
    if serial is not None:
        return Cleaned(serial[0], changes=(change(ChangeCode.SERIAL_DATE_CONVERTED),))
    parts = _parse_parts(text, options)
    if parts is None or parts.year is None:
        return fail(IssueCode.NOT_A_DATE)
    built = _build(parts)
    if built is None:
        return fail(IssueCode.INVALID_DATE)
    changes: tuple[Change, ...] = ()
    if parts.expanded_from is not None:
        changes = (change(ChangeCode.TWO_DIGIT_YEAR_EXPANDED, year=parts.year),)
    return Cleaned(built, changes=changes)


def date(value: str, options: CleanOptions | None = None) -> Cleaned[dt.date]:
    """A calendar date as ``datetime.date``.

    Accepted: numeric dates with ``/``, ``-`` or ``.`` in the order of
    ``options.date_order`` (day first by default); ISO dates, which start with a
    four-digit year; dates with month names or abbreviations in Portuguese or
    English (``12 de março de 1988``, ``12-mar-88``, ``March 12, 1988``); and
    spreadsheet serial numbers from 10000 to 2958465, reported as
    ``serial_date_converted``. A two-digit year is resolved with
    ``options.two_digit_year_pivot`` and reported as ``two_digit_year_expanded``.
    A date that does not exist is the issue ``invalid_date``. Text that is not a
    date, including a date with no year, is the issue ``not_a_date``.
    """
    options = options or CleanOptions()
    text = value.strip()
    if not text:
        return Cleaned()
    return _date_from_text(text, options)


def day_month(value: str, options: CleanOptions | None = None) -> Cleaned[DayMonth]:
    """A day and a month with no year, such as a birthday.

    Accepts the forms of ``date`` with the year left out (``12/03``,
    ``12-mar``, ``12 de março``). A full date is accepted too: the year is
    discarded and reported as ``year_discarded``, after checking that the date
    exists. No year is ever invented, and 29 February is valid. A day that does
    not exist in its month is the issue ``invalid_date``; text that is neither
    is ``not_a_date``.
    """
    options = options or CleanOptions()
    text = value.strip()
    if not text:
        return Cleaned()
    parts = _parse_parts(text, options)
    if parts is None:
        return fail(IssueCode.NOT_A_DATE)
    if parts.year is not None:
        built = _build(parts)
        if built is None:
            return fail(IssueCode.INVALID_DATE)
        return Cleaned(
            DayMonth(built.day, built.month), changes=(change(ChangeCode.YEAR_DISCARDED),)
        )
    try:
        return Cleaned(DayMonth(parts.day, parts.month))
    except ValueError:
        return fail(IssueCode.INVALID_DATE)


def _time_from_text(text: str) -> dt.time | None:
    match = _TIME.fullmatch(text.strip())
    if match is None:
        return None
    hour = int(match["hour"])
    minute = int(match["minute"] or match["hminute"] or 0)
    second = int(match["second"] or 0)
    micro = int((match["fraction"] or "").ljust(6, "0") or 0)
    meridiem = match["meridiem"]
    if meridiem:
        if not 1 <= hour <= 12:
            return None
        hour = hour % 12 + (12 if meridiem[0].lower() == "p" else 0)
    try:
        return dt.time(hour, minute, second, micro)
    except ValueError:
        return None


def time(value: str, options: CleanOptions | None = None) -> Cleaned[dt.time]:
    """A time of day as ``datetime.time``.

    Accepts ``H:MM``, ``HH:MM:SS`` with optional fractional seconds, ``9h30``,
    ``9h``, and a 12-hour clock with ``am`` or ``pm``. No time zone is read.
    Anything else, or a value out of range, is the issue ``not_a_time``.
    """
    text = value.strip()
    if not text:
        return Cleaned()
    parsed = _time_from_text(text)
    return Cleaned(parsed) if parsed is not None else fail(IssueCode.NOT_A_TIME)


def datetime(value: str, options: CleanOptions | None = None) -> Cleaned[dt.datetime]:
    """A date and a time of day as a naive ``datetime.datetime``.

    The date part follows ``date`` and the time part follows ``time``, separated
    by a space or ``T``. A spreadsheet serial number with a fraction is
    accepted. A date with no time becomes midnight and reports
    ``time_defaulted``. Time zones are not read.
    """
    options = options or CleanOptions()
    text = value.strip()
    if not text:
        return Cleaned()
    serial = _serial(text, allow_fraction=True)
    if serial is not None:
        seconds = round(serial[1] * 86_400)
        moment = dt.datetime.combine(serial[0], dt.time()) + dt.timedelta(seconds=seconds)
        return Cleaned(moment, changes=(change(ChangeCode.SERIAL_DATE_CONVERTED),))
    split = _TRAILING_TIME.fullmatch(text)
    if split is None:
        day = _date_from_text(text, options)
        if day.value is None:
            return Cleaned(issue=day.issue)
        return Cleaned(
            dt.datetime.combine(day.value, dt.time()),
            changes=(*day.changes, change(ChangeCode.TIME_DEFAULTED)),
        )
    day = _date_from_text(split["date"].strip(), options)
    if day.value is None:
        return fail(day.issue.code) if day.issue else Cleaned()
    clock = _time_from_text(split["time"])
    if clock is None:
        return fail(IssueCode.NOT_A_TIME)
    return Cleaned(dt.datetime.combine(day.value, clock), changes=day.changes)
