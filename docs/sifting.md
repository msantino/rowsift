# Sifting

`rowsift.sift` applies a mapping to a table. It cleans every data row with the kind of each field, keeps the rows whose required fields are good, lists the others as rejections, and counts every outcome. It has no side effect, so it serves as a preview and again as the final pass.

## Behavior

```python
import rowsift

table = rowsift.read(
    "Nome;Email;Obs\nana souza;ana@example.com;a\n;bia@example.com;b\nCarla;not-an-email;c\n".encode(
        "utf-8"
    )
)
profile = rowsift.profile(table)
fields = [
    rowsift.Field("name", rowsift.Kind.NAME, required=True, aliases=("Nome",)),
    rowsift.Field("email", rowsift.Kind.EMAIL, required=True),
]
mapping = rowsift.suggest(profile, fields)

result = rowsift.sift(table, profile, mapping, fields)

# One row is kept, two are rejected, and each rejection says which field and why.
assert result.summary.data_rows == 3
assert result.summary.kept == 1
assert result.summary.rejected == 2
assert [(item.number, item.field, item.issue.code) for item in result.rejected] == [
    (3, "name", "required_missing"),
    (4, "email", "invalid_email"),
]

kept = result.rows[0]
assert kept.number == 2
assert kept.values == {"name": "Ana Souza", "email": "ana@example.com"}
assert [change.code for change in kept.changes["name"]] == ["case_changed"]
assert kept.extras == {"obs": "a"}
```

- **`rows`** are the kept rows, each a `rowsift.SiftedRow`: `number` (the 1-based position in the file, counting rows above the header), `values` (the cleaned value of every declared field, `None` for an empty cell, a field with no column, or an optional value that failed), `extras` (the text of the columns no field uses, by normalized header), `changes` (what the cleaners altered, by field) and `issues` (why an optional field became `None`, by field).
- **`rejected`** are `rowsift.Rejection` entries: `number`, `field` and `issue`. A row with several failing required fields has one rejection per field.
- **`summary`** is a `rowsift.Summary` with `data_rows`, `kept`, `rejected` and, per field, a `rowsift.FieldSummary`: how many cells were `filled`, and a count of every change code and issue code.
- **A row is rejected only when a required field is empty or fails.** An optional field that is empty or fails leaves `None` in the row and the issue on the row.
- **Rows the profile skipped** (above the header, empty, repeated headers, totals) are not data and are not counted.

## Arguments

```python
import rowsift

table = rowsift.read("Nome;Obs\nAna;a\n".encode("utf-8"))
profile = rowsift.profile(table)
fields = [rowsift.Field("name", rowsift.Kind.NAME, aliases=("Nome",))]
mapping = rowsift.suggest(profile, fields)

result = rowsift.sift(
    table,
    profile,
    mapping,
    fields,
    options=rowsift.CleanOptions(name_case="keep"),
    include_extras=False,
)
assert result.rows[0].values["name"] == "Ana"
assert result.rows[0].extras == {}
```

- `options` are the cleaning options of the call. The `options` of a `Field` replace them for that field, and the `one_of` of a field replaces the one in both.
- `include_extras=False` leaves the unmapped columns out of each row.

## Raises

`sift` raises `ValueError` when the arguments disagree: two fields share a key, a field has no choice in the mapping, the mapping has a choice for a key that is not a declared field, a required field has no column, or the profile does not match the table. These are programming errors, not data errors, so they are not `RowsiftError`.

## Limits

`sift` works on a table already read under the limits of [reading](reading.md). It builds the rows in memory.
