"""Sifting: one test per scenario of the sifting requirements."""

from decimal import Decimal

import pytest

import rowsift
from rowsift import Field, Kind, read, suggest
from rowsift.clean import CleanOptions
from rowsift.sift import Rejection, SiftedRow, SiftResult, sift
from rowsift.types import ChangeCode, DayMonth, Issue, IssueCode, Table

HEADER = "Name;Phone;Birthday;Shift\n"


def run(
    text: str,
    fields: list[Field],
    *,
    include_extras: bool = True,
    options: CleanOptions | None = None,
) -> SiftResult:
    """Read, profile, map and sift one file, the way an application would."""
    table = read(text.encode())
    profile = rowsift.profile(table)
    mapping = suggest(profile, fields)
    return sift(table, profile, mapping, fields, include_extras=include_extras, options=options)


def people(*, phone_required: bool = False, birthday_required: bool = False) -> list[Field]:
    return [
        Field("name", Kind.NAME, required=True),
        Field("phone", Kind.PHONE, required=phone_required),
        Field("birthday", Kind.DAY_MONTH, required=birthday_required),
    ]


def test_typed_values() -> None:
    result = run(HEADER + "ana lima;(11) 99999-0001;12/03;morning\n", people())
    (row,) = result.rows
    assert row.values["name"] == "Ana Lima"
    assert row.values["phone"] == "+5511999990001"
    assert row.values["birthday"] == DayMonth(12, 3)
    assert row.changes["name"][0].code is ChangeCode.CASE_CHANGED


def test_row_number_points_to_the_file() -> None:
    text = "Customer list;;;\n;;;\n" + HEADER + "Ana Lima;(11) 99999-0001;12/03;morning\n"
    result = run(text, people())
    assert [row.number for row in result.rows] == [4]


def test_row_number_survives_skipped_rows_inside_the_data() -> None:
    text = (
        HEADER
        + "Ana Lima;(11) 99999-0001;12/03;morning\n"
        + ";;;\n"
        + "Bia Souza;(11) 99999-0002;05/11;night\n"
    )
    result = run(text, people())
    assert [row.number for row in result.rows] == [2, 4]
    assert result.summary.data_rows == 2


def test_required_phone_is_invalid() -> None:
    text = HEADER + "".join(f"Person {chr(65 + i)};(11) 99999-000{i};12/03;x\n" for i in range(5))
    text += "Gui Neves;(11) 9999-0001;01/01;x\n"
    result = run(text, people(phone_required=True))
    assert [row.number for row in result.rows] == [2, 3, 4, 5, 6]
    assert result.rejected == (Rejection(7, "phone", Issue(IssueCode.TRUNCATED, {"digits": 10})),)
    assert result.summary.rejected == 1
    assert result.summary.kept == 5


def test_required_value_is_empty() -> None:
    result = run(HEADER + "Ana Lima;;12/03;x\n", people(phone_required=True))
    assert result.rows == ()
    assert result.rejected == (Rejection(2, "phone", Issue(IssueCode.REQUIRED_MISSING)),)
    assert result.summary.fields["phone"].issues == {IssueCode.REQUIRED_MISSING: 1}


def test_a_row_with_two_failing_required_fields_counts_once() -> None:
    result = run(
        HEADER + "Ana Lima;;;x\n",
        people(phone_required=True, birthday_required=True),
    )
    assert [r.field for r in result.rejected] == ["phone", "birthday"]
    assert result.summary.rejected == 1


def test_optional_birthday_is_invalid() -> None:
    result = run(HEADER + "Ana Lima;(11) 99999-0001;31/02;x\n", people())
    (row,) = result.rows
    assert row.values["birthday"] is None
    assert row.issues["birthday"].code is IssueCode.INVALID_DATE
    assert result.rejected == ()
    assert result.summary.fields["birthday"].issues == {IssueCode.INVALID_DATE: 1}


def test_an_empty_optional_value_is_none_without_an_issue() -> None:
    result = run(HEADER + "Ana Lima;;12/03;x\n", people())
    (row,) = result.rows
    assert row.values["phone"] is None
    assert dict(row.issues) == {}


def test_required_field_has_no_column() -> None:
    table = read(b"Name;Shift\nAna Lima;morning\n")
    profile = rowsift.profile(table)
    fields = people(phone_required=True)
    with pytest.raises(ValueError, match="phone"):
        sift(table, profile, suggest(profile, fields), fields)


def test_an_optional_field_with_no_column_is_none_in_every_row() -> None:
    result = run("Name;Shift\nAna Lima;morning\n", people())
    (row,) = result.rows
    assert row.values == {"name": "Ana Lima", "phone": None, "birthday": None}
    assert result.summary.fields["phone"].filled == 0


def test_extra_column_preserved() -> None:
    result = run(HEADER + "Ana Lima;(11) 99999-0001;12/03;Morning shift\n", people())
    assert result.rows[0].extras == {"shift": "Morning shift"}


def test_extras_can_be_left_out() -> None:
    result = run(
        HEADER + "Ana Lima;(11) 99999-0001;12/03;morning\n", people(), include_extras=False
    )
    assert dict(result.rows[0].extras) == {}


