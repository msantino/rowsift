"""Integer, decimal and money cleaners."""

from decimal import Decimal

import pytest

from rowsift.clean import CleanOptions, decimal, integer, money
from rowsift.types import Change, ChangeCode, IssueCode

DOT = CleanOptions(decimal_separator=".")


def test_brazilian_money() -> None:
    result = money("R$ 1.234,56")
    assert result.value == Decimal("1234.56")
    assert result.changes == ()


def test_dot_decimal_under_comma_options() -> None:
    result = money("1,234.56")
    assert result.value == Decimal("1234.56")
    assert result.changes == (Change(ChangeCode.SEPARATOR_INFERRED),)


def test_not_a_number() -> None:
    result = decimal("n/a")
    assert result.value is None
    assert result.issue is not None
    assert result.issue.code is IssueCode.NOT_A_NUMBER


@pytest.mark.parametrize(
    ("raw", "expected", "options"),
    [
        ("12,5", "12.5", CleanOptions()),
        ("12.5", "12.5", DOT),
        ("1,234.56", "1234.56", DOT),
        ("1.234.567,89", "1234567.89", CleanOptions()),
        ("1.234", "1234", CleanOptions()),
        ("1,234", "1234", DOT),
        ("1.234.567", "1234567", CleanOptions()),
        (",50", "0.50", CleanOptions()),
        ("-3,5", "-3.5", CleanOptions()),
        ("3,5-", "-3.5", CleanOptions()),
        ("(1.200,00)", "-1200.00", CleanOptions()),
        ("+7", "7", CleanOptions()),
        ("R$ -10,00", "-10.00", CleanOptions()),
        ("BRL 99,90", "99.90", CleanOptions()),
        ("$ 5.00", "5.00", DOT),
        ("0", "0", CleanOptions()),
    ],
)
def test_separators_follow_the_options(raw: str, expected: str, options: CleanOptions) -> None:
    result = decimal(raw, options)
    assert result.value == Decimal(expected)
    assert result.changes == ()


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("1.5", "1.5"), ("0.123", "0.123"), ("1,234,567", "1234567"), ("12,345.6", "12345.6")],
)
def test_contradicting_input_is_read_as_written_and_reported(raw: str, expected: str) -> None:
    result = decimal(raw)
    assert result.value == Decimal(expected)
    assert result.changes == (Change(ChangeCode.SEPARATOR_INFERRED),)


@pytest.mark.parametrize(
    "raw",
    ["1E+5", "1,23,4.5", "12,", "1.2.3,4", "abc", "1 234", "--1", ".", "R$", "1,2,3", "1.23,4.5"],
)
def test_malformed_numbers_are_an_issue(raw: str) -> None:
    result = decimal(raw)
    assert result.value is None
    assert result.issue is not None
    assert result.issue.code is IssueCode.NOT_A_NUMBER


def test_integer() -> None:
    assert integer("1.234").value == 1234
    assert integer("42").value == 42
    assert integer("12,0").value == 12
    assert integer("-7").value == -7


def test_integer_never_truncates() -> None:
    result = integer("3,5")
    assert result.value is None
    assert result.issue is not None
    assert result.issue.code is IssueCode.NOT_A_NUMBER


def test_integer_reports_an_inferred_separator() -> None:
    result = integer("1,234,567")
    assert result.value == 1234567
    assert result.changes == (Change(ChangeCode.SEPARATOR_INFERRED),)


def test_integer_that_is_no_number() -> None:
    assert integer("abc").issue is not None


def test_a_negative_amount_keeps_every_digit() -> None:
    digits = "1" * 30
    assert decimal("-" + digits).value == Decimal("-" + digits)
    assert money("(" + digits + ")").value == Decimal("-" + digits)
    assert integer("-" + digits).value == -int(digits)


@pytest.mark.parametrize("raw", ["(-5)", "(5-)", "-(5)", "(-5,00)", "-5-"])
def test_two_negative_markers_are_not_a_number(raw: str) -> None:
    result = decimal(raw)
    assert result.value is None
    assert result.issue is not None
    assert result.issue.code is IssueCode.NOT_A_NUMBER


@pytest.mark.parametrize("cleaner", [decimal, money, integer])
def test_a_huge_digit_run_is_an_issue_not_an_error(cleaner) -> None:  # type: ignore[no-untyped-def]
    for raw in ("1" * 5000, "1" * 39, "R$ " + "9" * 200_000):
        result = cleaner(raw)
        assert result.value is None
        assert result.issue is not None
        assert result.issue.code is IssueCode.NOT_A_NUMBER


def test_a_number_at_the_digit_limit_is_kept() -> None:
    assert integer("9" * 38).value == int("9" * 38)
