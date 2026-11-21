import pytest

from rowsift import read
from rowsift.errors import DecodingError
from rowsift.read._text import decode, detect_delimiter
from rowsift.types import FileFormat, ReadNote
from tests.read_helpers import fixture


def test_utf_8_with_byte_order_mark() -> None:
    table = read(fixture("encoding", "utf8_bom.csv"))
    assert table.rows[0][0] == "Nome"
    assert table.report.encoding == "utf-8"
    assert table.report.notes == (ReadNote.BOM_REMOVED,)


def test_windows_1252_text_with_accents() -> None:
    table = read(fixture("encoding", "cp1252.csv"))
    assert table.rows[1][0] == "João"
    assert table.report.encoding == "cp1252"


def test_utf_16_exported_by_a_spreadsheet_program() -> None:
    table = read(fixture("encoding", "utf16le_tab.txt"))
    assert table.rows == (("Nome", "Telefone"), ("Ana Silva", "11999990001"))
    assert table.report.encoding == "utf-16-le"
    assert table.report.delimiter == "\t"
    assert table.report.notes == (ReadNote.BOM_REMOVED,)


def test_utf_16_without_a_mark_is_found_by_the_nul_pattern() -> None:
    table = read(fixture("encoding", "utf16be_no_mark.txt"))
    assert table.report.encoding == "utf-16-be"
    assert table.rows[0] == ("Nome", "Telefone")


def test_plain_utf_8_needs_no_mark() -> None:
    table = read(fixture("encoding", "utf8_plain.csv"))
    assert table.report.encoding == "utf-8"
    assert table.report.notes == ()


def test_a_byte_cp1252_does_not_define_falls_back_to_latin_1() -> None:
    table = read(fixture("encoding", "latin1_undefined_in_cp1252.csv"))
    assert table.report.encoding == "latin-1"


def test_a_byte_order_mark_the_bytes_do_not_follow_is_a_decoding_error() -> None:
    with pytest.raises(DecodingError):
        decode(b"\xef\xbb\xbf\xff\xfe\xfa")
    with pytest.raises(DecodingError):
        decode(b"\xff\xfeA")


def test_semicolon_file_with_commas_inside_quoted_values() -> None:
    table = read(fixture("delimiter", "semicolon_quoted_commas.csv"))
    assert all(len(row) == 2 for row in table.rows)
    assert table.report.delimiter == ";"
    assert table.rows[0][0] == "Silva, Ana"


def test_single_column() -> None:
    table = read(fixture("delimiter", "single_column.csv"))
    assert all(len(row) == 1 for row in table.rows)
    assert table.report.column_count == 1
    assert table.report.delimiter is None


def test_a_single_column_keeps_a_quoted_value_with_a_line_break() -> None:
    table = read(b'"a\nb"\nc\n')
    assert table.rows == (("a\nb",), ("c",))


def test_a_comma_inside_free_text_does_not_win_over_the_real_delimiter() -> None:
    table = read(fixture("delimiter", "comma_in_free_text_of_semicolon_file.csv"))
    assert table.report.delimiter == ";"


def test_a_tie_between_delimiters_goes_to_the_first_in_the_documented_order() -> None:
    assert detect_delimiter("a,b;c\n1,2;3\n") == ";"


def test_blank_lines_do_not_decide_the_delimiter() -> None:
    assert detect_delimiter("\n\na|b\n\n1|2\n") == "|"


def test_text_with_no_records_has_no_delimiter() -> None:
    assert detect_delimiter("") is None


def test_the_format_of_text_is_csv() -> None:
    assert read(b"a;b\n").report.format is FileFormat.CSV


def test_a_quote_that_is_never_closed_is_reported() -> None:
    table = read(fixture("delimiter", "unterminated_quote.csv"))
    assert table.rows[1] == ("abc\nrow2\nrow3\n",)
    assert table.report.notes == (ReadNote.UNTERMINATED_QUOTE,)


def test_a_stray_quote_earlier_does_not_hide_a_quote_that_is_never_closed() -> None:
    table = read(b'a,b\n"x"y,2\n"open,3\n1,2\n')
    assert table.report.notes == (ReadNote.UNTERMINATED_QUOTE,)
    assert table.rows[2] == ("open,3\n1,2\n", "")


def test_doubled_quotes_and_a_final_closed_field_carry_no_note() -> None:
    assert read(b'a,b\n"say ""hi""",2\n"x"y,3\n').report.notes == ()
    assert read(b'a,b\n1,"two"').report.notes == ()


def test_balanced_and_mid_field_quotes_carry_no_note() -> None:
    assert read(b'a,b\n"x, y",5" screen\n').report.notes == ()
    assert read(b'a,b\n"x","y"\n').report.notes == ()


def test_every_line_wrapped_in_one_quoted_field_is_unwrapped_cp1252() -> None:
    table = read(fixture("wrapped", "wrapped_cp1252.csv"))
    assert table.report.column_count == 4
    assert table.report.delimiter == ","
    assert table.report.encoding == "cp1252"
    assert table.report.notes == (ReadNote.WRAPPED_LINES_UNWRAPPED,)
    assert table.rows[0] == ("Code", "Name", "Phone", "Address, with comma")
    assert table.rows[1][1] == "JOSÉ ALVES"
    assert table.rows[1][3] == "R DAS FLORES, 120"


def test_every_line_wrapped_in_one_quoted_field_is_unwrapped_ascii_with_lost_letters() -> None:
    table = read(fixture("wrapped", "wrapped_ascii_question_marks.csv"))
    assert table.report.column_count == 4
    assert table.report.notes == (ReadNote.WRAPPED_LINES_UNWRAPPED,)
    assert table.rows[1][1] == "JOS? ALVES"


def test_a_file_that_really_has_one_quoted_column_stays_one_column() -> None:
    table = read(fixture("wrapped", "single_column_quoted.csv"))
    assert table.report.column_count == 1
    assert table.report.delimiter is None
    assert table.report.notes == ()


def test_wrapped_lines_with_different_column_counts_are_not_unwrapped() -> None:
    table = read(b'"a,b,c"\n"1,2"\n"3,4,5"\n')
    assert table.report.column_count == 1
    assert table.report.notes == ()


def test_wrapping_is_not_undone_when_a_line_is_not_wrapped() -> None:
    table = read(b'"a,b,c"\n1,2,3\n')
    assert ReadNote.WRAPPED_LINES_UNWRAPPED not in table.report.notes


def test_a_wrapped_file_with_a_byte_order_mark_reports_both_notes() -> None:
    data = b'\xef\xbb\xbf"a;b"\r\n"1;2"\r\n'
    table = read(data)
    assert table.rows == (("a", "b"), ("1", "2"))
    assert table.report.delimiter == ";"
    assert table.report.notes == (ReadNote.BOM_REMOVED, ReadNote.WRAPPED_LINES_UNWRAPPED)


def test_a_single_column_where_every_value_holds_a_delimiter_is_unwrapped_with_the_note() -> None:
    table = read(b'"Silva, Ana"\n"Souza, Bruno"\n')
    assert table.report.column_count == 2
    assert table.report.notes == (ReadNote.WRAPPED_LINES_UNWRAPPED,)
