"""The public surface of the mapping layer, composed with the earlier layers."""

import rowsift
from rowsift import Field, Kind, apply_saved, read, suggest
from rowsift.map import SavedMapping
from rowsift.types import Confidence, ReasonCode

DATA = (
    b"Customer list;;;\n"
    b";;;\n"
    b"Cliente;Celular;Niver;Shift\n"
    b"Ana Lima;(11) 99999-0001;12/03;morning\n"
    b"Bia Souza;(11) 99999-0002;05/11;night\n"
    b"Caio Dias;(11) 99999-0003;29/02;morning\n"
    b"Duda Reis;(11) 99999-0004;01/01;night\n"
)

FIELDS = [
    Field("name", Kind.NAME, required=True, aliases=("nome", "cliente")),
    Field("phone", Kind.PHONE, aliases=("celular", "telefone")),
    Field("birthday", Kind.DAY_MONTH, aliases=("aniversario", "nascimento")),
]


def test_the_names_are_exported_at_the_top_level() -> None:
    assert rowsift.suggest is suggest
    assert rowsift.apply_saved is apply_saved
    assert {"Field", "Mapping", "Choice", "SavedMapping", "Kind", "Confidence"} <= set(
        rowsift.__all__
    )


def test_a_file_read_from_bytes_is_mapped() -> None:
    result = suggest(rowsift.profile(read(DATA)), FIELDS)
    by_field = {c.field: c for c in result.choices}
    assert [by_field[k].column for k in ("name", "phone", "birthday")] == [0, 1, 2]
    assert by_field["name"].confidence is Confidence.HIGH
    assert by_field["phone"].confidence is Confidence.HIGH
    assert by_field["birthday"].confidence is Confidence.MEDIUM
    assert by_field["birthday"].reasons[0].code is ReasonCode.CONTENT_FITS_KIND
    assert result.unmapped == (3,)


def test_a_saved_mapping_is_applied_to_the_next_file() -> None:
    profile = rowsift.profile(read(DATA))
    saved = SavedMapping.from_mapping(suggest(profile, FIELDS).assign("birthday", 3), profile)
    again = apply_saved(rowsift.profile(read(DATA)), FIELDS, saved)
    assert [c.column for c in again.choices] == [0, 1, 3]
    assert again.unmapped == (2,)
