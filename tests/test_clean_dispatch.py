"""The dispatcher and the public surface of the clean layer."""

import datetime as dt
from decimal import Decimal

import pytest

import rowsift.clean as clean
from rowsift.clean import CleanOptions
from rowsift.types import DayMonth, Kind


def test_dispatch_by_kind() -> None:
    assert clean.value("12/03", Kind.DAY_MONTH) == clean.day_month("12/03")
    assert clean.value("12/03", Kind.DAY_MONTH).value == DayMonth(12, 3)


@pytest.mark.parametrize(
    ("kind", "raw", "expected"),
    [
        (Kind.TEXT, " a ", "a"),
        (Kind.NAME, "ANA LIMA", "Ana Lima"),
        (Kind.INTEGER, "1.234", 1234),
        (Kind.DECIMAL, "1,5", Decimal("1.5")),
        (Kind.MONEY, "R$ 10,00", Decimal("10.00")),
        (Kind.BOOLEAN, "sim", True),
        (Kind.DATE, "03/04/1990", dt.date(1990, 4, 3)),
        (Kind.DAY_MONTH, "03/04", DayMonth(3, 4)),
        (Kind.TIME, "9h30", dt.time(9, 30)),
        (Kind.DATETIME, "03/04/1990 9h30", dt.datetime(1990, 4, 3, 9, 30)),
        (Kind.PHONE, "(11) 3333-0042", "+551133330042"),
        (Kind.EMAIL, "Ana@Example.com", "Ana@example.com"),
        (Kind.POSTAL_CODE, "01310-100", "01310100"),
        (Kind.CATEGORY, "x", "x"),
    ],
)
def test_every_kind_has_a_cleaner(kind: Kind, raw: str, expected: object) -> None:
    assert clean.value(raw, kind).value == expected


def test_every_kind_is_covered() -> None:
    covered = {Kind.CPF, Kind.CNPJ}
    assert covered | {
        Kind.TEXT, Kind.NAME, Kind.INTEGER, Kind.DECIMAL, Kind.MONEY, Kind.BOOLEAN,
        Kind.DATE, Kind.DAY_MONTH, Kind.TIME, Kind.DATETIME, Kind.PHONE, Kind.EMAIL,
        Kind.POSTAL_CODE, Kind.CATEGORY,
    } == set(Kind)  # fmt: skip
    for kind in Kind:
        assert clean.value("", kind).value is None


def test_dispatch_passes_the_options_and_accepts_the_kind_as_text() -> None:
    options = CleanOptions(one_of=("Night",))
    assert clean.value("night", "category", options).value == "Night"  # type: ignore[arg-type]  # a str is accepted
    assert clean.value("03/04/1990", Kind.DATE, CleanOptions(date_order="mdy")).value == (
        dt.date(1990, 3, 4)
    )


def test_dispatch_refuses_a_name_that_is_no_kind() -> None:
    with pytest.raises(ValueError, match="is not a valid Kind"):
        clean.value("x", "nonsense")  # type: ignore[arg-type]  # on purpose


def test_every_exported_name_exists() -> None:
    for name in clean.__all__:
        assert hasattr(clean, name)


JUNK = [
    "\x00",
    "\u202e",
    "\u0663\u0664\u0665",
    "\uff11\uff12\uff13",
    "1e999",
    "-",
    "()",
    ".",
    "@",
    "/ / /",
    "0" * 500,
    "\u00e9" * 300,
]


@pytest.mark.parametrize("kind", [kind for kind in Kind if kind is not Kind.CATEGORY])
def test_no_cleaner_raises_on_junk(kind: Kind) -> None:
    for raw in JUNK:
        result = clean.value(raw, kind)
        assert result.value is None or result.issue is None


def test_the_text_parameter_is_named_text() -> None:
    assert clean.value(text="42", kind=Kind.INTEGER).value == 42
