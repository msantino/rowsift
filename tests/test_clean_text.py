"""Text, name, boolean and category cleaners, and the options and contract they share."""

from collections.abc import Callable
from typing import Any

import pytest

from rowsift.clean import CleanOptions, boolean, category, decimal, integer, money, name, text
from rowsift.types import Change, ChangeCode, Cleaned, IssueCode

ALL_CLEANERS: list[Callable[..., Cleaned[Any]]] = [
    text,
    name,
    boolean,
    category,
    integer,
    decimal,
    money,
]


@pytest.mark.parametrize("cleaner", ALL_CLEANERS)
@pytest.mark.parametrize("blank", ["", "   ", "\t\n", "\u00a0"])
def test_empty_input(cleaner: Callable[..., Cleaned[Any]], blank: str) -> None:
    result = cleaner(blank)
    assert result.value is None
    assert result.issue is None
    assert result.changes == ()


def test_text_is_trimmed() -> None:
    assert text("  hello  world \n").value == "hello  world"


def test_all_uppercase() -> None:
    result = name("HELENA PIRES DE ARAUJO", CleanOptions(name_case="title"))
    assert result.value == "Helena Pires de Araujo"
    assert result.changes == (Change(ChangeCode.CASE_CHANGED),)


def test_all_lowercase_is_recased_with_default_options() -> None:
    result = name("joao  da   silva e souza")
    assert result.value == "Joao da Silva e Souza"
    assert result.changes == (Change(ChangeCode.CASE_CHANGED),)


def test_mixed_case_is_kept() -> None:
    result = name("Ana McAllister")
    assert result.value == "Ana McAllister"
    assert result.changes == ()


def test_name_whitespace_is_collapsed_without_a_change() -> None:
    result = name("  Ana   Lima ")
    assert result.value == "Ana Lima"
    assert result.changes == ()


def test_name_case_keep_never_recases() -> None:
    result = name("HELENA PIRES", CleanOptions(name_case="keep"))
    assert result.value == "HELENA PIRES"
    assert result.changes == ()


def test_recasing_handles_hyphens_and_apostrophes() -> None:
    assert name("MARIA-CLARA D'AVILA").value == "Maria-Clara D'Avila"


def test_a_leading_particle_is_capitalized() -> None:
    assert name("DE LA CRUZ").value == "De La Cruz"


def test_a_name_without_letters_is_kept() -> None:
    result = name("1234")
    assert result.value == "1234"
    assert result.changes == ()


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("Sim", True), ("SIM", True), ("yes", True), ("1", True), ("Não", False), ("false", False)],
)
def test_boolean_word(raw: str, expected: bool) -> None:
    assert boolean(raw).value is expected


def test_boolean_that_is_no_word_is_an_issue() -> None:
    result = boolean("maybe")
    assert result.value is None
    assert result.issue is not None
    assert result.issue.code is IssueCode.NOT_A_BOOLEAN


def test_category_outside_the_allowed_values() -> None:
    options = CleanOptions(one_of=("Morning", "Afternoon", "Night"))
    result = category("Evening", options)
    assert result.value is None
    assert result.issue is not None
    assert result.issue.code is IssueCode.NOT_IN_ALLOWED_VALUES


def test_category_returns_the_declared_spelling() -> None:
    options = CleanOptions(one_of=("Manhã", "Tarde"))
    assert category("  manha ", options).value == "Manhã"


def test_category_without_allowed_values_keeps_the_text() -> None:
    assert category(" anything ").value == "anything"


def test_options_defaults() -> None:
    options = CleanOptions()
    assert (options.region, options.date_order, options.decimal_separator) == ("BR", "dmy", ",")
    assert options.two_digit_year_pivot == 30
    assert options.insert_ninth_digit is True
    assert options.name_case == "title"
    assert options.require_mobile is False
    assert options.one_of is None


def test_options_normalize_the_region_and_the_allowed_values() -> None:
    options = CleanOptions(region="br", one_of=["a", "b"])  # type: ignore[arg-type]  # list on purpose
    assert options.region == "BR"
    assert options.one_of == ("a", "b")


@pytest.mark.parametrize(
    "bad",
    [
        {"region": "BRA"},
        {"region": "1B"},
        {"date_order": "ymd"},
        {"decimal_separator": ";"},
        {"two_digit_year_pivot": 100},
        {"two_digit_year_pivot": -1},
        {"name_case": "upper"},
    ],
)
def test_invalid_options_are_refused(bad: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="must"):
        CleanOptions(**bad)


@pytest.mark.parametrize(
    "kwargs",
    [{"one_of": "abc"}, {"one_of": (1, 2)}, {"insert_ninth_digit": 1}, {"require_mobile": "yes"}],
)
def test_options_are_type_checked(kwargs: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="must be"):
        CleanOptions(**kwargs)


@pytest.mark.parametrize("raw", ["ß", "STRAßE", "İSTANBUL"])
def test_a_name_whose_recasing_changes_the_letters_is_kept(raw: str) -> None:
    result = name(raw)
    assert result.value == raw
    assert result.changes == ()


@pytest.mark.parametrize(
    "raw",
    [
        "\N{FULLWIDTH DIGIT ONE}",
        "\N{FULLWIDTH LATIN CAPITAL LETTER S}",
        "\N{ARABIC-INDIC DIGIT ONE}",
    ],
)
def test_boolean_does_not_accept_compatibility_forms(raw: str) -> None:
    assert boolean(raw).issue is not None
    assert boolean(raw).issue.code is IssueCode.NOT_A_BOOLEAN  # type: ignore[union-attr]
