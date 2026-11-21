"""Suggestions: confidence, reasons, conflicts and unmapped columns."""

import dataclasses

from rowsift.map import Alternative, Field, suggest
from rowsift.types import Confidence, Kind, Reason, ReasonCode
from tests.map_helpers import column, profile

PHONE = Field("phone", Kind.PHONE, aliases=("celular",))


def test_header_and_content_agree() -> None:
    result = suggest(profile(column(0, "Celular", Kind.PHONE, 0.98)), [PHONE])
    choice = result.choices[0]
    assert (choice.field, choice.column, choice.confidence) == ("phone", 0, Confidence.HIGH)
    assert [r.code for r in choice.reasons] == [
        ReasonCode.HEADER_MATCHES_ALIAS,
        ReasonCode.CONTENT_FITS_KIND,
    ]
    assert choice.reasons[1].data["share"] == 0.98


def test_unusual_header_fitting_content() -> None:
    field = Field("birthday", Kind.DAY_MONTH, aliases=("aniversario", "nascimento"))
    result = suggest(profile(column(0, "Niver", Kind.DAY_MONTH, 0.97)), [field])
    choice = result.choices[0]
    assert (choice.column, choice.confidence) == (0, Confidence.MEDIUM)
    assert choice.reasons == (
        Reason(ReasonCode.CONTENT_FITS_KIND, {"kind": "day_month", "share": 0.97}),
    )


def test_header_matches_content_does_not() -> None:
    telefone = Field("phone", Kind.PHONE, aliases=("telefone",))
    col = column(0, "Telefone", Kind.TEXT, 1.0, runner_up=(Kind.PHONE, 0.1))
    choice = suggest(profile(col), [telefone]).choices[0]
    assert (choice.column, choice.confidence) == (0, Confidence.LOW)
    assert [r.code for r in choice.reasons] == [
        ReasonCode.HEADER_MATCHES_ALIAS,
        ReasonCode.CONTENT_CONFLICTS_WITH_KIND,
    ]
    assert choice.reasons[1].data == {"column_kind": "text", "field_kind": "phone", "share": 0.1}


def test_nothing_fits() -> None:
    field = Field("name", Kind.NAME, required=True, aliases=("nome",))
    result = suggest(
        profile(column(0, "Valor", Kind.MONEY), column(1, "Qtd", Kind.INTEGER)), [field]
    )
    choice = result.choices[0]
    assert (choice.column, choice.confidence) == (None, None)
    assert choice.reasons == (Reason(ReasonCode.REQUIRED_FIELD_UNMATCHED),)
    assert result.unmapped == (0, 1)


def test_an_optional_field_nothing_fits_has_no_reason() -> None:
    choice = suggest(profile(column(0, "Valor", Kind.MONEY)), [PHONE]).choices[0]
    assert (choice.column, choice.confidence, choice.reasons) == (None, None, ())


def test_two_phone_fields_and_two_phone_columns() -> None:
    fields = [PHONE, Field("phone_alt", Kind.PHONE, aliases=("cel 2",))]
    cols = profile(column(0, "Celular", Kind.PHONE), column(1, "Cel 2", Kind.PHONE))
    result = suggest(cols, fields)
    assert [(c.field, c.column) for c in result.choices] == [("phone", 0), ("phone_alt", 1)]
    assert [c.confidence for c in result.choices] == [Confidence.HIGH, Confidence.HIGH]


def test_two_fields_want_the_same_column_and_the_higher_score_wins() -> None:
    fields = [
        Field("phone", Kind.PHONE, aliases=("contato",)),
        Field("phone_alt", Kind.PHONE, aliases=("celular",)),
    ]
    cols = profile(column(0, "Celular", Kind.PHONE), column(1, "Contato 2", Kind.PHONE))
    first, second = suggest(cols, fields).choices
    assert second.column == 0
    assert second.confidence is Confidence.HIGH
    assert first.column == 1
    assert first.confidence is Confidence.MEDIUM
    assert Alternative(0, Confidence.LOW) in first.alternatives


