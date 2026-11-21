import copy
import dataclasses
import pickle
from collections.abc import Callable
from enum import StrEnum

import pytest

from rowsift import types
from rowsift.types import (
    Change,
    ChangeCode,
    Cleaned,
    DayMonth,
    FileFormat,
    Issue,
    IssueCode,
    Kind,
    ReadReport,
    Table,
)

VALUE_TYPES = [Change, Issue, Cleaned, DayMonth, ReadReport, Table]
CODE_ENUMS = [
    types.Kind,
    types.Confidence,
    types.FileFormat,
    types.LineType,
    types.ChangeCode,
    types.IssueCode,
    types.ReasonCode,
    types.SkipCode,
    types.ReadNote,
    types.ErrorCode,
]


def make_report() -> ReadReport:
    return ReadReport(format=FileFormat.CSV, row_count=1, column_count=2)


SAMPLES: dict[type, object] = {
    Change: Change(ChangeCode.CASE_CHANGED, {"a": 1, "b": "x"}),
    Issue: Issue(IssueCode.TRUNCATED, {"share": 0.5, "ok": True}),
    Cleaned: Cleaned("v", changes=(Change(ChangeCode.MULTIPLE_VALUES, {"count": 2}),)),
    DayMonth: DayMonth(29, 2),
    ReadReport: make_report(),
    Table: Table(rows=(("a", "b"),), report=make_report()),
}
CLONES: list[Callable[[object], object]] = [
    lambda v: pickle.loads(pickle.dumps(v)),
    copy.copy,
    copy.deepcopy,
]


@pytest.mark.parametrize("cls", VALUE_TYPES)
@pytest.mark.parametrize("clone", CLONES, ids=["pickle", "copy", "deepcopy"])
def test_value_types_survive_pickle_and_copy(cls: type, clone: Callable[[object], object]) -> None:
    value = SAMPLES[cls]
    again = clone(value)
    assert again == value
    assert hash(again) == hash(value)


@pytest.mark.parametrize("cls", VALUE_TYPES)
def test_value_types_are_frozen_dataclasses_with_slots(cls: type) -> None:
    assert dataclasses.is_dataclass(cls)
    assert "__slots__" in vars(cls)
    instance = SAMPLES[cls]
    assert not hasattr(instance, "__dict__")
    field_name = dataclasses.fields(cls)[0].name
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(instance, field_name, None)


@pytest.mark.parametrize("enum_cls", CODE_ENUMS)
def test_codes_are_str_enums_that_serialize_as_plain_strings(enum_cls: type[StrEnum]) -> None:
    for member in enum_cls:
        assert isinstance(member, str)
        assert str(member) == member.value
        assert member.value == member.value.lower()


def test_kind_lists_the_documented_members() -> None:
    assert {kind.value for kind in Kind} == {
        "text", "name", "integer", "decimal", "money", "boolean", "date", "day_month",
        "time", "datetime", "phone", "email", "cpf", "cnpj", "postal_code", "category",
    }  # fmt: skip


def test_confidence_has_three_levels() -> None:
    assert [c.value for c in types.Confidence] == ["high", "medium", "low"]


def test_empty_input_gives_no_value_and_no_issue() -> None:
    cleaned: Cleaned[str] = Cleaned()
    assert cleaned.value is None
    assert cleaned.issue is None
    assert cleaned.changes == ()


def test_cleaned_with_a_value_and_changes() -> None:
    change = Change(ChangeCode.NINTH_DIGIT_INSERTED)
    cleaned = Cleaned("+5511988880042", changes=(change,))
    assert cleaned.value == "+5511988880042"
    assert cleaned.changes == (change,)
    assert cleaned.issue is None


def test_cleaned_with_an_issue_has_no_value() -> None:
    cleaned: Cleaned[str] = Cleaned(issue=Issue(IssueCode.TRUNCATED))
    assert cleaned.value is None
    assert cleaned.issue is not None
    assert cleaned.issue.code is IssueCode.TRUNCATED


def test_cleaned_rejects_a_value_together_with_an_issue() -> None:
    with pytest.raises(ValueError, match="never both"):
        Cleaned("x", issue=Issue(IssueCode.INVALID_DATE))


def test_a_code_carries_structured_data() -> None:
    change = Change(ChangeCode.MULTIPLE_VALUES, {"count": 2})
    assert change.data["count"] == 2
    assert Change(ChangeCode.CASE_CHANGED).data == {}


def test_value_types_cannot_be_modified() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        DayMonth(5, 8).day = 6  # type: ignore[misc]  # proving the instance is frozen


def test_day_month_without_a_year() -> None:
    value = DayMonth(5, 8)
    assert (value.day, value.month) == (5, 8)
    assert value == DayMonth(5, 8)


def test_leap_day_is_a_valid_day_month() -> None:
    assert DayMonth(29, 2) == DayMonth(29, 2)


@pytest.mark.parametrize(("day", "month"), [(30, 2), (31, 4), (0, 1), (1, 0), (1, 13)])
def test_day_month_that_does_not_exist_is_rejected(day: int, month: int) -> None:
    with pytest.raises(ValueError, match=r"does not exist|between"):
        DayMonth(day, month)


