"""Header detection and skipped rows."""

import pytest

from rowsift.profile import ProfileOptions, profile
from rowsift.types import SkipCode
from tests.profile_helpers import phone, table


def people(count: int, start: int = 0) -> list[tuple[str, ...]]:
    return [
        (f"Person {start + i}", phone(start + i), f"{1 + i % 28:02d}/03/1990") for i in range(count)
    ]


def test_title_and_blank_line_above_the_header() -> None:
    result = profile(
        table(
            ("Customer list",),
            (),
            ("Name", "Phone", "Birthday"),
            *people(5),
        )
    )
    assert result.header_row == 2
    assert result.data_start == 3
    assert result.data_rows == 5
    assert [(s.index, s.code) for s in result.skipped_rows] == [
        (0, SkipCode.BEFORE_HEADER),
        (1, SkipCode.EMPTY),
    ]


def test_file_with_no_header() -> None:
    result = profile(table(*[(f"Person {i}", phone(i)) for i in range(6)]))
    assert result.header_row is None
    assert result.data_start == 0
    assert result.data_rows == 6
    assert [c.normalized_header for c in result.columns] == ["column_1", "column_2"]
    assert [c.header for c in result.columns] == ["", ""]


def test_header_repeated_at_a_page_break() -> None:
    header = ("Name", "Phone", "Birthday")
    rows = [header, *people(38), header, *people(5, 38)]
    result = profile(table(*rows))
    assert result.header_row == 0
    assert [(s.index, s.code) for s in result.skipped_rows] == [(39, SkipCode.REPEATED_HEADER)]
    assert result.data_rows == 43


def test_the_repeated_header_is_compared_after_normalization() -> None:
    rows = [("Name", "Phone"), ("Ana", phone(1)), ("NAME ", "phone."), ("Bia", phone(2))]
    result = profile(table(*rows))
    assert [(s.index, s.code) for s in result.skipped_rows] == [(2, SkipCode.REPEATED_HEADER)]


def test_empty_rows_inside_the_data_are_skipped() -> None:
    rows = [("Name", "Phone"), ("Ana", phone(1)), ("", " "), ("Bia", phone(2))]
    result = profile(table(*rows))
    assert [(s.index, s.code) for s in result.skipped_rows] == [(2, SkipCode.EMPTY)]
    assert result.data_rows == 2


def test_trailing_total_rows() -> None:
    rows = [
        ("Item", "Amount"),
        ("Pen", "R$ 1,50"),
        ("Ink", "R$ 2,50"),
        ("", ""),
        ("Total", "R$ 4,00"),
        ("", ""),
    ]
    result = profile(table(*rows))
    assert [(s.index, s.code) for s in result.skipped_rows] == [
        (3, SkipCode.EMPTY),
        (4, SkipCode.TOTAL_ROW),
        (5, SkipCode.EMPTY),
    ]
    assert result.data_rows == 2


@pytest.mark.parametrize(
    "label", ["Total: 25", "TOTAL: 1.234,50", "Subtotal - 3", "Total geral: 12"]
)
def test_a_total_word_followed_by_a_count_in_one_cell_is_a_total_row(label: str) -> None:
    rows = [("Item", "Amount"), ("Pen", "1"), ("Ink", "2"), ("", ""), (label, "")]
    result = profile(table(*rows))
    assert [(s.index, s.code) for s in result.skipped_rows] == [
        (3, SkipCode.EMPTY),
        (4, SkipCode.TOTAL_ROW),
    ]
    assert result.data_rows == 2


def test_a_total_word_hyphen_and_a_year_is_a_total_row() -> None:
    rows = [("Item", "Amount"), ("Pen", "1"), ("Ink", "2"), ("Total - 2024", "")]
    result = profile(table(*rows))
    assert [(s.index, s.code) for s in result.skipped_rows] == [(3, SkipCode.TOTAL_ROW)]


