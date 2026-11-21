"""Small helpers shared by the cleaners. Private."""

from __future__ import annotations

import unicodedata
from typing import TypeVar

from rowsift.types import Change, ChangeCode, Cleaned, DataValue, Issue, IssueCode

T = TypeVar("T")


def fold(text: str, *, compatibility: bool = True) -> str:
    """Lowercase, accents removed, whitespace collapsed. For matching only.

    ``compatibility=False`` keeps compatibility forms such as a fullwidth digit apart.
    """
    decomposed = unicodedata.normalize("NFKD" if compatibility else "NFD", text.casefold())
    bare = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(bare.split())


def fail(code: IssueCode, **data: DataValue) -> Cleaned[T]:
    """A result that carries an issue and no value."""
    return Cleaned(issue=Issue(code, data))


def change(code: ChangeCode, **data: DataValue) -> Change:
    """A change with keyword data."""
    return Change(code, data)