def test_read_report_defaults_describe_a_text_file() -> None:
    report = make_report()
    assert report.encoding is None
    assert report.sheet is None
    assert report.sheets == ()
    assert report.notes == ()


def test_table_holds_text_rows_and_its_report() -> None:
    report = make_report()
    table = Table(rows=(("Name", "Phone"),), report=report)
    assert table.rows[0][1] == "Phone"
    assert table.report is report


def test_table_must_match_its_report() -> None:
    report = make_report()
    with pytest.raises(ValueError, match="row_count"):
        Table(rows=(), report=report)
    with pytest.raises(ValueError, match="column_count"):
        Table(rows=(("only",),), report=report)


@pytest.mark.parametrize("cls", [Change, Issue])
def test_code_data_is_read_only_and_copied(cls: type) -> None:
    for code in types.ChangeCode if cls is Change else types.IssueCode:
        source = {"count": 2}
        value = cls(code, source)
        source["count"] = 3
        assert value.data["count"] == 2
        with pytest.raises(TypeError):
            value.data["x"] = 1


@pytest.mark.parametrize("cls", [Change, Issue])
def test_codes_are_hashable_and_usable_as_keys(cls: type) -> None:
    for code in types.ChangeCode if cls is Change else types.IssueCode:
        assert hash(cls(code, {"a": 1})) == hash(cls(code, {"a": 1}))
        assert {cls(code, {"a": 1}): 1}[cls(code, {"a": 1})] == 1
        assert len({cls(code), cls(code), cls(code, {"a": 1})}) == 2


@pytest.mark.parametrize("cls", [Change, Issue])
def test_code_must_belong_to_its_enum(cls: type) -> None:
    with pytest.raises(ValueError, match="is not a valid"):
        cls("zzz")
    other = IssueCode.TRUNCATED if cls is Change else ChangeCode.CASE_CHANGED
    with pytest.raises(ValueError, match="is not a valid"):
        cls(other)


@pytest.mark.parametrize("cls", [Change, Issue])
def test_code_accepts_its_plain_string_value(cls: type) -> None:
    enum = ChangeCode if cls is Change else IssueCode
    member = next(iter(enum))
    assert cls(member.value).code is member


@pytest.mark.parametrize("bad", [{"a": [1]}, {"a": None}, {"a": (1,)}, {1: "x"}])
@pytest.mark.parametrize("cls", [Change, Issue])
def test_data_holds_only_scalars_under_text_keys(cls: type, bad: dict[object, object]) -> None:
    code = next(iter(ChangeCode if cls is Change else IssueCode))
    with pytest.raises(TypeError, match="must be"):
        cls(code, bad)


def test_cleaned_rejects_changes_without_a_value_or_an_issue() -> None:
    with pytest.raises(ValueError, match="changes need"):
        Cleaned(changes=(Change(ChangeCode.CASE_CHANGED),))


def test_cleaned_issue_may_carry_changes() -> None:
    cleaned: Cleaned[str] = Cleaned(
        changes=(Change(ChangeCode.CASE_CHANGED),), issue=Issue(IssueCode.TRUNCATED)
    )
    assert len(cleaned.changes) == 1


@pytest.mark.parametrize(
    "rows", [[("a", "b")], ("ab",), (["a", "b"],), ((1, "b"),), (("a", None),)]
)
def test_table_rows_must_be_a_tuple_of_tuples_of_text(rows: object) -> None:
    with pytest.raises(TypeError, match="tuple of tuples of str"):
        Table(rows=rows, report=make_report())  # type: ignore[arg-type]  # proving the runtime check


def test_table_without_rows_has_no_columns() -> None:
    report = ReadReport(format=FileFormat.CSV, row_count=0, column_count=5)
    with pytest.raises(ValueError, match="no columns"):
        Table(rows=(), report=report)
    assert Table(rows=(), report=ReadReport(format=FileFormat.CSV, row_count=0, column_count=0))


@pytest.mark.parametrize("count", [True, 1.0, "1"])
def test_read_report_counts_must_be_int(count: object) -> None:
    with pytest.raises(TypeError, match="must be int"):
        ReadReport(format=FileFormat.CSV, row_count=count, column_count=1)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="must be int"):
        ReadReport(format=FileFormat.CSV, row_count=1, column_count=count)  # type: ignore[arg-type]


def test_read_report_counts_must_not_be_negative() -> None:
    with pytest.raises(ValueError, match="negative"):
        ReadReport(format=FileFormat.CSV, row_count=-1, column_count=0)
    with pytest.raises(ValueError, match="negative"):
        ReadReport(format=FileFormat.CSV, row_count=0, column_count=-1)


def test_read_report_is_built_by_keyword() -> None:
    with pytest.raises(TypeError):
        ReadReport(FileFormat.CSV, 1, 1)  # type: ignore[arg-type, call-arg]  # proving keyword-only


@pytest.mark.parametrize(("day", "month"), [(True, 1), (1, True), (1.5, 1), (1, 1.0), ("1", 1)])
def test_day_month_rejects_values_that_are_not_int(day: object, month: object) -> None:
    with pytest.raises(TypeError, match="must be int"):
        DayMonth(day, month)  # type: ignore[arg-type]  # proving the runtime check
