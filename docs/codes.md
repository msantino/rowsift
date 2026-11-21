# Codes

Everything the library explains is a code plus structured data. There are no sentences: your application writes the message, in its own language and tone. A code is a string (each enumeration is a `StrEnum`), so it serializes as plain text and compares with `==` against a string.

Removing or renaming a code is a breaking change. Adding one is a minor change, and the release notes list it. The `data` of a code is a read-only mapping of scalars.

This page lists every code. A test keeps it equal to the enumerations in the code.

## `ChangeCode`

A transformation that altered the meaning-bearing content of a value. Found in `Cleaned.changes` and `SiftedRow.changes`.

| Code | Meaning |
|---|---|
| `ninth_digit_inserted` | an 8-digit mobile number got the ninth digit |
| `multiple_values` | the cell held several values and the first valid one was kept. `count` is the number of fragments with at least 8 digits |
| `two_digit_year_expanded` | a two-digit year was resolved with the pivot. `year` is the result |
| `year_discarded` | a full date was reduced to a day and month |
| `leading_zeros_restored` | zeros that a spreadsheet drops were put back, because the padded value passed its check |
| `separator_inferred` | the decimal and thousands separators were read as written because the value contradicts the options |
| `case_changed` | a name written entirely in one case was recased |
| `serial_date_converted` | a spreadsheet serial number was read as a date |
| `time_defaulted` | a date with no time became midnight |

## `IssueCode`

Why a value could not be normalized, or why a row was rejected. Found in `Cleaned.issue`, `SiftedRow.issues` and `Rejection.issue`.

| Code | Meaning |
|---|---|
| `too_short` | a phone number has too few digits. `digits` is the count |
| `truncated` | a phone number looks cut short by an export. `digits` is the count |
| `invalid_area_code` | the area code is not in the national list |
| `not_mobile` | a landline where a mobile was required |
| `invalid_date` | the date does not exist, such as 30 February |
| `not_a_date` | the text is not a date, including a date with no year |
| `not_a_number` | the text is not a number, or holds a character outside the supported digits, or a whole number has a fraction |
| `invalid_check_digit` | a CPF or CNPJ fails its check digits, or is one repeated digit |
| `invalid_email` | the text is not an address of the supported shape |
| `not_in_allowed_values` | the value is not one of the allowed values of a category |
| `required_missing` | a required field is empty |
| `invalid_phone` | the text has no valid phone shape: letters, a foreign country code, too many digits, an extension in the same fragment |
| `invalid_length` | a CPF, CNPJ or postal code has a wrong digit count. `digits` and `expected` give both |
| `not_a_time` | the text is not a time of day, or is out of range |
| `not_a_boolean` | the text is not a known yes or no word |

## `ReasonCode`

Why a column was, or was not, suggested for a field. Found in `Choice.reasons`.

| Code | Meaning |
|---|---|
| `header_matches_alias` | the header equals an alias of the field. `alias` is the alias |
| `header_contains_alias` | the header contains every word of an alias. `alias` is the alias |
| `content_fits_kind` | the values fit the field kind. `kind` is the column kind and `share` the share that fits |
| `content_conflicts_with_kind` | the values do not fit the field kind. `column_kind`, `field_kind` and `share` give the detail |
| `only_candidate` | the column is the only one left that fits |
| `required_field_unmatched` | a required field has no column |
| `saved_mapping` | the column comes from a saved mapping |
| `saved_header_missing` | a saved header is no longer in the file. `header` is the saved header |
| `set_by_caller` | the choice was set with `Mapping.assign` or `Mapping.unassign`. `displaced_by` names the field that took the column, when one did |

## `SkipCode`

Why a row is not a data row. Found in `Profile.skipped_rows`.

| Code | Meaning |
|---|---|
| `empty` | every cell is empty |
| `before_header` | a row above the header, such as a title |
| `repeated_header` | the header repeated in the middle of the data |
| `total_row` | a closing row of totals |

## `ReadNote`

Something the reader did that the caller may want to know about. Found in `ReadReport.notes`.

| Code | Meaning |
|---|---|
| `bom_removed` | a byte order mark was removed from the text |
| `merged_cells_filled` | merged cells of a workbook were filled with the value of the top-left cell |
| `trailing_empty_columns_dropped` | trailing columns empty in every row were dropped |
| `unterminated_quote` | a quoted field was never closed |
| `wrapped_lines_unwrapped` | every line of the file was one quoted field, and the wrapping was removed to read the columns inside; `report.delimiter` is the inner delimiter |

## `ErrorCode`

The code carried by every exception the library raises on purpose.

| Code | Meaning |
|---|---|
| `unsupported_file` | the bytes are no supported format |
| `sheet_not_found` | the requested sheet does not exist |
| `password_protected` | the workbook is encrypted with a password |
| `limit_exceeded` | a read limit was exceeded |
| `missing_extra` | a feature needs an extra that is not installed |
| `decoding_failed` | the text could not be decoded |

## Exceptions

Every exception derives from `RowsiftError` and carries a `code`. Messages never include cell contents.

| Exception | Code | Attributes |
|---|---|---|
| `RowsiftError` | any | `code` |
| `UnsupportedFileError` | `unsupported_file`, `sheet_not_found` or `password_protected` | |
| `LimitExceededError` | `limit_exceeded` | `limit`, `allowed` |
| `MissingExtraError` | `missing_extra` | `extra` |
| `DecodingError` | `decoding_failed` | |

## `Kind`

What a column or a value holds.

| Code | Meaning |
|---|---|
| `text` | free text |
| `name` | a person's name |
| `integer` | a whole number |
| `decimal` | a number with decimals |
| `money` | an amount of money |
| `boolean` | a yes or no |
| `date` | a calendar date |
| `day_month` | a day and a month with no year |
| `time` | a time of day |
| `datetime` | a date and a time of day |
| `phone` | a phone number |
| `email` | an e-mail address |
| `cpf` | a Brazilian individual tax id |
| `cnpj` | a Brazilian company tax id |
| `postal_code` | a Brazilian postal code (CEP) |
| `category` | one of a small set of values |

## `Confidence`

How sure a mapping suggestion is.

| Code | Meaning |
|---|---|
| `high` | the header equals an alias and the content fits the kind, or the person chose it |
| `medium` | one strong signal and the other neutral, or restored from a saved mapping with a changed file |
| `low` | anything weaker |

## `FileFormat`

The format a file was detected as, from its content.

| Code | Meaning |
|---|---|
| `csv` | delimited text |
| `xlsx` | an XLSX workbook |
| `xls` | an XLS workbook |

## `LineType`

Whether a phone number is a mobile or a landline.

| Code | Meaning |
|---|---|
| `mobile` | a mobile number |
| `landline` | a landline number |