def test_the_loser_lists_the_column_in_alternatives() -> None:
    fields = [Field("a", Kind.PHONE, aliases=("fone",)), Field("b", Kind.PHONE, aliases=("fone",))]
    cols = profile(column(0, "Fone", Kind.PHONE), column(1, "Outro", Kind.PHONE))
    a, b = suggest(cols, fields).choices
    assert a.column == 0
    assert b.column == 1
    assert b.confidence is Confidence.LOW
    assert b.alternatives == (Alternative(0, Confidence.HIGH),)


def test_extra_column_in_the_file() -> None:
    cols = profile(column(0, "Celular", Kind.PHONE), column(1, "Shift", Kind.TEXT))
    result = suggest(cols, [PHONE])
    assert result.unmapped == (1,)


def test_a_column_feeds_at_most_one_field() -> None:
    fields = [Field("a", Kind.TEXT, aliases=("nome",)), Field("b", Kind.TEXT, aliases=("nome",))]
    result = suggest(profile(column(0, "Nome")), fields)
    assert [c.column for c in result.choices] == [0, None]


def test_the_key_counts_as_an_alias() -> None:
    field = Field("birth_date", Kind.DATE)
    choice = suggest(profile(column(0, "Birth Date", Kind.DATE)), [field]).choices[0]
    assert choice.confidence is Confidence.HIGH


def test_an_alias_contained_in_the_header_is_medium() -> None:
    choice = suggest(profile(column(0, "Celular principal", Kind.PHONE)), [PHONE]).choices[0]
    assert (choice.column, choice.confidence) == (0, Confidence.MEDIUM)
    assert choice.reasons[0] == Reason(ReasonCode.HEADER_CONTAINS_ALIAS, {"alias": "celular"})


def test_a_header_match_on_an_empty_column_is_medium() -> None:
    choice = suggest(profile(column(0, "Celular", Kind.TEXT, filled=0)), [PHONE]).choices[0]
    assert (choice.column, choice.confidence) == (0, Confidence.MEDIUM)
    assert [r.code for r in choice.reasons] == [ReasonCode.HEADER_MATCHES_ALIAS]


def test_a_contained_alias_on_an_empty_column_is_low() -> None:
    choice = suggest(profile(column(0, "Celular 2", Kind.TEXT, filled=0)), [PHONE]).choices[0]
    assert choice.confidence is Confidence.LOW


def test_content_alone_with_several_candidates_is_low() -> None:
    cols = profile(column(0, "A", Kind.PHONE), column(1, "B", Kind.PHONE))
    choice = suggest(cols, [PHONE]).choices[0]
    assert (choice.column, choice.confidence) == (0, Confidence.LOW)
    assert choice.alternatives == (Alternative(1, Confidence.LOW),)


def test_content_alone_is_not_enough_for_a_general_kind() -> None:
    field = Field("note", Kind.TEXT)
    assert suggest(profile(column(0, "Obs")), [field]).choices[0].column is None


def test_a_profile_without_a_header_uses_content_only() -> None:
    cols = profile(column(0, "Celular", Kind.PHONE), header=False)
    choice = suggest(cols, [PHONE]).choices[0]
    assert choice.confidence is Confidence.MEDIUM
    assert [r.code for r in choice.reasons] == [ReasonCode.CONTENT_FITS_KIND]


def test_a_required_field_takes_the_only_column_its_kind_accepts() -> None:
    field = Field("name", Kind.NAME, required=True, aliases=("nome",))
    result = suggest(profile(column(0, "Quem"), column(1, "Valor", Kind.MONEY)), [field])
    choice = result.choices[0]
    assert (choice.column, choice.confidence) == (0, Confidence.LOW)
    assert [r.code for r in choice.reasons] == [
        ReasonCode.CONTENT_FITS_KIND,
        ReasonCode.ONLY_CANDIDATE,
    ]
    assert result.unmapped == (1,)


