"""Options shared by every cleaner."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

__all__ = ["CleanOptions", "DateOrder", "DecimalSeparator", "NameCase"]

DateOrder = Literal["dmy", "mdy"]
"""Order of the day and month in a numeric date such as ``03/04/1990``."""

DecimalSeparator = Literal[",", "."]
"""The character that separates the integer part from the decimals."""

NameCase = Literal["title", "keep"]
"""``title`` recases names written entirely in one case, ``keep`` never does."""


@dataclass(frozen=True, slots=True, kw_only=True)
class CleanOptions:
    """Every knob of the cleaners. All are passed by keyword.

    Attributes:
        region: two-letter region of phone numbers and postal codes. ``BR`` is
            implemented natively. Another region for a phone needs the ``phone``
            extra.
        date_order: ``dmy`` (default) or ``mdy``, for numeric dates whose year
            comes last. A date that starts with a four-digit year is always
            read as year, month, day.
        decimal_separator: ``,`` (default) or ``.``. The other character is the
            thousands separator.
        two_digit_year_pivot: a two-digit year from 00 up to the pivot belongs
            to the 2000s, a larger one to the 1900s.
        insert_ninth_digit: insert the ninth digit into an 8-digit mobile
            number and report it. When false, such a number is an issue.
        name_case: ``title`` or ``keep``.
        require_mobile: a landline number is an issue.
        one_of: allowed values of a ``category``. ``None`` means any text.

    Raises:
        ValueError: if a value is outside what the attribute allows.
    """

    region: str = "BR"
    date_order: DateOrder = "dmy"
    decimal_separator: DecimalSeparator = ","
    two_digit_year_pivot: int = 30
    insert_ninth_digit: bool = True
    name_case: NameCase = "title"
    require_mobile: bool = False
    one_of: tuple[str, ...] | None = None

    def __post_init__(self) -> None:
        if not (isinstance(self.region, str) and len(self.region) == 2 and self.region.isalpha()):
            raise ValueError("region must be a two-letter code")
        object.__setattr__(self, "region", self.region.upper())
        if self.date_order not in ("dmy", "mdy"):
            raise ValueError("date_order must be 'dmy' or 'mdy'")
        if self.decimal_separator not in (",", "."):
            raise ValueError("decimal_separator must be ',' or '.'")
        pivot = self.two_digit_year_pivot
        if type(pivot) is not int or not 0 <= pivot <= 99:
            raise ValueError("two_digit_year_pivot must be an int between 0 and 99")
        if self.name_case not in ("title", "keep"):
            raise ValueError("name_case must be 'title' or 'keep'")
        for flag in ("insert_ninth_digit", "require_mobile"):
            if type(getattr(self, flag)) is not bool:
                raise ValueError(f"{flag} must be a bool")
        if self.one_of is not None:
            if isinstance(self.one_of, str) or not all(
                isinstance(item, str) for item in self.one_of
            ):
                raise ValueError("one_of must be a sequence of strings")
            object.__setattr__(self, "one_of", tuple(self.one_of))
