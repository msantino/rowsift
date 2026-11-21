import copy
import pickle
from collections.abc import Callable

import pytest

from rowsift.errors import (
    DecodingError,
    LimitExceededError,
    MissingExtraError,
    RowsiftError,
    UnsupportedFileError,
)
from rowsift.types import ErrorCode


def test_catching_everything_with_the_base_class() -> None:
    raised: list[RowsiftError] = [
        UnsupportedFileError(),
        LimitExceededError("max_rows", 50_000),
        DecodingError(),
        MissingExtraError("excel"),
    ]
    for error in raised:
        with pytest.raises(RowsiftError) as caught:
            raise error
        assert isinstance(caught.value.code, ErrorCode)


def test_unsupported_file_has_a_default_code_and_can_name_a_missing_sheet() -> None:
    assert UnsupportedFileError().code is ErrorCode.UNSUPPORTED_FILE
    assert UnsupportedFileError(ErrorCode.SHEET_NOT_FOUND).code is ErrorCode.SHEET_NOT_FOUND


def test_limit_exceeded_names_the_limit_and_the_allowed_value() -> None:
    error = LimitExceededError("max_decompressed_bytes", 100_000_000)
    assert error.code is ErrorCode.LIMIT_EXCEEDED
    assert error.limit == "max_decompressed_bytes"
    assert error.allowed == 100_000_000
    assert "max_decompressed_bytes" in str(error)
    assert "100000000" in str(error)


def test_missing_extra_names_the_extra() -> None:
    error = MissingExtraError("phone")
    assert error.code is ErrorCode.MISSING_EXTRA
    assert error.extra == "phone"
    assert "rowsift[phone]" in str(error)


def test_decoding_error_carries_its_code_only() -> None:
    error = DecodingError()
    assert error.code is ErrorCode.DECODING_FAILED
    assert str(error) == "decoding_failed"


ALL_ERRORS: list[RowsiftError] = [
    UnsupportedFileError(),
    UnsupportedFileError(ErrorCode.SHEET_NOT_FOUND),
    LimitExceededError("max_rows", 50_000),
    MissingExtraError("excel"),
    DecodingError(),
]


@pytest.mark.parametrize("error", ALL_ERRORS, ids=lambda e: repr(e))
def test_messages_are_built_from_codes_and_constant_names_only(error: RowsiftError) -> None:
    """No constructor accepts file content, so the guarantee is structural.

    This pins the exact shape of every message, so a new constructor argument
    that reaches a message has to be added here on purpose.
    """
    allowed = {
        error.code.value,
        f"limit_exceeded: {getattr(error, 'limit', '')} (allowed {getattr(error, 'allowed', '')})",
        f"missing_extra: install rowsift[{getattr(error, 'extra', '')}]",
    }
    assert str(error) in allowed


@pytest.mark.parametrize("error", ALL_ERRORS, ids=lambda e: repr(e))
@pytest.mark.parametrize(
    "clone",
    [lambda e: pickle.loads(pickle.dumps(e)), copy.copy, copy.deepcopy],
    ids=["pickle", "copy", "deepcopy"],
)
def test_errors_survive_pickle_and_copy(
    error: RowsiftError, clone: Callable[[RowsiftError], RowsiftError]
) -> None:
    again = clone(error)
    assert type(again) is type(error)
    assert again.code is error.code
    assert str(again) == str(error)
    assert vars(again) == vars(error)


def test_base_error_needs_an_error_code() -> None:
    with pytest.raises(TypeError, match="ErrorCode"):
        RowsiftError("x")  # type: ignore[arg-type]  # proving the runtime check


def test_unsupported_file_accepts_only_its_two_codes() -> None:
    with pytest.raises(ValueError, match="unsupported_file or sheet_not_found"):
        UnsupportedFileError(ErrorCode.LIMIT_EXCEEDED)


@pytest.mark.parametrize("limit", ["anything", "max_rows\nfoo"])
def test_limit_must_be_a_known_name(limit: str) -> None:
    with pytest.raises(ValueError, match="known limit"):
        LimitExceededError(limit, 1)  # type: ignore[arg-type]  # proving the runtime check


@pytest.mark.parametrize("allowed", [-1, True, 1.5, "1"])
def test_allowed_must_be_a_non_negative_int(allowed: object) -> None:
    with pytest.raises(ValueError, match="non-negative int"):
        LimitExceededError("max_rows", allowed)  # type: ignore[arg-type]


def test_extra_must_be_a_known_name() -> None:
    with pytest.raises(ValueError, match="known extra"):
        MissingExtraError("x]\nfoo")  # type: ignore[arg-type]  # proving the runtime check