@pytest.mark.parametrize(
    "label",
    [
        "Total de vendas: 25",
        "Totally 25",
        "Total: 25 itens",
        "Total 2024",
        "Sum 3",
        "Total \u2013 3",
        "Total: -5",
    ],
)
def test_a_total_word_followed_by_other_text_is_data(label: str) -> None:
    rows = [("Item", "Amount"), ("Pen", "1"), (label, "")]
    result = profile(table(*rows))
    assert result.skipped_rows == ()
    assert result.data_rows == 2


def test_a_total_word_in_the_middle_of_the_data_is_data() -> None:
    rows = [("Item", "Amount"), ("Total", "R$ 1,00"), ("Ink", "R$ 2,50")]
    result = profile(table(*rows))
    assert result.data_rows == 2
    assert result.skipped_rows == ()


def test_the_header_is_looked_for_in_the_first_non_empty_rows_only() -> None:
    rows = [("Note",)] * 25 + [("Name", "Phone")] + [("Ana", phone(1))] * 3
    result = profile(table(*rows))
    assert result.header_row != 25


def test_a_header_with_one_numeric_cell_is_still_a_header() -> None:
    rows = [("Name", "Phone", "Region", "Group", "2024")] + [
        (f"P{i}", phone(i), "North", "A", f"{i}") for i in range(5)
    ]
    assert profile(table(*rows)).header_row == 0


def test_text_only_table_takes_its_first_row_as_header() -> None:
    rows = [("Name", "City"), ("Ana", "Recife"), ("Bia", "Natal")]
    result = profile(table(*rows))
    assert result.header_row == 0
    assert result.data_rows == 2


def test_header_only_table() -> None:
    result = profile(table(("Name", "Phone")))
    assert result.header_row == 0
    assert result.data_rows == 0
    assert [c.kind for c in result.columns] == ["text", "text"]
    assert [c.kind_share for c in result.columns] == [0.0, 0.0]


def test_a_table_with_no_rows() -> None:
    result = profile(table())
    assert (result.header_row, result.data_start, result.data_rows) == (None, 0, 0)
    assert result.columns == ()


def test_a_table_of_empty_rows() -> None:
    result = profile(table(("", ""), ("", "")))
    assert result.header_row is None
    assert [s.code for s in result.skipped_rows] == [SkipCode.EMPTY, SkipCode.EMPTY]
    assert result.data_rows == 0


def test_a_one_cell_title_above_a_two_column_header_is_not_the_header() -> None:
    result = profile(table(("Title", ""), ("Name", "Qty"), ("a", "1"), ("b", "2")))
    assert result.header_row == 1
    assert result.data_start == 2


def test_a_title_is_not_the_header_even_when_the_scan_window_is_one_row() -> None:
    rows = [("Title",), ("Name", "Qty", "Note"), ("a", "1", "x"), ("b", "2", "y")]
    result = profile(table(*rows), ProfileOptions(header_scan_rows=1))
    assert result.header_row != 0


def test_a_header_of_years_above_numbers_is_a_header() -> None:
    rows = [("Name", "2023", "2024"), ("Ana", "10", "20"), ("Bia", "30", "40")]
    result = profile(table(*rows))
    assert result.header_row == 0
    assert result.data_rows == 2
    assert result.columns[1].normalized_header == "2023"


def test_numbers_in_a_first_row_with_no_header_are_not_labels() -> None:
    rows = [("Ana", "2023", "5"), ("Bia", "2024", "6"), ("Cris", "2025", "7")]
    result = profile(table(*rows))
    assert result.header_row is None
    assert result.data_rows == 3


def test_a_total_followed_by_a_footer_is_not_detected() -> None:
    rows = [
        ("Item", "Amount"),
        ("Pen", "1"),
        ("Ink", "2"),
        ("Total", "3"),
        ("Generated on 01/01/2026", ""),
    ]
    result = profile(table(*rows))
    assert result.skipped_rows == ()
    assert result.data_rows == 4
