"""Column statistics, the low-cardinality signal and samples."""

import pytest

from rowsift.profile import ColumnProfile, ProfileOptions, TopValue, profile
from rowsift.types import Kind
from tests.profile_helpers import phone, table


def one_column(values: list[str], options: ProfileOptions | None = None) -> ColumnProfile:
    rows = [("Value",), *[(v,) for v in values]]
    return profile(table(*rows), options).columns[0]


def test_sparse_column() -> None:
    values = [f"item {i}" for i in range(30)] + [""] * 170
    column = one_column(values)
    assert column.filled == 30
    assert column.distinct == 30


def test_distinct_counts_values_not_cells() -> None:
    column = one_column(["a", "b", "a", "", "a"])
    assert (column.filled, column.distinct) == (4, 2)


def test_shift_column() -> None:
    values = ["Morning"] * 212 + ["Afternoon"] * 190 + ["Night"] * 96
    column = one_column(values)
    assert column.low_cardinality is True
    assert column.top_values == (
        TopValue("Morning", 212),
        TopValue("Afternoon", 190),
        TopValue("Night", 96),
    )


def test_unique_identifiers_are_not_low_cardinality() -> None:
    column = one_column([f"id-{i}" for i in range(100)])
    assert column.low_cardinality is False
    assert column.top_values == ()


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        (["a", "b"] * 9 + ["a"], False),  # 19 filled: under the minimum of 20
        (["a", "b"] * 10, False),  # 20 filled, 2 distinct = 10% over the 5% limit
        ([f"v{i % 13}" for i in range(400)], False),  # 13 distinct: over the maximum of 12
        ([f"v{i % 12}" for i in range(400)], True),  # 12 distinct, 3%
        ([f"v{i % 12}" for i in range(240)], True),  # 12 distinct, exactly 5%
        ([f"v{i % 12}" for i in range(239)], False),  # 12 distinct, just above 5%
    ],
)
def test_low_cardinality_thresholds(values: list[str], expected: bool) -> None:
    assert one_column(values).low_cardinality is expected


def test_low_cardinality_thresholds_are_options() -> None:
    values = ["a", "b"] * 10
    options = ProfileOptions(low_cardinality_max_share=0.1)
    assert one_column(values, options).low_cardinality is True
    options = ProfileOptions(low_cardinality_min_filled=21, low_cardinality_max_share=0.5)
    assert one_column(values, options).low_cardinality is False
    options = ProfileOptions(low_cardinality_max_distinct=1, low_cardinality_max_share=0.5)
    assert one_column(values, options).low_cardinality is False


def test_top_values_with_equal_counts_are_ordered_by_value() -> None:
    column = one_column(["b"] * 50 + ["a"] * 50 + ["c"] * 100)
    assert [t.value for t in column.top_values] == ["c", "a", "b"]


def test_phone_sample() -> None:
    column = one_column(["(11) 99999-0042"])
    assert column.kind is Kind.PHONE
    assert column.samples == ("11 *******42",)


def test_samples_are_distinct_first_seen_and_limited() -> None:
    column = one_column(["x", "y", "x", "z", "w", "v"])
    assert column.samples == ("x", "y", "z")
    assert one_column(["x", "y"], ProfileOptions(sample_count=1)).samples == ("x",)
    assert one_column(["x", "y"], ProfileOptions(sample_count=0)).samples == ()


def test_samples_come_from_the_data_rows_only() -> None:
    result = profile(table(("Name", "Phone"), ("Ana", phone(1)), ("Name", "Phone")))
    assert result.columns[0].samples == ("Ana",)


def test_masking_can_be_turned_off() -> None:
    options = ProfileOptions(mask_samples=False)
    assert one_column(["(11) 99999-0042"], options).samples == ("(11) 99999-0042",)


def test_top_values_are_masked_like_samples() -> None:
    values = ["ana@example.com"] * 20 + ["bia@example.com"] * 10
    column = one_column(values, ProfileOptions(low_cardinality_max_share=0.5))
    assert column.top_values == (TopValue("a***@example.com", 20), TopValue("b***@example.com", 10))
    plain = one_column(values, ProfileOptions(low_cardinality_max_share=0.5, mask_samples=False))
    assert plain.top_values[0].value == "ana@example.com"


def test_a_column_that_does_not_look_like_its_kind_hides_its_samples() -> None:
    values = [f"(11) 99999-{i:04d}" for i in range(9)] + ["call after 5"]
    column = one_column(values)
    assert column.kind is Kind.PHONE
    assert "call after 5" not in column.samples
    assert "call after *" not in column.samples


def test_the_profile_is_deterministic_and_immutable() -> None:
    t = table(("Name", "Phone"), ("Ana", phone(1)), ("Bia", phone(2)))
    assert profile(t) == profile(t)
    with pytest.raises(AttributeError):
        profile(t).data_rows = 3  # type: ignore[misc]  # frozen dataclass: the point of the test


