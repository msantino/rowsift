"""Decide the format of the bytes from their content, never from a filename."""

from __future__ import annotations

import io
import zipfile

from rowsift.errors import UnsupportedFileError
from rowsift.read._text import looks_like_text
from rowsift.types import FileFormat

__all__ = ["XLSX_WORKBOOK_PART", "detect_format"]

XLSX_WORKBOOK_PART = "xl/workbook.xml"

_ZIP_SIGNATURES = (b"PK\x03\x04", b"PK\x05\x06")
_COMPOUND_FILE_SIGNATURE = bytes.fromhex("d0cf11e0a1b11ae1")
_OTHER_BINARY_SIGNATURES = (
    b"%PDF-",
    b"\x89PNG\r\n\x1a\n",
    b"GIF87a",
    b"GIF89a",
    b"\xff\xd8\xff",
    b"\x1f\x8b",
    b"Rar!\x1a\x07",
    b"7z\xbc\xaf\x27\x1c",
    b"\x7fELF",
)


def detect_format(data: bytes) -> FileFormat:
    """The format of ``data``: an XLSX workbook, an XLS workbook or delimited text.

    An XLSX is a ZIP archive that holds the workbook part. The XLS signature is
    the compound file header. Everything else is delimited text when it has the
    look of text, which means no NUL bytes except in the pattern of UTF-16.

    Raises:
        UnsupportedFileError: if the bytes are a ZIP archive that is no workbook,
            a known binary format, or have the look of binary data.
    """
    if data.startswith(_ZIP_SIGNATURES):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                names = archive.namelist()
        except (zipfile.BadZipFile, OSError, ValueError, NotImplementedError):
            raise UnsupportedFileError() from None
        if XLSX_WORKBOOK_PART in names:
            return FileFormat.XLSX
        raise UnsupportedFileError()
    if data.startswith(_COMPOUND_FILE_SIGNATURE):
        return FileFormat.XLS
    if data.startswith(_OTHER_BINARY_SIGNATURES) or not looks_like_text(data):
        raise UnsupportedFileError()
    return FileFormat.CSV
