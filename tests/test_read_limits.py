import array
import pickle

import pytest

from rowsift import ReadLimits, read
from rowsift.errors import LimitExceededError, UnsupportedFileError
from rowsift.types import ErrorCode


def test_the_defaults() -> None:
    limits = ReadLimits()
    assert limits.max_bytes == 10 * 1024 * 1024
    assert limits.max_rows == 50_000
    assert limits.max_columns == 200
    assert limits.max_decompressed_bytes == 100 * 1024 * 1024
    assert limits.max_cell_chars == 10_000


def test_limits_are_frozen_and_pickle() -> None:
    limits = ReadLimits(max_rows=5)
    assert pickle.loads(pickle.dumps(limits)) == limits
    with pytest.raises(AttributeError):
        limits.max_rows = 6  # type: ignore[misc]  # frozen dataclass: the assignment must fail


@pytest.mark.parametrize("value", [0, -1])
def test_a_limit_must_be_positive(value: int) -> None:
    with pytest.raises(ValueError, match="max_rows"):
        ReadLimits(max_rows=value)


@pytest.mark.parametrize("value", [1.5, True, "10"])
def test_a_limit_must_be_an_int(value: object) -> None:
    with pytest.raises(TypeError, match="max_rows"):
        ReadLimits(max_rows=value)  # type: ignore[arg-type]  # the check under test


def test_too_many_rows() -> None:
    data = b"11999990001\n" * 50_001
    with pytest.raises(LimitExceededError) as caught:
        read(data)
    assert caught.value.limit == "max_rows"
    assert caught.value.allowed == 50_000


def test_exactly_the_row_limit_is_allowed() -> None:
    assert len(read(b"1\n" * 50_000).rows) == 50_000


def test_input_over_the_byte_limit_is_refused_before_it_is_looked_at() -> None:
    with pytest.raises(LimitExceededError) as caught:
        read(b"\x00" * 11, limits=ReadLimits(max_bytes=10))
    assert caught.value.limit == "max_bytes"
    assert caught.value.allowed == 10


def test_the_byte_limit_counts_bytes_and_not_items_of_a_wide_memoryview() -> None:
    wide = memoryview(array.array("H", [0x6161] * 1000))
    assert wide.nbytes == 2000
    with pytest.raises(LimitExceededError) as caught:
        read(wide, limits=ReadLimits(max_bytes=1500))
    assert caught.value.limit == "max_bytes"


def test_too_many_columns() -> None:
    with pytest.raises(LimitExceededError) as caught:
        read(b"a,b,c\n", limits=ReadLimits(max_columns=2))
    assert caught.value.limit == "max_columns"


def test_empty_trailing_columns_do_not_count_against_the_column_limit() -> None:
    table = read(b"a,b,,,,\n", limits=ReadLimits(max_columns=2))
    assert table.report.column_count == 2


def test_a_cell_that_is_too_long() -> None:
    with pytest.raises(LimitExceededError) as caught:
        read(b"a," + b"x" * 11 + b"\n", limits=ReadLimits(max_cell_chars=10))
    assert caught.value.limit == "max_cell_chars"


def test_a_cell_beyond_the_csv_module_default_but_within_the_limit_is_read() -> None:
    data = b"a," + b"x" * 150_000 + b"\n"
    table = read(data, limits=ReadLimits(max_bytes=1_000_000, max_cell_chars=200_000))
    assert table.rows == (("a", "x" * 150_000),)


def test_a_cell_beyond_a_large_limit_is_refused_with_that_limit() -> None:
    data = b"a," + b"x" * 250_000 + b"\n"
    with pytest.raises(LimitExceededError) as caught:
        read(data, limits=ReadLimits(max_bytes=1_000_000, max_cell_chars=200_000))
    assert caught.value.limit == "max_cell_chars"
    assert caught.value.allowed == 200_000


def test_the_csv_field_limit_is_restored_after_a_read() -> None:
    import csv

    before = csv.field_size_limit()
    read(b"a,b\n", limits=ReadLimits(max_cell_chars=200_000))
    with pytest.raises(LimitExceededError):
        read(b"a," + b"x" * 300 + b"\n", limits=ReadLimits(max_cell_chars=200))
    assert csv.field_size_limit() == before


def test_an_error_message_holds_no_cell_content() -> None:
    with pytest.raises(LimitExceededError) as caught:
        read(b"secret-value," + b"x" * 20 + b"\n", limits=ReadLimits(max_cell_chars=10))
    assert "secret" not in str(caught.value)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"data": "text"}, "data"),
        ({"data": b"a", "filename": 3}, "filename"),
        ({"data": b"a", "sheet": True}, "sheet"),
        ({"data": b"a", "sheet": 1.5}, "sheet"),
        ({"data": b"a", "limits": object()}, "limits"),
    ],
)
def test_arguments_of_the_wrong_type_are_refused(kwargs: dict[str, object], message: str) -> None:
    with pytest.raises(TypeError, match=message):
        read(**kwargs)  # type: ignore[arg-type]  # the check under test


def test_bytearray_and_memoryview_are_accepted() -> None:
    assert read(bytearray(b"a;b\n")).rows == (("a", "b"),)
    assert read(memoryview(b"a;b\n")).rows == (("a", "b"),)


def test_a_sheet_asked_of_text_is_refused_with_its_code() -> None:
    with pytest.raises(UnsupportedFileError) as caught:
        read(b"a\n", sheet="x")
    assert caught.value.code is ErrorCode.SHEET_NOT_FOUND
