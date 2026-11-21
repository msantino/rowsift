"""Saved mappings: serialization and application without guessing."""

import json
import pickle

import pytest

from rowsift.map import Field, SavedMapping, apply_saved, suggest
from rowsift.profile import Profile
from rowsift.types import Confidence, Kind, Reason, ReasonCode
from tests.map_helpers import column, profile

FIELDS = [
    Field("name", Kind.NAME, required=True, aliases=("nome",)),
    Field("birthday", Kind.DAY_MONTH, aliases=("dt nascimento",)),
    Field("phone", Kind.PHONE, aliases=("celular",)),
]


def layout(*headers: str) -> Profile:
    kinds = {"Nome": Kind.TEXT, "Dt Nascimento": Kind.DAY_MONTH, "Celular": Kind.PHONE}
    return profile(*(column(i, h, kinds.get(h, Kind.TEXT)) for i, h in enumerate(headers)))


def saved_from(headers: tuple[str, ...]) -> SavedMapping:
    base = layout(*headers)
    return SavedMapping.from_mapping(suggest(base, FIELDS), base)


def test_round_trip_through_a_dictionary() -> None:
    saved = saved_from(("Nome", "Dt Nascimento", "Celular"))
    assert SavedMapping.from_dict(saved.to_dict()) == saved
    assert SavedMapping.from_dict(json.loads(json.dumps(saved.to_dict()))) == saved


def test_the_dictionary_holds_the_fingerprint_and_the_normalized_headers() -> None:
    saved = saved_from(("Nome", "Dt Nascimento", "Celular"))
    assert saved.to_dict() == {
        "fingerprint": saved.fingerprint,
        "assignments": {"name": "nome", "birthday": "dt nascimento", "phone": "celular"},
    }


def test_a_field_without_a_column_is_not_saved() -> None:
    base = layout("Nome")
    saved = SavedMapping.from_mapping(suggest(base, FIELDS), base)
    assert dict(saved.assignments) == {"name": "nome"}


def test_a_saved_mapping_is_hashable_and_pickles() -> None:
    saved = saved_from(("Nome", "Celular"))
    assert hash(saved) == hash(SavedMapping.from_dict(saved.to_dict()))
    assert pickle.loads(pickle.dumps(saved)) == saved  # round trip of our own value


def test_the_assignments_are_read_only() -> None:
    saved = saved_from(("Nome", "Celular"))
    with pytest.raises(TypeError):
        saved.assignments["x"] = "y"  # type: ignore[index]  # proves the mapping is read-only


def test_from_dict_refuses_a_missing_key() -> None:
    with pytest.raises(ValueError, match="assignments"):
        SavedMapping.from_dict({"fingerprint": "x"})


def test_from_dict_refuses_the_wrong_types() -> None:
    with pytest.raises(TypeError):
        SavedMapping.from_dict({"fingerprint": 1, "assignments": {}})
    with pytest.raises(TypeError):
        SavedMapping.from_dict({"fingerprint": "x", "assignments": []})
    with pytest.raises(TypeError):
        SavedMapping.from_dict({"fingerprint": "x", "assignments": {"a": 1}})


def test_two_fields_on_the_same_header_are_refused() -> None:
    with pytest.raises(ValueError, match="same header"):
        SavedMapping("x", {"a": "nome", "b": "nome"})


def test_from_mapping_refuses_a_profile_of_another_file() -> None:
    mapping = suggest(layout("Nome", "Celular"), FIELDS)
    with pytest.raises(ValueError, match="fingerprint"):
        SavedMapping.from_mapping(mapping, layout("Celular", "Nome"))


def test_same_layout_next_month() -> None:
    headers = ("Nome", "Dt Nascimento", "Celular")
    saved = saved_from(headers)
    result = apply_saved(layout(*headers), FIELDS, saved)
    assert [c.column for c in result.choices] == [0, 1, 2]
    assert all(c.reasons == (Reason(ReasonCode.SAVED_MAPPING),) for c in result.choices)
    assert all(c.confidence is Confidence.HIGH for c in result.choices)
    assert result.unmapped == ()


def test_the_typing_of_the_headers_does_not_matter() -> None:
    saved = saved_from(("Nome", "Dt Nascimento", "Celular"))
    result = apply_saved(layout("NOME", "dt. nascimento", " Celular "), FIELDS, saved)
    assert [c.column for c in result.choices] == [0, 1, 2]
    assert all(c.confidence is Confidence.HIGH for c in result.choices)


def test_one_header_renamed() -> None:
    saved = saved_from(("Nome", "Dt Nascimento", "Celular"))
    result = apply_saved(layout("Nome", "Aniversario", "Celular"), FIELDS, saved)
    name, birthday, phone = result.choices
    assert (name.column, phone.column) == (0, 2)
    assert name.reasons == (Reason(ReasonCode.SAVED_MAPPING),)
    assert name.confidence is Confidence.MEDIUM
    assert (birthday.column, birthday.confidence) == (None, None)
    assert birthday.reasons == (
        Reason(ReasonCode.SAVED_HEADER_MISSING, {"header": "dt nascimento"}),
    )
    assert result.unmapped == (1,)


def test_a_renamed_header_is_never_matched_by_similarity() -> None:
    saved = saved_from(("Nome", "Celular"))
    result = apply_saved(layout("Nome", "Celular 2"), FIELDS, saved)
    assert result.choices[2].column is None
    assert result.unmapped == (1,)


def test_a_new_field_and_a_stale_key() -> None:
    saved = SavedMapping("x", {"name": "nome", "gone": "celular"})
    result = apply_saved(layout("Nome", "Celular"), FIELDS, saved)
    assert [c.field for c in result.choices] == ["name", "birthday", "phone"]
    assert result.choices[1].reasons == ()
    assert result.choices[2].column is None
    required = [Field("tax", Kind.CPF, required=True)]
    assert apply_saved(layout("Nome"), required, saved).choices[0].reasons == (
        Reason(ReasonCode.REQUIRED_FIELD_UNMATCHED),
    )


def test_duplicate_field_keys() -> None:
    with pytest.raises(ValueError, match="name"):
        apply_saved(layout("Nome"), [FIELDS[0], FIELDS[0]], SavedMapping("x"))


def test_an_optional_field_absent_from_the_saved_mapping_has_no_reasons() -> None:
    saved = saved_from(("Nome", "Celular"))
    result = apply_saved(layout("Nome", "Celular"), FIELDS, saved)
    birthday = result.choices[1]
    assert (birthday.column, birthday.confidence, birthday.reasons) == (None, None, ())
