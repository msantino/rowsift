"""The public surface of the profile layer, and the layer composed with the reader."""

import rowsift
from rowsift import ProfileOptions, read
from rowsift.profile import profile
from rowsift.types import Kind, SkipCode


def test_the_function_is_exported_at_the_top_level() -> None:
    assert rowsift.profile is profile
    assert {"Profile", "ProfileOptions", "ColumnProfile", "profile"} <= set(rowsift.__all__)


def test_a_file_read_from_bytes_is_profiled() -> None:
    data = (
        b"Customer list;;\n"
        b";;\n"
        b"Name;Phone;Birthday\n"
        b"Ana Lima;(11) 99999-0001;12/03\n"
        b"Bia Souza;(11) 99999-0002;05/11\n"
        b"Caio Dias;(11) 99999-0003;29/02\n"
    )
    result = profile(read(data), ProfileOptions())
    assert result.header_row == 2
    assert [c.kind for c in result.columns] == [Kind.TEXT, Kind.PHONE, Kind.DAY_MONTH]
    assert [s.code for s in result.skipped_rows] == [SkipCode.BEFORE_HEADER, SkipCode.EMPTY]
