"""Phone cleaner."""

import pickle
import sys
from types import SimpleNamespace
from typing import Any

import pytest

from rowsift.clean import CleanOptions, PhoneNumber, phone
from rowsift.errors import MissingExtraError
from rowsift.types import Change, ChangeCode, IssueCode, LineType


def code_of(raw: str, options: CleanOptions | None = None) -> IssueCode | None:
    result = phone(raw, options)
    assert result.value is None
    return result.issue.code if result.issue else None


def test_formatting_is_not_a_reported_change() -> None:
    result = phone("(11) 99999-0042")
    assert result.value == "+5511999990042"
    assert result.changes == ()
    assert result.value.line_type is LineType.MOBILE


def test_mobile_without_the_ninth_digit() -> None:
    result = phone("11 8888-0042")
    assert result.value == "+5511988880042"
    assert result.changes == (Change(ChangeCode.NINTH_DIGIT_INSERTED),)


def test_number_cut_short_by_an_export() -> None:
    result = phone("(11) 99999-004")
    assert result.value is None
    assert result.issue is not None
    assert result.issue.code is IssueCode.TRUNCATED
    assert result.changes == ()


def test_invalid_area_code() -> None:
    assert code_of("(00) 99999-0042") is IssueCode.INVALID_AREA_CODE
    assert code_of("(20) 99999-0042") is IssueCode.INVALID_AREA_CODE
    assert code_of("(10) 3333-0042") is IssueCode.INVALID_AREA_CODE


def test_landline() -> None:
    result = phone("(11) 3333-0042")
    assert result.value == "+551133330042"
    assert result.value.line_type is LineType.LANDLINE


def test_two_numbers_in_one_cell() -> None:
    result = phone("(11) 3333-0042 / (11) 99999-0042")
    assert result.value == "+551133330042"
    assert result.changes == (Change(ChangeCode.MULTIPLE_VALUES, {"count": 2}),)


def test_the_first_valid_number_wins_in_a_cell_with_several() -> None:
    result = phone("(11) 99999-004; (21) 98888-0042 ou (31) 3333-0042")
    assert result.value == "+5521988880042"
    assert result.changes == (Change(ChangeCode.MULTIPLE_VALUES, {"count": 3}),)


def test_several_numbers_none_valid_gives_the_first_issue() -> None:
    assert code_of("(11) 99999-004 / (00) 99999-0042") is IssueCode.TRUNCATED


def test_mobile_only() -> None:
    assert code_of("(11) 3333-0042", CleanOptions(require_mobile=True)) is IssueCode.NOT_MOBILE
    assert phone("(11) 99999-0042", CleanOptions(require_mobile=True)).value is not None


def test_ninth_digit_insertion_can_be_turned_off() -> None:
    result = phone("11 8888-0042", CleanOptions(insert_ninth_digit=False))
    assert result.value is None
    assert result.issue is not None
    assert result.issue.code is IssueCode.TOO_SHORT


@pytest.mark.parametrize(
    "raw",
    [
        "+55 11 99999-0042",
        "55 (11) 99999-0042",
        "0055 11 99999-0042",
        "011 99999-0042",
        "11999990042",
        "11.99999.0042",
        "5511999990042",
    ],
)
def test_country_code_trunk_zero_and_separators_are_removed(raw: str) -> None:
    result = phone(raw)
    assert result.value == "+5511999990042"
    assert result.changes == ()


def test_area_code_55_is_not_taken_for_the_country_code() -> None:
    assert phone("55 99999-0042").value == "+5555999990042"


@pytest.mark.parametrize("raw", ["99999-0042", "3333-0042", "999990042", "(11) 3333-004"])
def test_fewer_digits_than_any_valid_form(raw: str) -> None:
    result = phone(raw)
    assert result.value is None
    assert result.issue is not None
    assert result.issue.code is IssueCode.TOO_SHORT


@pytest.mark.parametrize(
    "raw",
    [
        "call me",
        "(11) 4999-00420",
        "+1 415 555 0100",
        "(11) 89999-0042",
        "(11) 1333-0042",
        "(11) 0333-0042",
        "12345678901234",
    ],
)
def test_other_shapes_are_an_invalid_phone(raw: str) -> None:
    assert code_of(raw) is IssueCode.INVALID_PHONE


def test_blank_input() -> None:
    result = phone("   ")
    assert (result.value, result.issue, result.changes) == (None, None, ())


def test_a_phone_number_is_a_plain_string_that_survives_pickling() -> None:
    number = phone("(11) 3333-0042").value
    assert isinstance(number, PhoneNumber)
    assert isinstance(number, str)
    clone = pickle.loads(pickle.dumps(number))
    assert clone == number
    assert clone.line_type is LineType.LANDLINE
    assert repr(number) == "PhoneNumber('+551133330042', <LineType.LANDLINE: 'landline'>)"


