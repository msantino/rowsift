"""The fields a caller declares."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import KW_ONLY, dataclass

from rowsift.clean import CleanOptions
from rowsift.types import Kind

__all__ = ["Field"]


def _texts(name: str, values: Iterable[str]) -> tuple[str, ...]:
    if isinstance(values, str):
        raise TypeError(f"{name} must be a sequence of str, not a bare str")
    items = tuple(values)
    if any(type(item) is not str for item in items):
        raise TypeError(f"{name} must hold only str")
    return items


@dataclass(frozen=True, slots=True)
class Field:
    """A field the application wants filled from a column.

    The library declares no field: every field comes from the caller. The key
    of a field also counts as one of its aliases, so a field ``phone`` matches
    a column headed ``Phone`` without declaring the alias.

    Attributes:
        key: the name the application uses for the field. Unique among the
            fields passed together.
        kind: what the field holds.
        required: whether a row with no value for the field is rejected when the
            rows are sifted. A required field that no column fits is reported by
            ``suggest``.
        aliases: other headers the column may carry. Compared after the same
            folding as the headers (case, accents and punctuation ignored).
        one_of: the allowed values of a ``Kind.CATEGORY`` field, or ``None`` for
            any text. Only a category field may set it.
        options: the cleaning options for this field alone, or ``None`` to use
            the options of the call.

    Raises:
        TypeError: if the key is not ``str``, ``aliases`` or ``one_of`` is a bare
            ``str`` or holds a non-``str``, ``required`` is not ``bool`` or
            ``options`` is not a ``CleanOptions``.
        ValueError: if the key is empty, ``kind`` is not a ``Kind``, or ``one_of``
            is set on a field that is not a category.
    """

    key: str
    kind: Kind
    _: KW_ONLY
    required: bool = False
    aliases: tuple[str, ...] = ()
    one_of: tuple[str, ...] | None = None
    options: CleanOptions | None = None

    def __post_init__(self) -> None:
        if type(self.key) is not str:
            raise TypeError("key must be str")
        if not self.key.strip():
            raise ValueError("key must not be empty")
        object.__setattr__(self, "kind", Kind(self.kind))
        if type(self.required) is not bool:
            raise TypeError("required must be bool")
        object.__setattr__(self, "aliases", _texts("aliases", self.aliases))
        if self.one_of is not None:
            if self.kind is not Kind.CATEGORY:
                raise ValueError("one_of is only for a category field")
            object.__setattr__(self, "one_of", _texts("one_of", self.one_of))
        if self.options is not None and not isinstance(self.options, CleanOptions):
            raise TypeError("options must be a CleanOptions or None")