@pytest.mark.parametrize(
    "bad",
    [
        {"header_scan_rows": 0},
        {"sample_rows": 0},
        {"kind_threshold": 0},
        {"kind_threshold": 1.5},
        {"kind_threshold": True},
        {"low_cardinality_max_share": -0.1},
        {"low_cardinality_max_distinct": -1},
        {"sample_count": -1},
        {"mask_samples": 1},
        {"clean": "BR"},
    ],
)
def test_options_are_validated(bad: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="must"):
        ProfileOptions(**bad)  # type: ignore[arg-type]  # invalid values are the point of the test


def test_documented_defaults() -> None:
    options = ProfileOptions()
    assert (options.header_scan_rows, options.kind_threshold, options.sample_rows) == (
        20,
        0.8,
        5000,
    )
    assert (
        options.low_cardinality_min_filled,
        options.low_cardinality_max_distinct,
        options.low_cardinality_max_share,
        options.sample_count,
        options.mask_samples,
    ) == (20, 12, 0.05, 3, True)


def test_a_phone_column_below_the_threshold_still_masks_its_phones() -> None:
    values = [phone(i) for i in range(7)] + ["no phone"] * 3
    column = one_column(values)
    assert column.kind is Kind.TEXT
    assert column.runner_up is not None
    assert column.runner_up.kind is Kind.PHONE
    assert column.samples == ("11 *******00", "11 *******01", "11 *******02")


def test_a_text_column_masks_each_value_by_the_personal_kind_it_fits() -> None:
    values = ["ana@example.com", "see notes", "529.982.247-25", "see notes"]
    column = one_column(values)
    assert column.kind is Kind.TEXT
    assert column.samples == ("a***@example.com", "see notes", "***.***.***-25")


def test_a_text_column_of_plain_words_is_returned_as_written() -> None:
    assert one_column(["Morning", "Night"]).samples == ("Morning", "Night")


def test_text_top_values_are_masked_per_value() -> None:
    values = ["ana@example.com"] * 15 + ["n/a"] * 10
    column = one_column(values, ProfileOptions(low_cardinality_max_share=0.5))
    assert column.top_values == (TopValue("a***@example.com", 15), TopValue("n/a", 10))


def test_a_value_that_does_not_fit_the_masked_kind_is_a_fixed_placeholder() -> None:
    column = one_column(["no phone", *[phone(i) for i in range(9)]])
    assert column.kind is Kind.PHONE
    assert column.samples[0] == "***"


def test_personal_data_inside_free_text_is_hidden() -> None:
    column = one_column(["ligar 11 99999-0042", "ana@example.com ok", "plain note"])
    assert column.kind is Kind.TEXT
    assert column.samples == ("***", "plain note")


def test_a_phone_in_a_date_column_is_masked() -> None:
    column = one_column(["12/03/1990"] * 8 + ["(11) 99999-0042"] * 2)
    assert column.kind is Kind.DATE
    assert column.samples == ("12/03/1990", "11 *******42")


def test_a_value_that_is_not_a_date_is_hidden_in_a_date_column() -> None:
    column = one_column(["Ana Souza", "Bia"] + ["12/03/1990"] * 8)
    assert column.kind is Kind.DATE
    assert column.samples == ("***", "12/03/1990")


def test_personal_values_in_an_integer_column_do_not_show() -> None:
    values = ["ana@example.com", "11999990042", "x y"] + [str(n) for n in range(10, 40)]
    column = one_column(values)
    assert column.kind is Kind.INTEGER
    assert column.samples[0] == "a***@example.com"
    assert column.samples[1] == "11 *******42"
    assert column.samples[2] == "***"


def test_plain_values_of_a_non_personal_kind_stay_as_written() -> None:
    assert one_column(["12/03/1990", "05/11/1991"]).samples == ("12/03/1990", "05/11/1991")
    assert one_column(["10", "20", "30"]).samples == ("10", "20", "30")


def test_samples_are_distinct_after_masking() -> None:
    column = one_column([phone(1042), phone(2042), phone(3042), phone(4043)])
    assert column.samples == ("11 *******42", "11 *******43")


def test_misfits_of_a_phone_column_give_one_placeholder() -> None:
    column = one_column(["a", "b", "c", *[phone(i) for i in range(40)]])
    assert column.kind is Kind.PHONE
    assert column.samples[0] == "***"
    assert column.samples.count("***") == 1


def test_top_values_that_mask_alike_are_merged_with_their_counts() -> None:
    values = [phone(1042)] * 30 + [phone(2042)] * 30 + [phone(3043)] * 10
    column = one_column(values, options=ProfileOptions(low_cardinality_max_share=0.5))
    assert column.top_values == (TopValue("11 *******42", 60), TopValue("11 *******43", 10))
