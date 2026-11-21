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

## Status

Early development. The package is not published yet and the API will change before `0.1.0`.

| Step | State |
|---|---|
| Read | not started |
| Profile | not started |
| Clean | not started |
| Map | not started |

## Requirements

Python 3.11 or newer.

## Development

You need [uv](https://docs.astral.sh/uv/) and [just](https://just.systems/).

```bash
just setup     # install the project and its tools into .venv
just verify    # lint, type check, tests, text check and build: exactly what CI runs
```

See [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request, and [SECURITY.md](SECURITY.md) to report a vulnerability.

## License

[Apache License 2.0](LICENSE). You can use, modify and distribute the library, including in commercial and closed-source software, as long as you keep the license and the notices.
