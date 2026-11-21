# Reading

`rowsift.read` turns the bytes of a file into a grid of text cells and a report of how it was read. It is the only step that touches the format of the file. It takes bytes, never a path, and writes nothing.

## Behavior

```python
import rowsift

table = rowsift.read("Nome;Cidade\nAna;Recife\nBruno;Natal\n".encode("utf-8"))

assert table.rows[0] == ("Nome", "Cidade")
assert table.report.format == "csv"
assert table.report.delimiter == ";"
assert table.report.row_count == 3
assert table.report.column_count == 2
```

- **The format comes from the content, never from the file name.** XLSX is a ZIP archive that holds a workbook, XLS is a compound file, and anything else that looks like text is delimited text. The `filename` argument is accepted for convenience and never changes the result.
- **Every cell is text.** An empty cell is `""`. Formulas give the value the file stored and are never evaluated. Macros are never run.
- **Rows are rectangular.** Short rows are padded, and trailing columns that are empty in every row are dropped (`trailing_empty_columns_dropped`).
- **Delimited text.** The encoding is decided in this order: a byte order mark (UTF-8, UTF-16 LE, UTF-16 BE), UTF-16 without a mark when the NUL bytes say so, strict UTF-8, then Windows-1252, then Latin-1. The delimiter is one of `;`, tab, `|` and `,`, chosen by how well each splits the first records, with quoted fields respected. A byte order mark is removed and reported (`bom_removed`).
- **Workbooks.** XLSX and XLS need the `excel` extra. The first sheet that holds data is read, or the sheet you name by name or by zero-based index with `sheet=`. Merged cells are filled with the value of the top-left cell (`merged_cells_filled`). A delimited file has no sheets, so asking for one raises `sheet_not_found`.

`table.report` is a `rowsift.ReadReport`: `format`, `encoding`, `delimiter`, `sheet`, `sheets`, `row_count`, `column_count` and `notes`. `encoding` and `delimiter` are `None` for workbooks, and `sheet` is `None` for delimited text.

## Limits

A file from a person is untrusted input. The limits are checked before the work they bound, and going past one stops the read with `rowsift.LimitExceededError`.

| Limit | Default | What it bounds |
|---|---|---|
| `max_bytes` | 10 MB | the size of the input |
| `max_rows` | 50,000 | rows of the table, empty rows included |
| `max_columns` | 200 | columns that hold data |
| `max_decompressed_bytes` | 100 MB | the sum of the uncompressed sizes a workbook archive declares |
| `max_cell_chars` | 10,000 | characters in one cell |

A megabyte is 1,048,576 bytes. Change them with `rowsift.ReadLimits`, passing every limit by keyword:

```python
import rowsift

limits = rowsift.ReadLimits(max_rows=2)
try:
    rowsift.read(b"a\nb\nc\n", limits=limits)
except rowsift.LimitExceededError as error:
    assert error.limit == "max_rows"
    assert error.allowed == 2
    assert error.code == "limit_exceeded"
else:
    raise AssertionError("the limit was not enforced")
```

## Errors

Every exception derives from `rowsift.RowsiftError` and carries a `code`. A message is built from codes and constant names only, never from cell contents, so it is safe to log.

| Exception | Code | When |
|---|---|---|
| `rowsift.UnsupportedFileError` | `unsupported_file` | the bytes are no supported format, such as a ZIP archive that is no workbook or binary data |
| `rowsift.UnsupportedFileError` | `password_protected` | the workbook is encrypted with a password. The library does not open it, and the application can ask for a copy without the password |
| `rowsift.UnsupportedFileError` | `sheet_not_found` | the requested sheet does not exist, or any sheet was requested of delimited text |
| `rowsift.LimitExceededError` | `limit_exceeded` | a limit above was exceeded. `limit` names it and `allowed` holds its value |
| `rowsift.MissingExtraError` | `missing_extra` | a workbook was read without the `excel` extra. `extra` names what to install |
| `rowsift.DecodingError` | `decoding_failed` | a byte order mark promises an encoding the bytes do not follow, or the text cannot be split into records |

```python
import rowsift

try:
    rowsift.read(b"a\nb\n", sheet="Sheet1")
except rowsift.RowsiftError as error:
    assert error.code == "sheet_not_found"
else:
    raise AssertionError("a delimited file has no sheets")
```
