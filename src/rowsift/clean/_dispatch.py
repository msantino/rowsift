"""One function that cleans a value by its kind."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from rowsift.clean._dates import date, datetime, day_month, time
from rowsift.clean._identifiers import cnpj, cpf, email, postal_code
from rowsift.clean._numbers import decimal, integer, money
from rowsift.clean._options import CleanOptions
from rowsift.clean._phone import phone
from rowsift.clean._text import boolean, category, name, text
from rowsift.types import Cleaned, Kind

__all__ = ["value"]

_CLEANERS: dict[Kind, Callable[[str, CleanOptions | None], Cleaned[Any]]] = {
    Kind.TEXT: text,
    Kind.NAME: name,
    Kind.INTEGER: integer,
    Kind.DECIMAL: decimal,
    Kind.MONEY: money,
    Kind.BOOLEAN: boolean,
    Kind.DATE: date,
    Kind.DAY_MONTH: day_month,
    Kind.TIME: time,
    Kind.DATETIME: datetime,
    Kind.PHONE: phone,
    Kind.EMAIL: email,
    Kind.CPF: cpf,
    Kind.CNPJ: cnpj,
    Kind.POSTAL_CODE: postal_code,
    Kind.CATEGORY: category,
}


def value(text: str, kind: Kind, options: CleanOptions | None = None) -> Cleaned[Any]:
    """Clean ``text`` with the cleaner of ``kind``.

    The result is the one the kind's own cleaner returns, so every layer cleans
    every kind through this function. ``kind`` accepts a ``Kind`` or its string
    value.

    Raises:
        ValueError: if ``kind`` is not a ``Kind``.
        MissingExtraError: for a phone in a region that needs the ``phone`` extra.
    """
    return _CLEANERS[Kind(kind)](text, options)
