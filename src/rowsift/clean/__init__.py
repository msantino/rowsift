"""Clean one value: the normalized value and what changed, or the reason it failed.

Every cleaner takes the text of a cell and an optional ``CleanOptions`` and
returns a ``Cleaned``: a ``value`` or an ``issue`` code, plus the ``changes``
made on the way. ``value`` cleans by ``Kind``. The ``mask`` functions make a
value safe to display.
"""

from rowsift.clean._dates import date, datetime, day_month, time
from rowsift.clean._dispatch import value
from rowsift.clean._identifiers import cnpj, cpf, email, postal_code
from rowsift.clean._mask import mask, mask_cnpj, mask_cpf, mask_email, mask_name, mask_phone
from rowsift.clean._numbers import decimal, integer, money
from rowsift.clean._options import CleanOptions
from rowsift.clean._phone import PhoneNumber, phone
from rowsift.clean._text import boolean, category, name, text

__all__ = [
    "CleanOptions",
    "PhoneNumber",
    "boolean",
    "category",
    "cnpj",
    "cpf",
    "date",
    "datetime",
    "day_month",
    "decimal",
    "email",
    "integer",
    "mask",
    "mask_cnpj",
    "mask_cpf",
    "mask_email",
    "mask_name",
    "mask_phone",
    "money",
    "name",
    "phone",
    "postal_code",
    "text",
    "time",
    "value",
]
