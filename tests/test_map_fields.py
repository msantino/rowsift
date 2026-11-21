"""Fields are declared by the caller."""

import dataclasses

import pytest

from rowsift.clean import CleanOptions
from rowsift.map import Field, suggest
from rowsift.types import Kind
from tests.map_helpers import column, profile


def test_duplicate_field_keys() -> None:
    fields = [Field("phone", Kind.PHONE), Field("phone", Kind.PHONE)]
    with pytest.raises(ValueError, match="phone"):
        suggest(profile(column(0, "Celular", Kind.PHONE)), fields)


def test_a_field_is_frozen_and_keeps_its_declaration() -> None:
    field = Field("tier", Kind.CATEGORY, required=True, aliases=["nivel"], one_of=["a", "b"])  # type: ignore[arg-type]  # lists are accepted and stored as tuples
    assert field.aliases == ("nivel",)
    assert field.one_of == ("a", "b")
    with pytest.raises(dataclasses.FrozenInstanceError):
        field.key = "other"  # type: ignore[misc]  # proves the dataclass is frozen


def test_the_kind_is_checked() -> None:
    assert Field("x", "phone").kind is Kind.PHONE  # type: ignore[arg-type]  # a plain string is coerced
    with pytest.raises(ValueError, match="not a valid Kind"):
        Field("x", "nope")  # type: ignore[arg-type]  # proves a bad kind is refused


@pytest.mark.parametrize("key", ["", "  "])
def test_an_empty_key_is_refused(key: str) -> None:
    with pytest.raises(ValueError, match="key"):
        Field(key, Kind.TEXT)


def test_the_key_must_be_text() -> None:
    with pytest.raises(TypeError, match="key"):
        Field(1, Kind.TEXT)  # type: ignore[arg-type]  # proves a non-str key is refused


@pytest.mark.parametrize("name", ["aliases", "one_of"])
def test_a_bare_string_is_not_a_sequence_of_strings(name: str) -> None:
    kwargs = {name: "celular"}
    with pytest.raises(TypeError, match=name):
        Field("x", Kind.CATEGORY, **kwargs)  # type: ignore[arg-type]  # proves a bare str is refused


def test_aliases_must_hold_text() -> None:
    with pytest.raises(TypeError, match="aliases"):
        Field("x", Kind.TEXT, aliases=(1,))  # type: ignore[arg-type]  # proves a non-str alias is refused


def test_only_a_category_may_list_allowed_values() -> None:
    with pytest.raises(ValueError, match="one_of"):
        Field("x", Kind.TEXT, one_of=("a",))


def test_required_must_be_a_bool() -> None:
    with pytest.raises(TypeError, match="required"):
        Field("x", Kind.TEXT, required=1)  # type: ignore[arg-type]  # proves a non-bool is refused


def test_options_must_be_clean_options() -> None:
    assert Field("x", Kind.TEXT, options=CleanOptions()).options == CleanOptions()
    with pytest.raises(TypeError, match="options"):
        Field("x", Kind.TEXT, options={})  # type: ignore[arg-type]  # proves a wrong type is refused