def test_region_without_native_rules_and_no_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "phonenumbers", None)
    with pytest.raises(MissingExtraError) as caught:
        phone("+351 912 345 678", CleanOptions(region="PT"))
    assert caught.value.extra == "phone"


class _ParseError(Exception):
    pass


class _Parsed(str):
    extension = None


def _fake_phonenumbers() -> Any:
    kinds = SimpleNamespace(MOBILE=1, FIXED_LINE=2, OTHER=3)

    def parse(text: str, region: str) -> str:
        if "999" in text:
            raise _ParseError
        return _Parsed(text)

    return SimpleNamespace(
        NumberParseException=_ParseError,
        PhoneNumberType=kinds,
        PhoneNumberFormat=SimpleNamespace(E164="e164"),
        parse=parse,
        is_valid_number=lambda number: "000" not in number,
        number_type=lambda number: kinds.MOBILE if "912" in number else kinds.FIXED_LINE,
        format_number=lambda number, fmt: "+" + "".join(c for c in number if c.isdigit()),
    )


def test_region_with_the_extra_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "phonenumbers", _fake_phonenumbers())
    options = CleanOptions(region="PT")
    result = phone("351 912 345", options)
    assert result.value == "+351912345"
    assert result.value.line_type is LineType.MOBILE
    assert phone("351 21 100", options).value.line_type is LineType.LANDLINE  # type: ignore[union-attr]  # value is set
    assert code_of("351 000", options) is IssueCode.INVALID_PHONE
    assert code_of("351 999", options) is IssueCode.INVALID_PHONE
    assert code_of("351 21 100", CleanOptions(region="PT", require_mobile=True)) is (
        IssueCode.NOT_MOBILE
    )


def test_an_extension_is_not_counted_as_a_second_number() -> None:
    result = phone("(11) 3333-0042, ramal 12")
    assert result.value == "+551133330042"
    assert result.changes == ()


def test_a_missing_extra_is_raised_even_for_an_empty_cell(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "phonenumbers", None)
    for cell in ("", "no digits here"):
        with pytest.raises(MissingExtraError):
            phone(cell, CleanOptions(region="US"))


def test_an_extension_in_the_same_fragment_is_invalid() -> None:
    result = phone("(11) 99999-0042 ramal 12")
    assert result.value is None
    assert result.issue is not None
    assert result.issue.code is IssueCode.INVALID_PHONE


def test_an_eight_digit_mobile_without_the_ninth_digit_option_is_too_short() -> None:
    result = phone("11 8888-0042", CleanOptions(insert_ninth_digit=False))
    assert result.issue is not None
    assert result.issue.code is IssueCode.TOO_SHORT


def test_the_real_library_cleans_a_us_number() -> None:
    pytest.importorskip("phonenumbers")
    result = phone("(212) 555-0123", CleanOptions(region="US"))
    assert result.value == "+12125550123"
    assert result.issue is None
    assert result.value.line_type is None  # a US number can be either, so the library cannot tell


@pytest.mark.parametrize("cell", ["+1 212 555 0123 ext 5", "212 555 0123 x99"])
def test_the_real_library_does_not_drop_an_extension_silently(cell: str) -> None:
    pytest.importorskip("phonenumbers")
    result = phone(cell, CleanOptions(region="US"))
    assert result.value is None
    assert result.issue is not None
    assert result.issue.code is IssueCode.INVALID_PHONE


@pytest.mark.parametrize(
    "cell",
    [
        "ABC 212 555 0123",
        "1-800-FLOWERS",
        "tel: 212 555 0123",
        "(212) 555-0123 x",
        "212 555 0123 ext",
        "212 555 0123 #5",
    ],
)
def test_the_real_library_rejects_text_it_would_alter_or_drop(cell: str) -> None:
    pytest.importorskip("phonenumbers")
    result = phone(cell, CleanOptions(region="US"))
    assert result.value is None
    assert result.issue is not None
    assert result.issue.code is IssueCode.INVALID_PHONE


def test_other_regions_reject_letters_without_calling_the_library(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _fake_phonenumbers()
    fake.parse = lambda text, region: pytest.fail("the library must not see letters")
    monkeypatch.setitem(sys.modules, "phonenumbers", fake)
    assert code_of("351 912 x5", CleanOptions(region="PT")) is IssueCode.INVALID_PHONE


@pytest.mark.parametrize("raw", ["1.1E+10", "5,5119E+12", "5.5119e+12", " 5,5119E+12 "])
def test_a_scientific_notation_cell_is_an_invalid_phone_not_a_reading_of_its_digits(
    raw: str,
) -> None:
    result = phone(raw)
    assert result.value is None
    assert result.issue is not None
    assert result.issue.code is IssueCode.INVALID_PHONE
