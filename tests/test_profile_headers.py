"""Header normalization and column names."""

from rowsift.profile import normalize_header, profile
from tests.profile_helpers import table


def test_accents_and_punctuation() -> None:
    result = profile(table(("Dt. Nascimento ", "Name"), ("12/03/1990", "Ana")))
    assert result.columns[0].header == "Dt. Nascimento "
    assert result.columns[0].normalized_header == "dt nascimento"


def test_duplicate_headers() -> None:
    result = profile(
        table(("Phone", "Name", "Phone"), ("(11) 99999-0001", "Ana", "(11) 99999-0002"))
    )
    assert [c.normalized_header for c in result.columns] == ["phone", "name", "phone 2"]
    assert [c.header for c in result.columns] == ["Phone", "Name", "Phone"]


def test_empty_header_is_named_by_position() -> None:
    result = profile(table(("Name", "", "Phone"), ("Ana", "x", "(11) 99999-0001")))
    assert [c.normalized_header for c in result.columns] == ["name", "column_2", "phone"]
    assert result.columns[1].header == ""


def test_a_generated_name_never_collides_with_a_written_one() -> None:
    result = profile(table(("Column 1", "", "Phone"), ("a", "b", "(11) 99999-0001")))
    names = [c.normalized_header for c in result.columns]
    assert len(set(names)) == 3


def test_normalize_header_rules() -> None:
    assert normalize_header("  Endereço_de  E-mail!! ") == "endereco de e mail"
    assert normalize_header("ÇÃO") == "cao"
    assert normalize_header("") == ""
    assert normalize_header("###") == ""
