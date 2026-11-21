"""Header normalization and column names."""

from __future__ import annotations

import re
import unicodedata

__all__ = ["normalize_header"]

_NOT_ALPHANUMERIC = re.compile(r"[^0-9a-z]+")


def normalize_header(text: str) -> str:
    """Fold a header for matching.

    Lowercase, accents removed, every run of characters that are not letters or
    digits replaced by one space, and the ends trimmed: ``Dt. Nascimento `` is
    ``dt nascimento``. Only ASCII letters and digits survive, so a header written
    in a script with no Latin decomposition folds to an empty string.
    """
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    bare = "".join(char for char in decomposed if not unicodedata.combining(char))
    return _NOT_ALPHANUMERIC.sub(" ", bare).strip()


def column_names(headers: list[str] | None, width: int) -> list[str]:
    """Unique normalized names for ``width`` columns.

    ``headers`` is the header row as written, or ``None`` when the table has no
    header. An empty header is named ``column_<position>``. A name already taken
    gets the suffix `` 2``, `` 3`` and so on.
    """
    taken: set[str] = set()
    names: list[str] = []
    for position in range(width):
        base = normalize_header(headers[position]) if headers is not None else ""
        base = base or f"column_{position + 1}"
        name, suffix = base, 1
        while name in taken:
            suffix += 1
            name = f"{base} {suffix}"
        taken.add(name)
        names.append(name)
    return names
