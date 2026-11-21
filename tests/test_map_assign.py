"""The caller changes a mapping."""

import pytest

from rowsift.map import Alternative, Field, Mapping, suggest
from rowsift.types import Confidence, Kind, Reason, ReasonCode
from tests.map_helpers import column, profile

FIELDS = [
    Field("name", Kind.NAME, aliases=("nome",)),
    Field("phone", Kind.PHONE, aliases=("celular",)),
]


def base() -> Mapping:
    cols = profile(
        column(0, "Nome"),
        column(1, "Obs"),
        column(2, "Celular", Kind.PHONE),
        column(3, "Cel 2", Kind.PHONE),
        column(4, "Shift"),
    )
    return suggest(cols, FIELDS)


def test_person_picks_another_column() -> None:
    original = base()
    assert original.choices[1].column == 2
    changed = original.assign("phone", 3)
    phone = changed.choices[1]
    assert (phone.column, phone.confidence) == (3, Confidence.HIGH)
    assert phone.reasons == (Reason(ReasonCode.SET_BY_CALLER),)
    assert 2 in changed.unmapped
    assert 3 not in changed.unmapped
    assert changed.unmapped == (1, 2, 4)
    assert original.choices[1].column == 2
    assert original.unmapped == (1, 3, 4)


def test_assigning_an_unmapped_column() -> None:
    changed = base().assign("name", 4)
    assert changed.choices[0].column == 4
    assert changed.unmapped == (0, 1, 3)


def test_a_column_taken_from_another_field_leaves_it_empty() -> None:
    changed = base().assign("name", 2)
    name, phone = changed.choices
    assert name.column == 2
    assert (phone.column, phone.confidence) == (None, None)
    assert phone.reasons == (Reason(ReasonCode.SET_BY_CALLER, {"displaced_by": "name"}),)
    assert changed.unmapped == (0, 1, 3, 4)


def test_the_displaced_field_keeps_the_lost_column_as_an_alternative() -> None:
    changed = base().assign("name", 2)
    assert 2 in [a.column for a in changed.choices[1].alternatives]


def test_the_previous_column_becomes_an_alternative() -> None:
    original = base()
    previous = original.choices[1].confidence
    changed = original.assign("phone", 3)
    assert Alternative(2, previous) in changed.choices[1].alternatives  # type: ignore[arg-type]


def test_the_chosen_column_leaves_the_alternatives() -> None:
    original = base()
    assert any(a.column == 3 for a in original.choices[1].alternatives)
    changed = original.assign("phone", 3)
    assert all(a.column != 3 for a in changed.choices[1].alternatives)


def test_unassign_frees_the_column() -> None:
    original = base()
    changed = original.unassign("phone")
    phone = changed.choices[1]
    assert (phone.column, phone.confidence) == (None, None)
    assert phone.reasons == (Reason(ReasonCode.SET_BY_CALLER),)
    assert changed.unmapped == (1, 2, 3, 4)
    assert original.choices[1].column == 2


def test_the_fingerprint_survives_a_change() -> None:
    original = base()
    assert original.assign("phone", 3).fingerprint == original.fingerprint


def test_an_unknown_key_is_refused_by_assign() -> None:
    with pytest.raises(ValueError, match="nope"):
        base().assign("nope", 1)


def test_an_unknown_key_is_refused_by_unassign() -> None:
    with pytest.raises(ValueError, match="nope"):
        base().unassign("nope")


def test_a_column_outside_the_mapping_is_refused() -> None:
    with pytest.raises(ValueError, match="column 9"):
        base().assign("phone", 9)
    with pytest.raises(ValueError, match="column -1"):
        base().assign("phone", -1)


def test_the_column_must_be_an_int() -> None:
    with pytest.raises(TypeError, match="column_index"):
        base().assign("phone", True)
    with pytest.raises(TypeError, match="column_index"):
        base().assign("phone", "3")  # type: ignore[arg-type]  # proves a str is refused


def test_a_mapping_cannot_be_built_with_a_shared_column() -> None:
    from rowsift.map import Choice

    one = Choice("a", 0, Confidence.HIGH)
    two = Choice("b", 0, Confidence.HIGH)
    with pytest.raises(ValueError, match="more than one field"):
        Mapping((one, two), (), "x")
    with pytest.raises(ValueError, match="share a field key"):
        Mapping((one, Choice("a", None, None)), (), "x")
    with pytest.raises(ValueError, match="assigned and unmapped"):
        Mapping((one,), (0,), "x")


def test_a_choice_has_a_column_and_a_confidence_or_neither() -> None:
    from rowsift.map import Choice

    with pytest.raises(ValueError, match="neither"):
        Choice("a", 1, None)


def test_a_mapping_refuses_unsorted_or_negative_unmapped_columns() -> None:
    from rowsift.map import Choice

    one = Choice("a", 0, Confidence.HIGH)
    with pytest.raises(ValueError, match="sorted"):
        Mapping((one,), (3, 1), "x")
    with pytest.raises(ValueError, match="negative"):
        Mapping((one,), (-1,), "x")
    with pytest.raises(ValueError, match="negative"):
        Mapping((Choice("a", -1, Confidence.HIGH),), (), "x")
