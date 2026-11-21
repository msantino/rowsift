"""Date, day and month, time and datetime cleaners."""

import datetime as dt
from collections.abc import Callable
from typing import Any

import pytest

from rowsift.clean import CleanOptions, date, datetime, day_month, time
from rowsift.types import Change, ChangeCode, Cleaned, DayMonth, IssueCode


def code_of(result: Cleaned[Any]) -> IssueCode | None:
    return result.issue.code if result.issue else None


def test_day_first_date() -> None:
    result = date("03/04/1990")
    assert result.value == dt.date(1990, 4, 3)
    assert result.changes == ()


def test_two_digit_year() -> None:
    result = date("3/11/91", CleanOptions(two_digit_year_pivot=30))
    assert result.value == dt.date(1991, 11, 3)
    assert result.changes == (Change(ChangeCode.TWO_DIGIT_YEAR_EXPANDED, {"year": 1991}),)


def test_two_digit_year_up_to_the_pivot_belongs_to_the_2000s() -> None:
    options = CleanOptions(two_digit_year_pivot=30)
    assert date("1/1/30", options).value == dt.date(2030, 1, 1)
    assert date("1/1/31", options).value == dt.date(1931, 1, 1)
    assert date("1/1/05", CleanOptions(two_digit_year_pivot=4)).value == dt.date(1905, 1, 1)


def test_month_name_in_portuguese() -> None:
    result = date("12 de março de 1988")
    assert result.value == dt.date(1988, 3, 12)
    assert result.changes == ()


def test_date_that_does_not_exist() -> None:
    result = date("31/02/1990")
    assert result.value is None
    assert result.issue is not None
    assert result.issue.code is IssueCode.INVALID_DATE


def test_text_that_is_not_a_date() -> None:
    result = date("to confirm")
    assert result.value is None
    assert result.issue is not None
    assert result.issue.code is IssueCode.NOT_A_DATE


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1990-04-03", dt.date(1990, 4, 3)),
        ("1990/4/3", dt.date(1990, 4, 3)),
        ("03-04-1990", dt.date(1990, 4, 3)),
        ("03.04.1990", dt.date(1990, 4, 3)),
        ("12-mar-1988", dt.date(1988, 3, 12)),
        ("12 MAR 1988", dt.date(1988, 3, 12)),
        ("March 12, 1988", dt.date(1988, 3, 12)),
        ("12 March 1988", dt.date(1988, 3, 12)),
        ("1 setembro 2001", dt.date(2001, 9, 1)),
        ("5 Sept 2001", dt.date(2001, 9, 5)),
        ("29/02/2024", dt.date(2024, 2, 29)),
        ("  03/04/1990  ", dt.date(1990, 4, 3)),
    ],
)
def test_accepted_date_forms(raw: str, expected: dt.date) -> None:
    result = date(raw)
    assert result.value == expected
    assert result.changes == ()


def test_month_first_order() -> None:
    assert date("03/04/1990", CleanOptions(date_order="mdy")).value == dt.date(1990, 3, 4)


def test_iso_is_read_year_first_whatever_the_order() -> None:
    assert date("1990-04-03", CleanOptions(date_order="mdy")).value == dt.date(1990, 4, 3)


def test_serial_number() -> None:
    result = date("45000")
    assert result.value == dt.date(2023, 3, 15)
    assert result.changes == (Change(ChangeCode.SERIAL_DATE_CONVERTED),)
    assert date("45000.0").value == dt.date(2023, 3, 15)


@pytest.mark.parametrize("raw", ["1990", "20240305", "45000.5", "5", "3000000"])
def test_numbers_that_are_not_a_serial_date_are_not_dates(raw: str) -> None:
    result = date(raw)
    assert result.issue is not None
    assert result.issue.code is IssueCode.NOT_A_DATE


