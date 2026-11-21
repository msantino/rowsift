"""A workbook encrypted with a password gets its own code."""

import pytest

from rowsift import read
from rowsift.errors import UnsupportedFileError
from rowsift.read._detect import detect_format
from rowsift.types import ErrorCode, FileFormat
from tests.read_helpers import compound_file


def test_a_workbook_encrypted_with_a_password_is_reported_as_such() -> None:
    data = compound_file("EncryptionInfo", "EncryptedPackage")
    with pytest.raises(UnsupportedFileError) as caught:
        read(data)
    assert caught.value.code is ErrorCode.PASSWORD_PROTECTED
    assert str(caught.value) == "password_protected"


def test_the_encrypted_workbook_is_reported_without_the_excel_extra_too() -> None:
    with pytest.raises(UnsupportedFileError) as caught:
        detect_format(compound_file("EncryptionInfo", "EncryptedPackage"))
    assert caught.value.code is ErrorCode.PASSWORD_PROTECTED


def test_a_compound_file_without_an_encrypted_package_is_still_an_xls_candidate() -> None:
    assert detect_format(compound_file("Workbook")) is FileFormat.XLS


def test_the_encrypted_marker_inside_delimited_text_is_only_text() -> None:
    table = read(b"name,note\nAna,EncryptedPackage\n")
    assert table.rows[1] == ("Ana", "EncryptedPackage")


def test_the_marker_as_cell_data_in_a_compound_file_is_still_an_xls_candidate() -> None:
    marker = "EncryptedPackage".encode("utf-16-le")
    data = compound_file("Workbook", filler=b"cell data " + marker)
    assert marker in data
    assert detect_format(data) is FileFormat.XLS


def test_the_marker_after_the_end_of_the_container_is_not_in_the_directory() -> None:
    data = compound_file("Workbook") + "EncryptedPackage".encode("utf-16-le")
    assert detect_format(data) is FileFormat.XLS


def test_an_encrypted_workbook_in_a_container_with_4096_byte_sectors_is_reported() -> None:
    data = compound_file("EncryptionInfo", "EncryptedPackage", shift=12, spill=True)
    with pytest.raises(UnsupportedFileError) as caught:
        detect_format(data)
    assert caught.value.code is ErrorCode.PASSWORD_PROTECTED


def test_a_container_with_4096_byte_sectors_without_the_marker_is_an_xls_candidate() -> None:
    assert detect_format(compound_file("Workbook", shift=12, spill=True)) is FileFormat.XLS


def test_the_extended_difat_chain_is_followed() -> None:
    data = compound_file("EncryptionInfo", "EncryptedPackage", difat_chain=True, spill=True)
    with pytest.raises(UnsupportedFileError) as caught:
        detect_format(data)
    assert caught.value.code is ErrorCode.PASSWORD_PROTECTED


def test_a_truncated_compound_file_is_left_to_the_reader() -> None:
    data = compound_file("EncryptionInfo", "EncryptedPackage")[:600]
    assert detect_format(data) is FileFormat.XLS
