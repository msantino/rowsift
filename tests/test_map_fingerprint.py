"""The header fingerprint, on profiles built from real tables."""

import hashlib

from rowsift import profile as make_profile
from rowsift.map import Field, suggest
from rowsift.profile import Profile
from rowsift.types import Kind
from tests.profile_helpers import phone, table

FIELDS = [Field("name", Kind.NAME, aliases=("nome",)), Field("phone", Kind.PHONE)]


def people(*header: str) -> Profile:
    rows = tuple((f"Ana {n}", phone(n)) for n in range(1, 6))
    return make_profile(table(header, *rows))


def test_same_layout_different_typing() -> None:
    first = suggest(people("Nome", "Celular"), FIELDS)
    second = suggest(people("NOME ", " celular"), FIELDS)
    assert first.fingerprint == second.fingerprint


def test_column_order_matters() -> None:
    rows = tuple((phone(n), f"Ana {n}") for n in range(1, 6))
    swapped = make_profile(table(("Celular", "Nome"), *rows))
    straight = people("Nome", "Celular")
    assert suggest(swapped, FIELDS).fingerprint != suggest(straight, FIELDS).fingerprint


def test_the_fingerprint_is_the_sha256_of_the_normalized_headers() -> None:
    result = suggest(people("Nome", "Dt. Celular"), FIELDS)
    assert result.fingerprint == hashlib.sha256(b"nome\ndt celular").hexdigest()