@pytest.mark.parametrize(
    "raw",
    [
        "12/03",
        "12/03/1",
        "1/2/3/4",
        "32 mar 1988",
        "12 foo 1988",
        "mar",
        "12 mar 88 x",
        "12 mar 198",
    ],
)
def test_shapes_that_are_not_dates(raw: str) -> None:
    result = date(raw)
    assert result.value is None
    assert result.issue is not None
    assert result.issue.code in (IssueCode.NOT_A_DATE, IssueCode.INVALID_DATE)


def test_a_date_without_a_year_is_not_a_date() -> None:
    assert date("12/03").issue is not None
    assert date("12 de março").issue is not None


def test_year_zero_is_an_invalid_date() -> None:
    assert code_of(date("0000-01-01")) is IssueCode.INVALID_DATE


def test_yearless_input() -> None:
    result = day_month("5-ago")
    assert result.value == DayMonth(5, 8)
    assert result.changes == ()


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("12/03", DayMonth(12, 3)),
        ("12-mar", DayMonth(12, 3)),
        ("12 de março", DayMonth(12, 3)),
        ("12.03", DayMonth(12, 3)),
        ("mar 12", DayMonth(12, 3)),
    ],
)
def test_day_and_month_forms(raw: str, expected: DayMonth) -> None:
    assert day_month(raw).value == expected


def test_day_and_month_follow_the_date_order() -> None:
    assert day_month("12/03", CleanOptions(date_order="mdy")).value == DayMonth(3, 12)


def test_full_date_given_for_a_birthday_field() -> None:
    result = day_month("09/06/1984")
    assert result.value == DayMonth(9, 6)
    assert result.changes == (Change(ChangeCode.YEAR_DISCARDED),)


def test_iso_date_given_for_a_birthday_field() -> None:
    result = day_month("1984-06-09")
    assert result.value == DayMonth(9, 6)
    assert result.changes == (Change(ChangeCode.YEAR_DISCARDED),)


def test_leap_day() -> None:
    result = day_month("29/02")
    assert result.value == DayMonth(29, 2)
    assert result.changes == ()


def test_impossible_day() -> None:
    result = day_month("31/04")
    assert result.value is None
    assert result.issue is not None
    assert result.issue.code is IssueCode.INVALID_DATE


def test_a_full_date_that_does_not_exist_is_not_a_birthday() -> None:
    assert code_of(day_month("29/02/1990")) is IssueCode.INVALID_DATE


def test_day_and_month_that_is_not_a_date() -> None:
    assert day_month("soon").issue is not None
    assert day_month("13/13").issue is not None


def test_day_and_month_no_year_is_invented() -> None:
    assert isinstance(day_month("12/03").value, DayMonth)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("9:30", dt.time(9, 30)),
        ("09:30:15", dt.time(9, 30, 15)),
        ("23:59", dt.time(23, 59)),
        ("9h30", dt.time(9, 30)),
        ("9h", dt.time(9, 0)),
        ("9:30 PM", dt.time(21, 30)),
        ("12:00 am", dt.time(0, 0)),
        ("12:15 pm", dt.time(12, 15)),
        ("10:30:00.250", dt.time(10, 30, 0, 250000)),
    ],
)
def test_time_forms(raw: str, expected: dt.time) -> None:
    result = time(raw)
    assert result.value == expected
    assert result.changes == ()


@pytest.mark.parametrize("raw", ["25:00", "9:60", "13:00 pm", "0:30 am", "noon", "9", "9:3"])
def test_time_that_is_not_a_time(raw: str) -> None:
    result = time(raw)
    assert result.value is None
    assert result.issue is not None
    assert result.issue.code is IssueCode.NOT_A_TIME


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2024-03-05T10:30:00", dt.datetime(2024, 3, 5, 10, 30)),
        ("2024-03-05 10:30", dt.datetime(2024, 3, 5, 10, 30)),
        ("05/03/2024 9h30", dt.datetime(2024, 3, 5, 9, 30)),
        ("5 mar 2024 14:00", dt.datetime(2024, 3, 5, 14, 0)),
    ],
)
def test_datetime_forms(raw: str, expected: dt.datetime) -> None:
    result = datetime(raw)
    assert result.value == expected
    assert result.changes == ()


