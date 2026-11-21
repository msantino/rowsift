"""CPF, CNPJ, postal code and e-mail cleaners."""

from typing import Any

import pytest

from rowsift.clean import CleanOptions, cnpj, cpf, email, postal_code
from rowsift.types import Change, ChangeCode, Cleaned, IssueCode


def _digit(numbers: list[int], weights: list[int]) -> int:
    remainder = sum(n * w for n, w in zip(numbers, weights, strict=True)) % 11
    return 0 if remainder < 2 else 11 - remainder


def make_cpf(base: str) -> str:
    """Append the check digits to 9 invented digits, independently of the library."""
    nine = [int(c) for c in base]
    first = _digit(nine, list(range(10, 1, -1)))
    second = _digit([*nine, first], list(range(11, 1, -1)))
    return base + str(first) + str(second)


def make_cnpj(base: str) -> str:
    """Append the check digits to 12 invented digits, independently of the library."""
    twelve = [int(c) for c in base]
    first = _digit(twelve, [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    second = _digit([*twelve, first], [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    return base + str(first) + str(second)


VALID_CPF = make_cpf("290471836")
VALID_CNPJ = make_cnpj("407182630001")
CPF_WITH_ZEROS = make_cpf("004718362")  # begins with two zeros
CNPJ_WITH_ZEROS = make_cnpj("004071826300")


def code_of(result: Cleaned[Any]) -> IssueCode | None:
    assert result.value is None
    return result.issue.code if result.issue else None


def test_formatted_cpf() -> None:
    formatted = f"{VALID_CPF[:3]}.{VALID_CPF[3:6]}.{VALID_CPF[6:9]}-{VALID_CPF[9:]}"
    result = cpf(formatted)
    assert result.value == VALID_CPF
    assert len(VALID_CPF) == 11
    assert result.changes == ()


def test_leading_zeros_lost_in_a_spreadsheet() -> None:
    result = cpf(str(int(CPF_WITH_ZEROS)))
    assert len(str(int(CPF_WITH_ZEROS))) == 9
    assert result.value == CPF_WITH_ZEROS
    assert result.changes == (Change(ChangeCode.LEADING_ZEROS_RESTORED),)


def test_wrong_check_digit() -> None:
    wrong = VALID_CPF[:10] + str((int(VALID_CPF[10]) + 1) % 10)
    assert code_of(cpf(wrong)) is IssueCode.INVALID_CHECK_DIGIT


def test_repeated_digits() -> None:
    assert code_of(cpf("111.111.111-11")) is IssueCode.INVALID_CHECK_DIGIT
    assert code_of(cnpj("00.000.000/0000-00")) is IssueCode.INVALID_CHECK_DIGIT


def test_padding_that_does_not_pass_the_check_digits_is_not_applied() -> None:
    result = cpf("123456789")
    assert result.value is None
    assert result.issue is not None
    assert result.issue.code is IssueCode.INVALID_LENGTH
    assert result.issue.data == {"digits": 9, "expected": 11}


@pytest.mark.parametrize("raw", ["1234", "123456789012", "1" * 12])
def test_cpf_with_the_wrong_digit_count(raw: str) -> None:
    assert code_of(cpf(raw)) is IssueCode.INVALID_LENGTH


def test_cpf_with_other_characters() -> None:
    assert code_of(cpf("2904718360x")) is IssueCode.NOT_A_NUMBER


def test_formatted_cnpj() -> None:
    formatted = (
        f"{VALID_CNPJ[:2]}.{VALID_CNPJ[2:5]}.{VALID_CNPJ[5:8]}/{VALID_CNPJ[8:12]}-{VALID_CNPJ[12:]}"
    )
    result = cnpj(formatted)
    assert result.value == VALID_CNPJ
    assert result.changes == ()


def test_cnpj_leading_zeros_lost_in_a_spreadsheet() -> None:
    lost = str(int(CNPJ_WITH_ZEROS))
    assert len(lost) == 12
    result = cnpj(lost)
    assert result.value == CNPJ_WITH_ZEROS
    assert result.changes == (Change(ChangeCode.LEADING_ZEROS_RESTORED),)


def test_cnpj_wrong_check_digit_and_length() -> None:
    wrong = VALID_CNPJ[:13] + str((int(VALID_CNPJ[13]) + 1) % 10)
    assert code_of(cnpj(wrong)) is IssueCode.INVALID_CHECK_DIGIT
    assert code_of(cnpj("1234")) is IssueCode.INVALID_LENGTH
    assert code_of(cnpj("AB.123.456/0001-00")) is IssueCode.NOT_A_NUMBER


@pytest.mark.parametrize("cleaner", [cpf, cnpj, postal_code, email])
def test_blank_input(cleaner: Any) -> None:
    result = cleaner("  ")
    assert (result.value, result.issue, result.changes) == (None, None, ())


def test_postal_code_with_a_dash() -> None:
    result = postal_code("01310-100")
    assert result.value == "01310100"
    assert result.changes == ()


def test_postal_code_leading_zero_lost() -> None:
    result = postal_code("1310100")
    assert result.value == "01310100"
    assert result.changes == (Change(ChangeCode.LEADING_ZEROS_RESTORED),)


def test_postal_code_with_the_wrong_digit_count_or_characters() -> None:
    assert code_of(postal_code("13101")) is IssueCode.INVALID_LENGTH
    assert code_of(postal_code("013101000")) is IssueCode.INVALID_LENGTH
    assert code_of(postal_code("0131A-100")) is IssueCode.NOT_A_NUMBER


def test_postal_code_has_native_rules_for_brazil_only() -> None:
    with pytest.raises(ValueError, match="region BR"):
        postal_code("01310-100", CleanOptions(region="PT"))


def test_malformed_email() -> None:
    assert code_of(email("ana.example.com")) is IssueCode.INVALID_EMAIL


@pytest.mark.parametrize(
    "raw",
    [
        "a@b@example.com",
        "@example.com",
        "ana@example",
        "ana@.example.com",
        "ana@example..com",
        "ana@-example.com",
        "ana lima@example.com",
        "ana@exa mple.com",
        "ana@example.123",
        "ana@",
        "<ana>@example.com",
        "ana@" + "a" * 250 + ".com",
    ],
)
def test_other_malformed_emails(raw: str) -> None:
    assert code_of(email(raw)) is IssueCode.INVALID_EMAIL


def test_email_is_trimmed_and_the_domain_lowercased() -> None:
    result = email("  Ana.Lima+list@Example.COM ")
    assert result.value == "Ana.Lima+list@example.com"
    assert result.changes == ()


@pytest.mark.parametrize("cleaner", [cpf, cnpj, postal_code])
def test_digits_of_other_scripts_are_not_a_number(cleaner: Any) -> None:
    result = cleaner("\u0660\u0661\u0663\u0661\u0660-\u0661\u0660\u0660")
    assert result.value is None
    assert result.issue is not None
    assert result.issue.code is IssueCode.NOT_A_NUMBER


def test_email_length_limits() -> None:
    assert email("a" * 64 + "@example.com").value is not None
    for bad in ("a" * 65 + "@example.com", "a@" + "b" * 64 + ".com", "a" * 70 + "@x.com"):
        issue = email(bad).issue
        assert issue is not None
        assert issue.code is IssueCode.INVALID_EMAIL


@pytest.mark.parametrize("raw", ["a..b@example.com", ".a@example.com", "a.@example.com"])
def test_email_local_part_dots(raw: str) -> None:
    issue = email(raw).issue
    assert issue is not None
    assert issue.code is IssueCode.INVALID_EMAIL
