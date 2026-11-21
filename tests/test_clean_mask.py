"""Masking functions."""

import pytest

from rowsift.clean import mask, mask_cnpj, mask_cpf, mask_email, mask_name, mask_phone
from rowsift.types import Kind


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("(11) 99999-0042", "11 *******42"),
        ("+55 11 3333-0042", "11 ******42"),
        ("11999990042", "11 *******42"),
    ],
)
def test_a_phone_keeps_the_area_code_and_the_last_two_digits(raw: str, expected: str) -> None:
    assert mask_phone(raw) == expected


@pytest.mark.parametrize("raw", ["call Ana at 5", "99999-0042", "1.1E+10"])
def test_a_phone_column_value_that_is_no_phone_is_hidden(raw: str) -> None:
    masked = mask_phone(raw)
    assert not any(char.isalnum() for char in masked)
    assert len(masked) == len(raw)


def test_a_cpf_keeps_the_last_two_digits() -> None:
    assert mask_cpf("290.471.836-09") == "***.***.***-09"
    assert mask_cpf("29047183609") == "*********09"


def test_a_cnpj_keeps_the_last_two_digits() -> None:
    assert mask_cnpj("40.718.263/0001-55") == "**.***.***/****-55"


def test_a_tax_id_with_letters_is_hidden() -> None:
    assert mask_cpf("pending 123") == "******* ***"


def test_an_email_keeps_the_first_character_and_the_domain() -> None:
    assert mask_email("ana.lima@example.com") == "a***@example.com"


@pytest.mark.parametrize("raw", ["ana.lima", "a@b@c", "@example.com", "ana@", "ana lima@x.com"])
def test_something_that_is_no_email_is_hidden(raw: str) -> None:
    assert not any(char.isalnum() for char in mask_email(raw))


def test_a_name_keeps_the_first_name_and_the_initials() -> None:
    assert mask_name("Helena Pires de Araujo") == "Helena P. A."
    assert mask_name("Helena") == "Helena"
    assert mask_name("  ") == "  "


@pytest.mark.parametrize(
    ("kind", "raw", "expected"),
    [
        (Kind.PHONE, "(11) 99999-0042", "11 *******42"),
        (Kind.CPF, "290.471.836-09", "***.***.***-09"),
        (Kind.CNPJ, "40718263000155", "************55"),
        (Kind.EMAIL, "ana@example.com", "a***@example.com"),
        (Kind.NAME, "Ana Lima", "Ana L."),
        (Kind.TEXT, "free text stays", "free text stays"),
        (Kind.DATE, "03/04/1990", "03/04/1990"),
        (Kind.CATEGORY, "Morning", "Morning"),
    ],
)
def test_masking_by_kind(kind: Kind, raw: str, expected: str) -> None:
    assert mask(raw, kind) == expected


@pytest.mark.parametrize(
    "raw", ["ana@x.com", "12345678909", "note: call mom", "Ana 42", "\u0661\u0662\u0663"]
)
def test_a_name_column_with_no_name_is_hidden(raw: str) -> None:
    masked = mask_name(raw)
    assert not any(char.isalnum() for char in masked)
    assert len(masked) == len(raw)


def test_names_with_punctuation_are_still_masked_by_initials() -> None:
    assert mask_name("Ana D'Avila-Souza Lima") == "Ana D. L."


def test_a_foreign_phone_number_is_hidden() -> None:
    assert mask_phone("+1 415 555 0132") == "+* *** *** ****"
    assert mask_phone("+55 11 99999-0042") == "11 *******42"
