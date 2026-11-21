"""Kind inference per column."""

import pytest

from rowsift.clean import CleanOptions
from rowsift.profile import ColumnProfile, ProfileOptions, profile
from rowsift.types import Kind
from tests.profile_helpers import phone, table


def cpf(base: int) -> str:
    """A synthetic CPF: nine digits from ``base`` plus valid check digits."""
    digits = [int(c) for c in f"{base:09d}"]
    for length in (9, 10):
        total = sum(d * w for d, w in zip(digits, range(length + 1, 1, -1), strict=True))
        digits.append(total * 10 % 11 % 10)
    return "".join(map(str, digits))


def one_column(
    values: list[str], header: str = "Value", options: ProfileOptions | None = None
) -> ColumnProfile:
    rows = [(header,), *[(v,) for v in values]]
    return profile(table(*rows), options).columns[0]


def test_column_of_mobile_numbers_in_mixed_formats() -> None:
    forms = ["(11) 99999-{n}", "1199999{n}", "+55 11 99999-{n}", "11 9 9999-{n}"]
    values = [forms[i % 4].format(n=f"{i:04d}") for i in range(95)] + ["no phone"] * 5
    column = one_column(values, "Contact")
    assert column.kind is Kind.PHONE
    assert column.kind_share == 0.95


def test_day_and_month_without_a_year() -> None:
    column = one_column(["12/03", "05/11", "29/02", "01/01", "30/12"])
    assert column.kind is Kind.DAY_MONTH
    assert column.kind_share == 1.0


def test_tax_id_stored_as_a_number() -> None:
    column = one_column([cpf(100000000 + i * 37) for i in range(10)])
    assert column.kind is Kind.CPF
    assert column.runner_up is not None
    assert column.runner_up.kind is Kind.INTEGER


def test_mixed_content() -> None:
    values = ["12/03/1990", "01/02/1985", "see notes", "to confirm"] * 5
    column = one_column(values)
    assert column.kind is Kind.TEXT
    assert column.runner_up is not None
    assert (column.runner_up.kind, column.runner_up.share) == (Kind.DATE, 0.5)


@pytest.mark.parametrize(
    ("values", "kind"),
    [
        (["ana@example.com", "bia@example.org", "cai@example.net"], Kind.EMAIL),
        (["12/03/1990", "01/02/1985", "30/12/2001"], Kind.DATE),
        (["12/03/1990 10:30", "01/02/1985 08:00", "30/12/2001 23:15"], Kind.DATETIME),
        (["10:30", "08:00", "23:15"], Kind.TIME),
        (["sim", "nao", "sim", "sim"], Kind.BOOLEAN),
        (["01310-100", "20040-020", "30130-010"], Kind.POSTAL_CODE),
        (["R$ 10,00", "R$ 2.500,50", "R$ 3,25"], Kind.MONEY),
        (["10", "250", "3", "-4"], Kind.INTEGER),
        (["10,5", "250,25", "3", "4,1"], Kind.DECIMAL),
        (["Ana Lima", "Bia Souza", "Caio Lima"], Kind.TEXT),
    ],
)
def test_each_kind_is_inferred(values: list[str], kind: Kind) -> None:
    assert one_column(values).kind is kind


def test_a_money_amount_needs_a_currency_symbol() -> None:
    assert one_column(["10,00", "2,50", "3,25"]).kind is Kind.DECIMAL


def test_spreadsheet_serials_do_not_make_a_date_column() -> None:
    assert one_column(["45000", "45001", "45002"]).kind is Kind.INTEGER


def test_a_bare_date_is_not_a_datetime_and_a_full_date_is_not_a_day_and_month() -> None:
    assert one_column(["12/03/1990", "01/02/1985"]).kind is Kind.DATE


def test_a_postal_code_that_lost_its_zero_is_not_guessed() -> None:
    assert one_column(["1310100", "2004002", "3013001"]).kind is Kind.INTEGER


def test_the_threshold_is_an_option() -> None:
    values = ["12/03", "05/11", "29/02", "01/01", "see notes", "to confirm"]
    assert one_column(values).kind is Kind.TEXT
    assert one_column(values, options=ProfileOptions(kind_threshold=0.6)).kind is Kind.DAY_MONTH
    assert one_column(values, options=ProfileOptions(kind_threshold=0.7)).kind is Kind.TEXT


def test_the_clean_options_reach_the_cleaners() -> None:
    values = ["03/13/1990", "04/25/1985"]
    assert one_column(values).kind is Kind.TEXT
    options = ProfileOptions(clean=CleanOptions(date_order="mdy"))
    assert one_column(values, options=options).kind is Kind.DATE


def test_only_the_sample_is_read_for_the_kind() -> None:
    values = ["12/03", "05/11"] + ["not a day"] * 8
    options = ProfileOptions(sample_rows=2)
    column = one_column(values, options=options)
    assert column.kind is Kind.DAY_MONTH
    assert column.filled == 10


def test_a_column_with_no_filled_cell_is_text_with_no_share() -> None:
    column = one_column(["", " "])
    assert (column.kind, column.kind_share, column.runner_up) == (Kind.TEXT, 0.0, None)


def test_a_text_column_with_nothing_close_has_no_runner_up() -> None:
    column = one_column(["Ana Lima", "Bia Souza"])
    assert (column.kind, column.kind_share, column.runner_up) == (Kind.TEXT, 1.0, None)


def test_a_phone_column_beats_integer_at_equal_share() -> None:
    column = one_column(
        [phone(i).replace("(", "").replace(") ", "").replace("-", "") for i in range(5)]
    )
    assert column.kind is Kind.PHONE


def test_a_date_of_eight_digits_is_not_a_postal_code() -> None:
    assert one_column(["03/13/1990", "04/25/1985"]).kind is Kind.TEXT


def test_a_column_of_zero_and_one_is_a_boolean_whatever_its_length() -> None:
    # Documented ambiguity: 0 and 1 are boolean literals, so a count column that
    # holds only 0 and 1 reads as boolean. A 2 anywhere makes it an integer.
    assert profile(table(("Qty",), ("1",))).columns[0].kind is Kind.BOOLEAN
    assert profile(table(("Qty",), ("1",), ("2",))).columns[0].kind is Kind.INTEGER


def test_a_cell_longer_than_any_value_is_never_a_typed_value() -> None:
    assert one_column(["1" * 300] * 5).kind is Kind.TEXT