def test_a_required_field_with_two_accepted_columns_is_left_unmatched() -> None:
    field = Field("name", Kind.NAME, required=True, aliases=("nome",))
    result = suggest(profile(column(0, "Quem"), column(1, "Onde")), [field])
    assert result.choices[0].column is None
    assert result.choices[0].reasons == (Reason(ReasonCode.REQUIRED_FIELD_UNMATCHED),)


def test_an_optional_field_never_takes_a_column_by_elimination() -> None:
    field = Field("name", Kind.NAME, aliases=("nome",))
    assert suggest(profile(column(0, "Quem")), [field]).choices[0].column is None


def test_no_fields_leaves_every_column_unmapped() -> None:
    result = suggest(profile(column(0, "A"), column(1, "B")), [])
    assert (result.choices, result.unmapped) == ((), (0, 1))


def test_choices_follow_the_declaration_order() -> None:
    fields = [Field("b", Kind.TEXT), Field("a", Kind.TEXT)]
    assert [c.field for c in suggest(profile(column(0, "A")), fields).choices] == ["b", "a"]


def test_a_compatible_kind_fits_with_its_own_share() -> None:
    field = Field("amount", Kind.MONEY, aliases=("valor",))
    choice = suggest(profile(column(0, "Valor", Kind.DECIMAL, 0.9)), [field]).choices[0]
    assert choice.confidence is Confidence.HIGH
    assert choice.reasons[1].data == {"kind": "decimal", "share": 0.9}


def test_the_result_is_deterministic() -> None:
    cols = profile(column(0, "A", Kind.PHONE), column(1, "B", Kind.PHONE))
    assert suggest(cols, [PHONE]) == suggest(cols, [PHONE])


def test_an_empty_header_gives_no_header_signal() -> None:
    field = Field("column 1", Kind.PHONE)
    choice = suggest(profile(column(0, "", Kind.PHONE)), [field]).choices[0]
    assert choice.confidence is Confidence.MEDIUM
    assert [r.code for r in choice.reasons] == [ReasonCode.CONTENT_FITS_KIND]


def test_a_text_field_reads_any_column_kind() -> None:
    field = Field("data", Kind.TEXT, aliases=("data",))
    choice = suggest(profile(column(0, "Data", Kind.DATE, 0.99)), [field]).choices[0]
    assert (choice.column, choice.confidence) == (0, Confidence.HIGH)
    assert ReasonCode.CONTENT_CONFLICTS_WITH_KIND not in [r.code for r in choice.reasons]


def test_a_required_text_field_does_not_take_any_lone_column_as_only_candidate() -> None:
    field = Field("note", Kind.TEXT, required=True)
    choice = suggest(profile(column(0, "Quando", Kind.DATE, 0.99)), [field]).choices[0]
    assert choice.column is None
    assert [r.code for r in choice.reasons] == [ReasonCode.REQUIRED_FIELD_UNMATCHED]


def test_a_header_that_is_a_whole_line_matches_no_alias() -> None:
    header = "Code,Name,Phone,Celular principal,Address,City,State"
    result = suggest(profile(column(0, header)), [PHONE])
    assert result.choices[0].column is None


def test_a_header_with_a_couple_of_delimiters_still_matches() -> None:
    choice = suggest(profile(column(0, "Celular, principal", Kind.PHONE)), [PHONE]).choices[0]
    assert choice.column == 0


def test_a_category_field_reads_a_low_cardinality_text_column_as_a_content_fit() -> None:
    low = dataclasses.replace(column(0, "Status", Kind.TEXT), low_cardinality=True)
    field = Field("status", Kind.CATEGORY, one_of=("active", "inactive"))
    choice = suggest(profile(low), [field]).choices[0]
    assert (choice.column, choice.confidence) == (0, Confidence.HIGH)
    assert [reason.code for reason in choice.reasons] == [
        ReasonCode.HEADER_MATCHES_ALIAS,
        ReasonCode.CONTENT_FITS_KIND,
    ]
