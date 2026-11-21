# Profiling

`rowsift.profile` looks at a table and says where the header is, which rows are data and what each column holds. It does not change the table.

## Behavior

```python
import rowsift

rows = (
    "Relatório de clientes;;\n"
    ";;\n"
    "Nome;Nascimento;Cidade\n"
    "Ana Souza;03/04/1990;Recife\n"
    "Bruno Lima;15/08/1985;Natal\n"
    "Total;;2\n"
)
table = rowsift.read(rows.encode("utf-8"))
profile = rowsift.profile(table)

assert profile.header_row == 2
assert profile.data_start == 3
assert profile.data_rows == 2
assert [(skipped.index, skipped.code) for skipped in profile.skipped_rows] == [
    (0, "before_header"),
    (1, "empty"),
    (5, "total_row"),
]
assert [column.kind for column in profile.columns] == ["text", "date", "text"]
```

- **The header** is searched among the first non-empty rows (`header_scan_rows`, 20 by default). "There is no header" is a valid answer: `header_row` is then `None` and the columns are named by position.
- **Rows that are not data** are listed in `skipped_rows` with a code: `empty`, `before_header` (a title above the header), `repeated_header` (a header repeated in the middle, as in a pasted report) and `total_row` (a closing row of totals, such as `Total`, or a total word with a count after a colon or hyphen, as in `Total: 25`; `Total 2024` is data. Only the ASCII colon and hyphen separate, so `Total - 2024` is a total row while an en dash or a negative count, as in `Total: -5`, is data). Skipped rows are not counted in `data_rows`.
- **Each column** is a `rowsift.ColumnProfile` with its `kind`, the `kind_share` (the share of non-empty sampled values that fit it), the `runner_up` kind, how many cells are `filled` and `distinct`, whether it is `low_cardinality`, its `top_values` and a few masked `samples`.
- **The kind** is the most specific one that at least `kind_threshold` (0.8) of the non-empty sampled values fit, and `text` otherwise. The kinds are listed in [codes.md](codes.md#kind). The inference uses the first `sample_rows` (5,000) data rows, and the counts cover every data row.
- **Low cardinality** marks a column of a small set of repeated values, such as a status or a plan. A column needs at least 20 filled cells, at most 12 distinct values and at most 5% of distinct values over filled cells.
- **`normalized_header`** is the header folded for matching: case, accents and punctuation ignored, and unique among the columns. `normalize_header`, in the `rowsift.profile` module, exposes the same folding.

## Samples are masked

A profile is meant to be shown to the person who sent the file, so its samples and top values are masked by the kind of the column and by the personal kind each value fits: a phone keeps its area code and last two digits, a CPF its last two digits, an e-mail its first character and its domain, a name its first name and initials.

```python
import rowsift

table = rowsift.read("Celular\n(11) 91234-5678\n(11) 98765-4321\n".encode("utf-8"))
profile = rowsift.profile(table)
assert profile.columns[0].kind == "phone"
assert profile.columns[0].samples == ("11 *******78", "11 *******21")
```

Masking can be turned off with `mask_samples=False`, only for values that are safe to display.

## Options

`rowsift.ProfileOptions` holds every knob, passed by keyword:

| Option | Default | Meaning |
|---|---|---|
| `header_scan_rows` | 20 | non-empty rows examined as header candidates |
| `kind_threshold` | 0.8 | share of sampled values a kind must fit |
| `sample_rows` | 5000 | data rows read to infer the kind |
| `low_cardinality_min_filled` | 20 | filled cells a low-cardinality column needs |
| `low_cardinality_max_distinct` | 12 | distinct values it may have |
| `low_cardinality_max_share` | 0.05 | distinct values over filled cells |
| `sample_count` | 3 | distinct samples kept per column |
| `mask_samples` | `True` | mask samples and top values |
| `clean` | `CleanOptions()` | the cleaning options used while inferring kinds, such as the order of day and month |

```python
import rowsift

options = rowsift.ProfileOptions(clean=rowsift.CleanOptions(date_order="mdy"))
table = rowsift.read("Date\n04/03/1990\n12/25/1990\n".encode("utf-8"))
profile = rowsift.profile(table, options)
assert profile.columns[0].kind == "date"
assert profile.columns[0].kind_share == 1.0
```

## Limits

The kind of a column is an inference from its values, not a fact. A column of eight-digit numbers can be a postal code or an integer, and the `runner_up` says what came second. Use the profile to suggest and to ask the person, not to decide in silence.
