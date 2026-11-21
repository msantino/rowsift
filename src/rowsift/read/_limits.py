"""The limits of a read."""

from __future__ import annotations

from dataclasses import dataclass, fields

__all__ = ["ReadLimits"]


@dataclass(frozen=True, slots=True, kw_only=True)
class ReadLimits:
    """Upper bounds a read enforces before it does the work. All are passed by keyword.

    A file that goes beyond one of them stops the read with a
    ``LimitExceededError`` that names the limit. Sizes are in bytes, with a
    megabyte being 1,048,576 bytes.

    Attributes:
        max_bytes: size of the input. Default 10 MB.
        max_rows: rows of the table, empty rows included. Default 50,000.
        max_columns: columns that hold data. Trailing columns that are empty in
            every row do not count. Default 200.
        max_decompressed_bytes: sum of the uncompressed sizes a workbook
            archive declares. Default 100 MB.
        max_cell_chars: characters in one cell. Default 10,000.

    Raises:
        TypeError: if a limit is not an ``int`` (a ``bool`` is not).
        ValueError: if a limit is not positive.
    """

    max_bytes: int = 10 * 1024 * 1024
    max_rows: int = 50_000
    max_columns: int = 200
    max_decompressed_bytes: int = 100 * 1024 * 1024
    max_cell_chars: int = 10_000

    def __post_init__(self) -> None:
        for field in fields(self):
            value = getattr(self, field.name)
            if type(value) is not int:
                raise TypeError(f"{field.name} must be an int")
            if value < 1:
                raise ValueError(f"{field.name} must be positive")