def test_counts_of_ninth_digits_inserted() -> None:
    text = HEADER + "".join(f"Person {i};(11) 8888-{i:04d};12/03;x\n" for i in range(58))
    text += "Other;(11) 99999-0001;12/03;x\n"
    result = run(text, people())
    phone = result.summary.fields["phone"]
    assert phone.changes["ninth_digit_inserted"] == 58
    assert phone.filled == 59
    assert result.summary.data_rows == 59


def test_the_summary_counts_rejected_rows_too() -> None:
    text = HEADER + "Ana Lima;(11) 9999-0001;12/03;x\nBia Souza;(11) 8888-0001;12/03;x\n"
    result = run(text, people(phone_required=True))
    phone = result.summary.fields["phone"]
    assert (result.summary.kept, result.summary.rejected) == (1, 1)
    assert phone.issues == {IssueCode.TRUNCATED: 1}
    assert phone.changes == {ChangeCode.NINTH_DIGIT_INSERTED: 1}
    assert phone.filled == 1


def test_calling_twice() -> None:
    table = read((HEADER + "Ana Lima;(11) 9999-0001;31/02;x\nBia;;;y\n").encode())
    profile = rowsift.profile(table)
    fields = people(phone_required=True)
    mapping = suggest(profile, fields)
    before = (table, profile, mapping)
    first = sift(table, profile, mapping, fields)
    second = sift(table, profile, mapping, fields)
    assert first == second
    assert (table, profile, mapping) == before


def test_the_result_cannot_be_changed_through_a_row() -> None:
    (row,) = run(HEADER + "Ana Lima;;;x\n", people()).rows
    assert isinstance(row, SiftedRow)
    with pytest.raises(TypeError):
        row.values["name"] = "x"  # type: ignore[index]  # mappingproxy rejects item assignment


def test_a_field_option_replaces_the_call_option() -> None:
    fields = [
        Field("name", Kind.NAME, options=CleanOptions(name_case="keep")),
        Field("price", Kind.MONEY),
    ]
    table = read(b"Name;Price\nANA LIMA;1.234,50\n")
    profile = rowsift.profile(table)
    result = sift(table, profile, suggest(profile, fields), fields, options=CleanOptions())
    assert result.rows[0].values == {"name": "ANA LIMA", "price": Decimal("1234.50")}


def test_a_category_field_takes_its_allowed_values_from_the_field() -> None:
    fields = [Field("shift", Kind.CATEGORY, required=True, one_of=("morning", "night"))]
    table = read(b"Shift\nmorning\nafternoon\n")
    profile = rowsift.profile(table)
    result = sift(table, profile, suggest(profile, fields), fields)
    assert [row.number for row in result.rows] == [2]
    assert result.rejected[0].issue.code is IssueCode.NOT_IN_ALLOWED_VALUES


def test_a_field_without_a_choice_is_refused() -> None:
    table: Table = read(b"Name\nAna\n")
    profile = rowsift.profile(table)
    mapping = suggest(profile, [Field("name", Kind.NAME)])
    with pytest.raises(ValueError, match="phone"):
        sift(table, profile, mapping, [Field("name", Kind.NAME), Field("phone", Kind.PHONE)])


def test_a_choice_without_a_field_is_refused() -> None:
    table = read(b"Name\nAna\n")
    profile = rowsift.profile(table)
    mapping = suggest(profile, [Field("name", Kind.NAME), Field("phone", Kind.PHONE)])
    with pytest.raises(ValueError, match="phone"):
        sift(table, profile, mapping, [Field("name", Kind.NAME)])


def test_two_fields_with_one_key_are_refused() -> None:
    table = read(b"Name\nAna\n")
    profile = rowsift.profile(table)
    fields = [Field("name", Kind.NAME), Field("name", Kind.TEXT)]
    mapping = suggest(profile, [Field("name", Kind.NAME)])
    with pytest.raises(ValueError, match="share a key"):
        sift(table, profile, mapping, fields)


def test_a_column_outside_the_profile_is_refused() -> None:
    table = read(b"Name;City\nAna;Recife\n")
    profile = rowsift.profile(table)
    fields = [Field("name", Kind.NAME)]
    mapping = suggest(profile, fields).assign("name", 1)
    narrow = rowsift.profile(read(b"Name\nAna\n"))
    with pytest.raises(ValueError, match="not in the profile"):
        sift(table, narrow, mapping, fields)


def test_a_table_with_no_data_rows_gives_an_empty_result() -> None:
    result = run("Name;Phone\n", people())
    assert result.rows == ()
    assert result.rejected == ()
    assert result.summary.data_rows == 0


def test_profile_of_a_wider_table_is_refused() -> None:
    wide = read(b"Name;Phone\nAna Silva;11987654321\n")
    narrow = read(b"Name\nAna Silva\n")
    fields = [Field("name", Kind.NAME, required=True), Field("phone", Kind.PHONE)]
    profile = rowsift.profile(wide)
    mapping = suggest(profile, fields)
    with pytest.raises(ValueError, match="does not match") as caught:
        sift(narrow, profile, mapping, fields)
    assert "Ana" not in str(caught.value)
