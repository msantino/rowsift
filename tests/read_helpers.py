"""Helpers shared by the reading tests."""

from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures" / "reading"


def fixture(folder: str, name: str) -> bytes:
    """The bytes of one reading fixture."""
    return (FIXTURES / folder / name).read_bytes()


_END_OF_CHAIN = 0xFFFFFFFE
_FREE = 0xFFFFFFFF
_NO_STREAM = 0xFFFFFFFF


def compound_file(
    *stream_names: str,
    shift: int = 9,
    filler: bytes = b"",
    difat_chain: bool = False,
    spill: bool = False,
) -> bytes:
    """A minimal compound file (the container of XLS and of encrypted workbooks).

    One FAT sector and one directory sector, with an empty stream per name. It
    is enough for the signature and the directory, not a workbook anyone can open.
    ``shift`` is the sector shift (9 for 512-byte sectors, 12 for 4096). When
    ``filler`` is given, one extra sector holds it, as the data of the first
    stream. With ``difat_chain``, the FAT sector is listed in an extended DIFAT
    sector instead of the header. With ``spill``, the directory takes two
    sectors and the stream names sit in the second, behind the whole first one.
    """
    if filler and difat_chain:
        raise ValueError("filler and difat_chain are exclusive")
    if not 1 <= len(stream_names) <= 3:
        raise ValueError("one to three stream names")
    size = 1 << shift
    extra = 3 if spill else 2  # the sector after the directory
    header = bytearray(size)
    header[0:8] = bytes.fromhex("d0cf11e0a1b11ae1")
    header[24:26] = (0x3E).to_bytes(2, "little")  # minor version
    header[26:28] = (3 if shift == 9 else 4).to_bytes(2, "little")  # major version
    header[28:30] = (0xFFFE).to_bytes(2, "little")  # little endian
    header[30:32] = shift.to_bytes(2, "little")  # sector size
    header[32:34] = (6).to_bytes(2, "little")  # mini sector size 64
    header[44:48] = (1).to_bytes(4, "little")  # FAT sectors
    header[48:52] = (1).to_bytes(4, "little")  # first directory sector
    header[56:60] = (4096).to_bytes(4, "little")  # mini stream cutoff
    header[60:64] = _END_OF_CHAIN.to_bytes(4, "little")  # no mini FAT
    header[68:72] = (extra if difat_chain else _END_OF_CHAIN).to_bytes(4, "little")
    difat = [_FREE if difat_chain else 0] + [_FREE] * 108
    header[76:512] = b"".join(value.to_bytes(4, "little") for value in difat)

    directory_chain = [2, _END_OF_CHAIN] if spill else [_END_OF_CHAIN]
    third = [_END_OF_CHAIN] if filler else [0xFFFFFFFC] if difat_chain else []
    fat = ([0xFFFFFFFD, *directory_chain, *third] + [_FREE] * (size // 4))[: size // 4]
    fat_sector = b"".join(value.to_bytes(4, "little") for value in fat)

    def entry(name: str, kind: int, left: int, right: int, child: int) -> bytes:
        raw = bytearray(128)
        encoded = name.encode("utf-16-le")
        raw[0 : len(encoded)] = encoded
        raw[64:66] = (len(encoded) + 2).to_bytes(2, "little")
        raw[66] = kind
        raw[67] = 1 if kind else 0  # black for a used entry
        raw[68:72] = left.to_bytes(4, "little")
        raw[72:76] = right.to_bytes(4, "little")
        raw[76:80] = child.to_bytes(4, "little")
        raw[116:120] = _END_OF_CHAIN.to_bytes(4, "little") if kind == 2 else bytes(4)
        return bytes(raw)

    per_sector = size // 128
    first = per_sector if spill else 1
    entries = [entry("Root Entry", 5, _NO_STREAM, _NO_STREAM, first)]
    while spill and len(entries) < per_sector:
        entries.append(entry("", 0, _NO_STREAM, _NO_STREAM, _NO_STREAM))
    for index, name in enumerate(stream_names, start=first):
        right = index + 1 if index < first + len(stream_names) - 1 else _NO_STREAM
        entries.append(entry(name, 2, _NO_STREAM, right, _NO_STREAM))
    while len(entries) < (per_sector + 4 if spill else 4):
        entries.append(entry("", 0, _NO_STREAM, _NO_STREAM, _NO_STREAM))
    directory = b"".join(entries).ljust(size, b"\0")
    tail = filler.ljust(size, b"\0") if filler else b""
    if difat_chain:
        entries_in_sector = [0] + [_FREE] * (size // 4 - 2) + [_END_OF_CHAIN]
        tail = b"".join(value.to_bytes(4, "little") for value in entries_in_sector)
    return bytes(header) + fat_sector + directory + tail