def test_datetime_of_a_date_only_reports_the_midnight() -> None:
    result = datetime("05/03/2024")
    assert result.value == dt.datetime(2024, 3, 5)
    assert result.changes == (Change(ChangeCode.TIME_DEFAULTED),)


def test_datetime_from_a_serial_number() -> None:
    result = datetime("45000.75")
    assert result.value == dt.datetime(2023, 3, 15, 18, 0)
    assert result.changes == (Change(ChangeCode.SERIAL_DATE_CONVERTED),)


def test_datetime_issues_come_from_the_part_that_failed() -> None:
    assert code_of(datetime("31/02/2024 10:00")) is IssueCode.INVALID_DATE
    assert code_of(datetime("05/03/2024 25:00")) is IssueCode.NOT_A_TIME
    assert code_of(datetime("10:30")) is IssueCode.NOT_A_DATE
    assert code_of(datetime("whenever")) is IssueCode.NOT_A_DATE


def test_datetime_carries_the_year_expansion() -> None:
    result = datetime("3/11/91 10:00")
    assert result.value == dt.datetime(1991, 11, 3, 10, 0)
    assert result.changes == (Change(ChangeCode.TWO_DIGIT_YEAR_EXPANDED, {"year": 1991}),)


@pytest.mark.parametrize("cleaner", [date, day_month, time, datetime])
def test_blank_input(cleaner: Callable[[str], Cleaned[Any]]) -> None:
    result = cleaner("  ")
    assert (result.value, result.issue, result.changes) == (None, None, ())


def test_two_digit_year_after_a_month_name() -> None:
    result = date("12-mar-88")
    assert result.value == dt.date(1988, 3, 12)
    assert result.changes == (Change(ChangeCode.TWO_DIGIT_YEAR_EXPANDED, {"year": 1988}),)


def test_a_three_digit_day_is_not_a_date() -> None:
    assert code_of(date("123 mar 1988")) is IssueCode.NOT_A_DATE


@pytest.mark.parametrize("cleaner", [date, datetime])
def test_a_huge_digit_run_is_an_issue_not_an_error(cleaner: Callable[..., Cleaned[Any]]) -> None:
    result = cleaner("9" * 5000)
    assert result.value is None
    assert result.issue is not None
    assert result.issue.code is IssueCode.NOT_A_DATE


@pytest.mark.parametrize(
    "raw",
    [
        "\uff12\uff10\uff12\uff14-\uff10\uff13-\uff10\uff14",
        "\u0660\u0663/\u0660\u0664/\u0661\u0669\u0669\u0660",
        "\uff13 mar 2024",
    ],
)
def test_digits_of_other_scripts_are_not_a_date(raw: str) -> None:
    result = date(raw)
    assert result.value is None
    assert result.issue is not None
    assert result.issue.code is IssueCode.NOT_A_DATE


def test_digits_of_other_scripts_are_not_a_time() -> None:
    result = time("\u0660\u0669:\u0663\u0660")
    assert result.value is None
    assert result.issue is not None
    assert result.issue.code is IssueCode.NOT_A_TIME


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("3pm", dt.time(15)), ("12 am", dt.time(0)), ("12 PM", dt.time(12)), ("9 a.m.", dt.time(9))],
)
def test_a_bare_hour_with_a_meridiem(raw: str, expected: dt.time) -> None:
    assert time(raw).value == expected


@pytest.mark.parametrize("raw", ["9", "13pm", "0 am"])
def test_a_bare_hour_needs_a_valid_meridiem(raw: str) -> None:
    assert code_of(time(raw)) is IssueCode.NOT_A_TIME


def test_a_datetime_with_a_bare_hour_and_a_meridiem() -> None:
    assert datetime("2024-03-05 3pm").value == dt.datetime(2024, 3, 5, 15)
