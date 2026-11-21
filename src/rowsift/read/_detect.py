"""Decide the format of the bytes from their content, never from a filename."""

from __future__ import annotations

import io
import zipfile

from rowsift.errors import UnsupportedFileError
from rowsift.read._text import looks_like_text
from rowsift.types import ErrorCode, FileFormat

__all__ = ["XLSX_WORKBOOK_PART", "detect_format"]

XLSX_WORKBOOK_PART = "xl/workbook.xml"

_ZIP_SIGNATURES = (b"PK\x03\x04", b"PK\x05\x06")
_COMPOUND_FILE_SIGNATURE = bytes.fromhex("d0cf11e0a1b11ae1")
# The directory of a workbook encrypted with a password holds a stream with this name.
_ENCRYPTED_PACKAGE = "EncryptedPackage"
_HEADER_SIZE = 512
_MAX_DIFAT_SECTORS = 4096
_DIRECTORY_ENTRY_SIZE = 128
_DIFAT_IN_HEADER = 109
_END_OF_CHAIN = 0xFFFFFFFE
_MAX_DIRECTORY_SECTORS = 4096
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


def _u32(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 4], "little")


def _directory_names(data: bytes) -> list[str]:
    """The entry names of the compound file directory, or none when it cannot be walked.

    Reads the header, follows the directory chain through the allocation table
    and decodes each 128-byte entry name by its length field. Sector offsets
    account for the header filling a whole sector (512 or 4096 bytes), and the
    extended DIFAT chain is followed, bounded. A damaged or
    truncated container yields what could be read, never an error: the XLS
    reader applies its own checks afterwards.
    """
    if len(data) < _HEADER_SIZE:
        return []
    shift = int.from_bytes(data[30:32], "little")
    if not 7 <= shift <= 16:
        return []
    size = 1 << shift

    def sector_at(sector: int) -> bytes:
        # The header fills the first sector, so sector n starts at (n + 1) * size.
        if sector >= _END_OF_CHAIN:
            return b""
        start = (sector + 1) * size
        return data[start : start + size]

    fat_sectors = [_u32(data, 76 + 4 * i) for i in range(_DIFAT_IN_HEADER)]
    difat = _u32(data, 68)
    for _ in range(_MAX_DIFAT_SECTORS):
        block = sector_at(difat)
        if not block:
            break
        count = len(block) // 4
        fat_sectors.extend(_u32(block, 4 * i) for i in range(count - 1))
        difat = _u32(block, 4 * (count - 1))
    fat: list[int] = []
    listed = [sector for sector in fat_sectors if sector < _END_OF_CHAIN]
    for sector in listed[: _u32(data, 44)]:
        block = sector_at(sector)
        fat.extend(_u32(block, i) for i in range(0, len(block) - 3, 4))
    names: list[str] = []
    sector = _u32(data, 48)
    for _ in range(_MAX_DIRECTORY_SECTORS):
        if sector >= _END_OF_CHAIN:
            break
        block = sector_at(sector)
        for offset in range(0, len(block) - _DIRECTORY_ENTRY_SIZE + 1, _DIRECTORY_ENTRY_SIZE):
            length = int.from_bytes(block[offset + 64 : offset + 66], "little")
            if 2 <= length <= 64:
                raw = block[offset : offset + length - 2]
                names.append(raw.decode("utf-16-le", errors="replace"))
        sector = fat[sector] if sector < len(fat) else _END_OF_CHAIN
    return names


def detect_format(data: bytes) -> FileFormat:
    """The format of ``data``: an XLSX workbook, an XLS workbook or delimited text.

    An XLSX is a ZIP archive that holds the workbook part. The XLS signature is
    the compound file header. Everything else is delimited text when it has the
    look of text, which means no NUL bytes except in the pattern of UTF-16.

    Raises:
        UnsupportedFileError: if the bytes are a ZIP archive that is no workbook,
            a known binary format, or have the look of binary data
            (``unsupported_file``), or a compound file that holds an encrypted
            workbook (``password_protected``).
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
        if _ENCRYPTED_PACKAGE in _directory_names(data):
            raise UnsupportedFileError(ErrorCode.PASSWORD_PROTECTED)
        return FileFormat.XLS
    if data.startswith(_OTHER_BINARY_SIGNATURES) or not looks_like_text(data):
        raise UnsupportedFileError()
    return FileFormat.CSV
