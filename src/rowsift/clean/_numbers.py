"""Integer, decimal and money cleaners."""

from __future__ import annotations

import re
from decimal import Decimal

from rowsift.clean._common import change, fail
from rowsift.clean._options import CleanOptions
from rowsift.types import Change, ChangeCode, Cleaned, IssueCode

__all__ = ["decimal", "integer", "money"]

_CURRENCY = re.compile(r"R\$|US\$|BRL|USD|EUR|[$€£]", re.IGNORECASE)
_NUMBER_CHARS = re.compile(r"[0-9.,]+")
# Decimal precision of the default context, and well under the int/str digit limit.
_MAX_DIGITS = 38


def _groups_ok(integer_part: str, separator: str) -> bool:
    parts = integer_part.split(separator)
    return (
        bool(parts[0])
        and len(parts[0]) <= 3
        and all(len(part) == 3 for part in parts[1:])
        and "".join(parts).isdigit()
    )


def _unsigned(body: str, options: CleanOptions) -> tuple[str, bool] | None:
    """Digits with a ``.`` decimal point, and whether the options were contradicted."""
    decimal_sep: str = options.decimal_separator
    group_sep = "." if decimal_sep == "," else ","
    n_decimal, n_group = body.count(decimal_sep), body.count(group_sep)

    if n_decimal and n_group:
        point: str
        group: str
        if body.rfind(decimal_sep) > body.rfind(group_sep):
            point, group, inferred = decimal_sep, group_sep, False
        else:
            point, group, inferred = group_sep, decimal_sep, True
        integer_part, _, fraction = body.rpartition(point)
        if not fraction.isdigit() or point in integer_part or not _groups_ok(integer_part, group):
            return None
        return integer_part.replace(group, "") + "." + fraction, inferred
    if n_decimal == 1 and not n_group:
        integer_part, _, fraction = body.partition(decimal_sep)
        if not fraction.isdigit() or not (integer_part == "" or integer_part.isdigit()):
            return None
        return (integer_part or "0") + "." + fraction, False
    if n_decimal > 1:
        # The configured decimal character cannot repeat: read it as thousands.
        return (body.replace(decimal_sep, ""), True) if _groups_ok(body, decimal_sep) else None
    if n_group == 1:
        integer_part, _, fraction = body.partition(group_sep)
        grouped = len(fraction) == 3 and fraction.isdigit() and _groups_ok(integer_part, group_sep)
        if grouped and not integer_part.startswith("0"):
            return integer_part + fraction, False  # ambiguous: the options decide
        if not fraction.isdigit() or not (integer_part == "" or integer_part.isdigit()):
            return None
        return (integer_part or "0") + "." + fraction, True
    if n_group > 1:
        return (body.replace(group_sep, ""), False) if _groups_ok(body, group_sep) else None
    return (body, False) if body.isdigit() else None


def _parse(value: str, options: CleanOptions) -> tuple[Decimal, tuple[Change, ...]] | None:
    body = value.strip()
    parenthesized = body.startswith("(") and body.endswith(")")
    if parenthesized:
        body = body[1:-1]
    body = _CURRENCY.sub("", body).strip()
    minus = 0
    if body[:1] in ("+", "-"):
        minus += body[0] == "-"
        body = body[1:].strip()
    elif body[-1:] == "-":
        minus += 1
        body = body[:-1].strip()
    if parenthesized + minus > 1:
        return None  # two negative markers: never read as a positive number
    negative = bool(parenthesized or minus)
    if not _NUMBER_CHARS.fullmatch(body) or sum(c.isdigit() for c in body) > _MAX_DIGITS:
        return None
    parsed = _unsigned(body, options)
    if parsed is None:
        return None
    digits, inferred = parsed
    number = Decimal(digits)
    changes = (change(ChangeCode.SEPARATOR_INFERRED),) if inferred else ()
    # copy_negate keeps every digit: unary minus would round to the context precision.
    return (number.copy_negate() if negative else number), changes


def decimal(value: str, options: CleanOptions | None = None) -> Cleaned[Decimal]:
    """A number as a ``decimal.Decimal``.

    Currency symbols (``R$``, ``$``, ``BRL``...) and surrounding spaces are
    removed. A leading or trailing minus sign and parentheses mean negative.
    Thousands and decimal separators follow ``options.decimal_separator``. An
    input that is ambiguous under the options, such as ``1.234`` with the
    default comma, is read by the options. An input that contradicts them
    unambiguously, such as ``1,234.56``, is read as written and reports
    ``separator_inferred``. Exponent notation and any other text is the issue
    ``not_a_number``, and so is a number of more than 38 digits.
    """
    options = options or CleanOptions()
    if not value.strip():
        return Cleaned()
    parsed = _parse(value, options)
    if parsed is None:
        return fail(IssueCode.NOT_A_NUMBER)
    return Cleaned(parsed[0], changes=parsed[1])


def money(value: str, options: CleanOptions | None = None) -> Cleaned[Decimal]:
    """An amount of money as a ``decimal.Decimal``, parsed like ``decimal``.

    The amount is not rounded: the decimals written are the decimals returned.
    """
    return decimal(value, options)


def integer(value: str, options: CleanOptions | None = None) -> Cleaned[int]:
    """A whole number as an ``int``.

    Parsed like ``decimal``. A value with a non-zero fractional part is the
    issue ``not_a_number``, never truncated.
    """
    options = options or CleanOptions()
    if not value.strip():
        return Cleaned()
    parsed = _parse(value, options)
    if parsed is None or parsed[0] != parsed[0].to_integral_value():
        return fail(IssueCode.NOT_A_NUMBER)
    return Cleaned(int(parsed[0]), changes=parsed[1])
