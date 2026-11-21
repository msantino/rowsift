import datetime

import pytest

from rowsift.read._cells import cell_text


@pytest.mark.parametrize(
    ("value", "text"),
    [
        (None, ""),
        ("Ana", "Ana"),
        (True, "true"),
        (False, "false"),
        (7, "7"),
        (11999990001.0, "11999990001"),
        (3.0, "3"),
        (7.5, "7.5"),
        (0.1 + 0.2, "0.3"),
        (-2.25, "-2.25"),
        (1.5e20, "150000000000000000000"),
        (1.25e-7, "0.000000125"),
        (float("nan"), "nan"),
        (float("inf"), "inf"),
        (datetime.date(2024, 3, 15), "2024-03-15"),
        (datetime.datetime(2024, 3, 15), "2024-03-15"),
        (datetime.datetime(2024, 3, 15, 13, 45, 30), "2024-03-15T13:45:30"),
        (datetime.datetime(2024, 3, 15, 13, 45, 29, 999_999), "2024-03-15T13:45:30"),
        (datetime.datetime(2024, 3, 15, 23, 59, 59, 999_999), "2024-03-16"),
        (datetime.datetime(2024, 12, 31, 23, 59, 59, 700_000), "2024-12-31T23:59:59"),
        (datetime.datetime(2024, 3, 15, 13, 45, 29, 999_700), "2024-03-15T13:45:30"),
        (datetime.time(23, 59, 59, 700_000), "23:59:59"),
        (datetime.time(23, 59, 59, 999_600), "00:00:00"),
        (datetime.datetime.max, "9999-12-31T23:59:59"),
        (datetime.timedelta(seconds=49529.9996), "13:45:30"),
        (datetime.timedelta(seconds=49529.7), "13:45:29"),
        (datetime.timedelta(seconds=-49529.9996), "-13:45:30"),
        (12345678901234567890.0, "12345678901234600000"),
        (2.0**53, "9007199254740992"),
        (datetime.time(8, 5), "08:05:00"),
        (datetime.timedelta(hours=26, minutes=3), "26:03:00"),
        (datetime.timedelta(seconds=-90), "-00:01:30"),
    ],
)
def test_a_cell_value_becomes_stable_text(value: object, text: str) -> None:
    assert cell_text(value) == text


def test_a_value_of_another_type_is_converted_with_str() -> None:
    assert cell_text(complex(1, 2)) == "(1+2j)"
