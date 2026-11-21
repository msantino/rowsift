import pytest

from rowsift import read
from rowsift.errors import UnsupportedFileError
from rowsift.read._detect import detect_format
from rowsift.types import ErrorCode, FileFormat
from tests.read_helpers import fixture

pytest.importorskip("openpyxl")


def test_workbook_with_a_text_extension() -> None:
    data = fixture("workbook_cells", "phone_as_number.xlsx")
    table = read(data, filename="list.csv")
    assert table.report.format is FileFormat.XLSX
    assert table.rows == (("Phone",), ("11999990001",))


def test_text_with_a_workbook_extension_is_still_text() -> None:
    table = read(b"a,b\n1,2\n", filename="list.xlsx")
    assert table.report.format is FileFormat.CSV


def test_bytes_that_are_no_supported_format() -> None:
    pdf = b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n"
    with pytest.raises(UnsupportedFileError) as caught:
        read(pdf)
    assert caught.value.code is ErrorCode.UNSUPPORTED_FILE
    assert str(caught.value) == "unsupported_file"
    assert "Catalog" not in str(caught.value)


@pytest.mark.parametrize(
    "data",
    [
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR",
        b"\xff\xd8\xff\xe0\x00\x10JFIF",
        b"\x1f\x8b\x08\x00\x00\x00\x00\x00",
        b"a;b\x00\x01\x02\x03;c\n1;2\n",
    ],
    ids=["png", "jpeg", "gzip", "binary-with-nul"],
)
def test_other_binary_content_is_unsupported(data: bytes) -> None:
    with pytest.raises(UnsupportedFileError):
        detect_format(data)


def test_a_zip_archive_that_is_no_workbook_is_unsupported() -> None:
    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("notes.txt", "hello")
    with pytest.raises(UnsupportedFileError):
        detect_format(buffer.getvalue())


def test_a_truncated_zip_archive_is_unsupported() -> None:
    data = fixture("workbook_cells", "phone_as_number.xlsx")
    with pytest.raises(UnsupportedFileError):
        detect_format(data[:40])


def test_the_compound_file_signature_is_a_legacy_workbook() -> None:
    assert detect_format(bytes.fromhex("d0cf11e0a1b11ae1") + b"\x00" * 64) is FileFormat.XLS


def test_plain_text_is_delimited_text() -> None:
    assert detect_format(b"a;b\n1;2\n") is FileFormat.CSV
