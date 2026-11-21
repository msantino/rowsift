"""Exceptions raised on purpose by the library.

Every one derives from ``RowsiftError`` and carries a code. Messages are built
from codes and constant names only: they never include cell contents. Every
one survives ``pickle`` and ``copy``, so it can cross process boundaries.
"""

from __future__ import annotations

from typing import Any, Literal, get_args

from rowsift.types import ErrorCode

__all__ = [
    "DecodingError",
    "ExtraName",
    "LimitExceededError",
    "LimitName",
    "MissingExtraError",
    "RowsiftError",
    "UnsupportedFileError",
]

LimitName = Literal[
    "max_bytes",
    "max_rows",
    "max_columns",
    "max_cell_chars",
    "max_decompressed_bytes",
]
"""The limits a read can exceed. Constants only, never a value taken from a file."""

ExtraName = Literal["excel", "phone"]
"""The optional extras. Constants only, never a value taken from a file."""


_UNSUPPORTED_CODES = (
    ErrorCode.UNSUPPORTED_FILE,
    ErrorCode.SHEET_NOT_FOUND,
    ErrorCode.PASSWORD_PROTECTED,
)


class RowsiftError(Exception):
    """Base class of every exception the library raises on purpose.

    Attributes:
        code: the machine-readable reason.
    """

    code: ErrorCode

    def __init__(self, code: ErrorCode) -> None:
        if not isinstance(code, ErrorCode):
            raise TypeError("code must be an ErrorCode")
        super().__init__(code.value)
        self.code = code

    def __reduce__(self) -> tuple[Any, tuple[Any, ...]]:
        return (type(self), (self.code,))


class UnsupportedFileError(RowsiftError):
    """The bytes are no supported format, or a requested sheet does not exist.

    The code is ``unsupported_file`` by default, ``sheet_not_found`` when a
    named sheet is absent and ``password_protected`` when the workbook is
    encrypted with a password, which the library does not open.
    """

    def __init__(self, code: ErrorCode = ErrorCode.UNSUPPORTED_FILE) -> None:
        if code not in _UNSUPPORTED_CODES:
            raise ValueError("code must be unsupported_file, sheet_not_found or password_protected")
        super().__init__(code)


class LimitExceededError(RowsiftError):
    """A read limit was exceeded.

    Attributes:
        limit: the name of the limit, such as ``max_rows``.
        allowed: the value the limit allows.
    """

    def __init__(self, limit: LimitName, allowed: int) -> None:
        if limit not in get_args(LimitName):
            raise ValueError("limit must be a known limit name")
        if type(allowed) is not int or allowed < 0:
            raise ValueError("allowed must be a non-negative int")
        super().__init__(ErrorCode.LIMIT_EXCEEDED)
        self.limit = limit
        self.allowed = allowed
        self.args = (f"{ErrorCode.LIMIT_EXCEEDED.value}: {limit} (allowed {allowed})",)

    def __reduce__(self) -> tuple[Any, tuple[Any, ...]]:
        return (type(self), (self.limit, self.allowed))


class MissingExtraError(RowsiftError):
    """A feature needs an optional extra that is not installed.

    Attributes:
        extra: the extra to install, such as ``excel`` or ``phone``.
    """

    def __init__(self, extra: ExtraName) -> None:
        if extra not in get_args(ExtraName):
            raise ValueError("extra must be a known extra name")
        super().__init__(ErrorCode.MISSING_EXTRA)
        self.extra = extra
        self.args = (f"{ErrorCode.MISSING_EXTRA.value}: install rowsift[{extra}]",)

    def __reduce__(self) -> tuple[Any, tuple[Any, ...]]:
        return (type(self), (self.extra,))


class DecodingError(RowsiftError):
    """The text of a file could not be decoded."""

    def __init__(self) -> None:
        super().__init__(ErrorCode.DECODING_FAILED)

    def __reduce__(self) -> tuple[Any, tuple[Any, ...]]:
        return (type(self), ())
