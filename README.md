# rowsift

rowsift reads spreadsheets written by people and turns them into typed, clean rows mapped to the fields your application declares.

A file exported by a person is rarely a clean table. The header sits on the fourth row under a title and a blank line. The encoding is whatever the spreadsheet program chose. Phone numbers come in five formats, dates have no year, and the column you need is called `Cel 2`. rowsift handles that part of an import, on the server, and reports every decision it made so the application can show it to the person who sent the file.

## What it does

The work is split into four steps. Each one can be used on its own.

| Step | Input | Output |
|---|---|---|
| **Read** | bytes of a CSV, XLSX or XLS file | a grid of text cells, plus how it was read: format, encoding, delimiter, sheet |
| **Profile** | the grid | where the header is, which rows are data, and what each column holds: text, number, money, date, day and month, phone, e-mail, tax id, postal code, or a small set of repeated values |
| **Clean** | one value and the kind it should be | the normalized value, or the reason it could not be normalized |
| **Map** | the profile and the fields you declare | a suggested column for each field, with a confidence level and the reason for it |

Applying a mapping to a file gives typed rows, the rows that were rejected with the reason for each, and counts of what was changed.

## What it does not do

- It does not store anything. Models, jobs, uploads and screens belong to the application.
- It does not guess silently. A phone number cut short by an export is reported as cut short, never completed.
- It does not write user-facing text. Reasons are returned as codes with their data, so the application writes the message in its own language and tone.
- It does not depend on a web framework.

## Formats and conventions

Brazilian conventions are supported from the first version, because that is where the library started: day-first dates, decimal comma, CPF and CNPJ check digits, CEP, and mobile numbers written with or without the ninth digit. Region-specific behavior is selected through options, and the defaults are documented with each function.

## Example

```python
import rowsift

data = (
    "Cadastro de clientes\n"
    "\n"
    "Nome;Celular;Nascimento\n"
    "ana souza;(11) 91234-5678;03/04/1990\n"
    "bruno lima;(11) 9123;15/08/1985\n"
).encode("utf-8")

table = rowsift.read(data)
profile = rowsift.profile(table)

fields = [
    rowsift.Field("name", rowsift.Kind.NAME, required=True, aliases=("Nome",)),
    rowsift.Field("phone", rowsift.Kind.PHONE, aliases=("Celular",)),
    rowsift.Field("birthday", rowsift.Kind.DATE, aliases=("Nascimento",)),
]
mapping = rowsift.suggest(profile, fields)
result = rowsift.sift(table, profile, mapping, fields)

assert result.summary.kept == 2
assert result.rows[0].values["name"] == "Ana Souza"
assert result.rows[0].values["phone"] == "+5511912345678"
# A phone number cut short is reported, not completed.
assert result.rows[1].values["phone"] is None
assert result.rows[1].issues["phone"].code == "too_short"
```

The header was found under a title and a blank line, each column was matched to a field, and the second phone number came back with a reason code instead of a guess. The [quick start](https://github.com/msantino/rowsift/blob/main/docs/quick-start.md) walks through the same file step by step.

## Documentation

- [Quick start](https://github.com/msantino/rowsift/blob/main/docs/quick-start.md)
- [Reading](https://github.com/msantino/rowsift/blob/main/docs/reading.md): formats, encodings, limits, errors
- [Profiling](https://github.com/msantino/rowsift/blob/main/docs/profiling.md): the header, skipped rows, kinds
- [Cleaning](https://github.com/msantino/rowsift/blob/main/docs/cleaning.md): one function per kind, options, masking
- [Mapping](https://github.com/msantino/rowsift/blob/main/docs/mapping.md): suggestions, confidence, saved mappings
- [Sifting](https://github.com/msantino/rowsift/blob/main/docs/sifting.md): rows, rejections, counts
- [Codes](https://github.com/msantino/rowsift/blob/main/docs/codes.md): every code and what it means

## Status

Early development, version `0.1.1`. The API can still change between minor versions. Before `1.0.0`, a breaking change raises the minor version. Removing or renaming a public name or a code is a breaking change, and adding a code is a minor change.

| Step | State |
|---|---|
| Read | available: `rowsift.read(...)` turns CSV, XLSX and XLS bytes into a grid of text cells and a report, under explicit limits. XLSX and XLS need the `excel` extra |
| Profile | available: `rowsift.profile(table)` finds the header, skips rows that are not data with a code, and gives each column a kind with its share, counts, the low-cardinality signal and masked samples |
| Clean | available: one cleaner per kind, `rowsift.clean.value` to dispatch by kind, masking functions. Phone numbers of a region other than Brazil need the `phone` extra |
| Map | available: `rowsift.suggest(profile, fields)` suggests a column for each declared `Field`, with a confidence level and reason codes. `SavedMapping` and `rowsift.apply_saved` carry a person's choices to the next file without guessing |
| Sift | available: `rowsift.sift(table, profile, mapping, fields)` returns the kept rows with their cleaned values and changes, the rejected rows with the field and issue code, and counts per field. It has no side effect, so it serves as a preview and as the final pass |

## Requirements

Python 3.11 to 3.14. The core has no runtime dependency.

```bash
pip install rowsift              # core: CSV and delimited text
pip install "rowsift[excel]"     # adds XLSX and XLS
pip install "rowsift[phone]"     # adds phone numbers outside Brazil
pip install "rowsift[all]"       # every extra
```

A function that needs an extra that is not installed raises `rowsift.MissingExtraError`, which names the extra.

## Development

You need [uv](https://docs.astral.sh/uv/) and [just](https://just.systems/).

```bash
just setup     # install the project and its tools into .venv
just verify    # lint, type check, tests, text check and build: exactly what CI runs
```

See [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request, and [SECURITY.md](SECURITY.md) to report a vulnerability.

## License

[Apache License 2.0](LICENSE). You can use, modify and distribute the library, including in commercial and closed-source software, as long as you keep the license and the notices.
