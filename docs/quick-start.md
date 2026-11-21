# Quick start

rowsift reads a spreadsheet exported by a person and gives back typed rows. This page runs the four steps on one small file. Every example on this page is run by the test suite.

## Install

```bash
pip install rowsift
```

The core has no dependency and reads CSV and other delimited text. Reading XLSX and XLS needs the `excel` extra, and cleaning a phone number of a region other than Brazil needs the `phone` extra:

```bash
pip install "rowsift[excel]"   # XLSX and XLS
pip install "rowsift[phone]"   # phone numbers outside Brazil
pip install "rowsift[all]"     # both
```

A function that needs an extra that is not installed raises `rowsift.MissingExtraError`, whose `extra` attribute names what to install. It never falls back silently.

## The four steps

```python
import rowsift

data = (
    "Cadastro de clientes\n"
    "\n"
    "Nome;Celular;Nascimento;Valor\n"
    "ana souza;(11) 91234-5678;03/04/1990;1.234,50\n"
    "bruno lima;11 8765-4321;15/08/1985;99,90\n"
    "carla dias;(11) 9123;22/11/1979;10,00\n"
).encode("utf-8")

# 1. Read: bytes to a grid of text cells, and how it was read.
table = rowsift.read(data)
assert table.report.format == "csv"
assert table.report.delimiter == ";"

# 2. Profile: where the header is and what each column holds.
profile = rowsift.profile(table)
assert profile.header_row == 2
assert profile.data_rows == 3

# 3. Map: declare the fields you want, get a column for each.
fields = [
    rowsift.Field("name", rowsift.Kind.NAME, required=True, aliases=("Nome",)),
    rowsift.Field("phone", rowsift.Kind.PHONE, aliases=("Celular",)),
    rowsift.Field("birthday", rowsift.Kind.DATE, aliases=("Nascimento",)),
    rowsift.Field("amount", rowsift.Kind.MONEY, aliases=("Valor",)),
]
mapping = rowsift.suggest(profile, fields)
assert [choice.column for choice in mapping.choices] == [0, 1, 2, 3]

# 4. Sift: clean every data row with the kind of its field.
result = rowsift.sift(table, profile, mapping, fields)
assert result.summary.data_rows == 3
assert result.summary.kept == 3
first = result.rows[0]
assert first.values["name"] == "Ana Souza"
assert first.values["phone"] == "+5511912345678"
assert str(first.values["birthday"]) == "1990-04-03"
assert str(first.values["amount"]) == "1234.50"

# A value that cannot be normalized is reported, never corrected.
assert result.rows[1].changes["phone"][0].code == "ninth_digit_inserted"
assert result.rows[2].values["phone"] is None
assert result.rows[2].issues["phone"].code == "too_short"
```

Reading the output:

- `table.report` says what the reader decided: format, encoding, delimiter, sheet.
- `profile` found the header on the third row, below a title and a blank line.
- `mapping.choices` has one `Choice` per declared field, with a column, a confidence and the reasons as codes.
- `result.rows` are the kept rows. Each one has the cleaned `values`, the `changes` made to them (`ninth_digit_inserted` above) and the `issues` of values that could not be cleaned.
- `result.rejected` lists the rows that were left out, each with the field and the issue code. A row is rejected only when a required field is empty or fails.
- `result.summary` counts every change and every issue code per field.

Every reason in the output is a code with data. The library writes no message: your application turns a code into text in its own language. The codes are listed in [codes.md](codes.md).

## Next

- [Reading](reading.md): formats, encodings, limits, errors.
- [Profiling](profiling.md): the header, skipped rows, kinds, samples.
- [Cleaning](cleaning.md): one function per kind, options, masking.
- [Mapping](mapping.md): suggestions, confidence, saved mappings.
- [Sifting](sifting.md): rows, rejections, counts.
- [Codes](codes.md): every code and what it means.
