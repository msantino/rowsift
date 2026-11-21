# Cleaning

The cleaners turn one value, the text of a cell, into its normalized form, or say why they could not. They take no table and keep no state, so they are usable on their own.

## Behavior

Every cleaner returns a `rowsift.Cleaned` with three parts:

- `value`: the normalized value, or `None`.
- `changes`: what was altered on the way, as `rowsift.Change` codes with data.
- `issue`: the reason it failed, as a `rowsift.Issue` code with data, or `None`.

A non-empty input gives a `value` or an `issue`, never both. An empty input gives neither.

```python
from rowsift import clean

ok = clean.phone("(11) 8765-4321")
assert ok.value == "+5511987654321"
assert ok.value.line_type == "mobile"
assert [change.code for change in ok.changes] == ["ninth_digit_inserted"]

cut = clean.phone("(11) 98765")
assert cut.value is None
assert cut.issue is not None
assert cut.issue.code == "too_short"
assert cut.issue.data["digits"] == 7

assert clean.phone("").value is None
assert clean.phone("").issue is None
```

**A value that cannot be normalized with certainty is returned with a reason, never corrected.** A phone number cut short by an export is reported as `truncated` or `too_short`. A date that does not exist is `invalid_date`. Where a change alters what a value means, such as inserting the ninth digit of a mobile number, a change code says so.

`clean.value(text, kind)` cleans by `rowsift.Kind` and is what `sift` calls for each field:

```python
from rowsift import Kind, clean

assert str(clean.value("R$ 1.234,50", Kind.MONEY).value) == "1234.50"
assert clean.value("Sim", "boolean").value is True
```

## The cleaners

| Function | Value | Notes |
|---|---|---|
| `clean.text` | `str` | trimmed. Empty input gives no value |
| `clean.name` | `str` | whitespace collapsed. A name written entirely in one case is recased with the particles `da`, `de`, `do`, `das`, `dos`, `e` kept lowercase after the first word, and `case_changed` is reported |
| `clean.integer` | `int` | parsed like `decimal`. A non-zero fraction is `not_a_number`, never truncated |
| `clean.decimal` | `Decimal` | currency symbols removed, minus sign or parentheses mean negative. Exponent notation and numbers of more than 38 digits are `not_a_number` |
| `clean.money` | `Decimal` | like `decimal`, never rounded |
| `clean.boolean` | `bool` | `sim`, `s`, `yes`, `y`, `true`, `t`, `1`, `verdadeiro` and `nao`, `n`, `no`, `false`, `f`, `0`, `falso`. Case and accents are ignored |
| `clean.date` | `datetime.date` | numeric dates, ISO dates, month names in Portuguese or English, and spreadsheet serial numbers (`serial_date_converted`) |
| `clean.day_month` | `rowsift.DayMonth` | a day and month with no year, such as a birthday. A full date is accepted and the year discarded (`year_discarded`). No year is ever invented, and 29 February is valid |
| `clean.time` | `datetime.time` | `H:MM`, `HH:MM:SS`, `9h30`, `9h`, and a 12-hour clock. No time zone is read |
| `clean.datetime` | `datetime.datetime` | naive. A date with no time becomes midnight and reports `time_defaulted` |
| `clean.phone` | `rowsift.PhoneNumber` | E.164 text with a `line_type`. See below |
| `clean.email` | `str` | trimmed, domain in lowercase, local part as written. Quoted local parts and internationalized domains are refused |
| `clean.cpf` | `str` | the 11 digits, check digits verified |
| `clean.cnpj` | `str` | the 14 digits, check digits verified |
| `clean.postal_code` | `str` | a Brazilian CEP as its 8 digits |
| `clean.category` | `str` | one of `one_of`, in its declared spelling. Case, accents and repeated whitespace are ignored when matching |

Tax ids and postal codes that a spreadsheet stored as numbers lose their leading zeros. A value one or two digits short is padded only when the padded value passes the check digits (a postal code has none, so a 7-digit value is padded), and `leading_zeros_restored` is reported.

```python
from rowsift import clean

padded = clean.cpf("123456797")
assert padded.value == "00123456797"
assert [change.code for change in padded.changes] == ["leading_zeros_restored"]
assert clean.cpf("123.456.789-00").issue.code == "invalid_check_digit"
assert clean.postal_code("1310100").value == "01310100"
assert clean.email(" Ana@Example.COM ").value == "Ana@example.com"
assert clean.boolean("Talvez").issue.code == "not_a_boolean"
```

### Phones

With region `BR`, the default, the rules are native and need no extra. The country code (`+55`, `55`, `0055`) and the trunk zero are removed, the area code must be one of the national list, and the number is a mobile (11 digits, or 10 digits whose subscriber part starts with 6, 7 or 8) or a landline (starts with 2 to 5).

- A mobile written with 8 subscriber digits gets the ninth digit, reported as `ninth_digit_inserted`. With `insert_ninth_digit=False` it is `too_short`.
- A 10-digit number whose subscriber part starts with 9 is `truncated`. Fewer than 10 digits is `too_short`. An unknown area code is `invalid_area_code`. A landline with `require_mobile` is `not_mobile`. Any other shape is `invalid_phone`.
- Several numbers in one cell (separated by `/`, `;`, `|`, `,`, a line break, `ou` or `e`) give the first valid one and `multiple_values` with the `count`.

For a region other than `BR`, the `phone` extra parses the number. Without it, `rowsift.MissingExtraError` is raised with `extra == "phone"`, whatever the cell holds.

## Options

`rowsift.CleanOptions` holds every knob, passed by keyword. The defaults follow Brazilian conventions.

| Option | Default | Meaning |
|---|---|---|
| `region` | `"BR"` | two-letter region of phone numbers and postal codes. Only `BR` has native rules |
| `date_order` | `"dmy"` | `"dmy"` or `"mdy"` for numeric dates whose year comes last. A date that starts with a four-digit year is always year, month, day |
| `decimal_separator` | `","` | `","` or `"."`. The other character is the thousands separator. A value that contradicts it unambiguously, such as `1,234.56`, is read as written and reports `separator_inferred` |
| `two_digit_year_pivot` | `30` | a two-digit year up to the pivot is in the 2000s, a larger one in the 1900s. Reported as `two_digit_year_expanded` |
| `insert_ninth_digit` | `True` | insert the ninth digit of an 8-digit mobile and report it |
| `name_case` | `"title"` | `"title"` or `"keep"` |
| `require_mobile` | `False` | a landline is an issue |
| `one_of` | `None` | allowed values of a `category` |

```python
from rowsift import CleanOptions, clean

assert str(clean.date("03/04/1990").value) == "1990-04-03"
assert str(clean.date("03/04/1990", CleanOptions(date_order="mdy")).value) == "1990-03-04"

two_digits = clean.date("12/03/88")
assert str(two_digits.value) == "1988-03-12"
assert two_digits.changes[0].code == "two_digit_year_expanded"

dotted = CleanOptions(decimal_separator=".")
assert str(clean.decimal("1,234.56", dotted).value) == "1234.56"
```

## Masking

A value that will be displayed is masked first. The masks keep enough to recognize a value and hide the rest:

| Function | Example |
|---|---|
| `clean.mask_phone` | `(11) 99999-0042` becomes `11 *******42` |
| `clean.mask_cpf` | `***.***.***-09` |
| `clean.mask_cnpj` | the last 2 digits and the punctuation |
| `clean.mask_email` | `a***@example.com` |
| `clean.mask_name` | `Helena P. A.` |
| `clean.mask` | by `Kind`. A kind with no masking rule is returned as written |

A value that does not have the shape the mask expects is hidden entirely. Exceptions never carry cell contents.

```python
from rowsift import Kind, clean

assert clean.mask_phone("(11) 99999-0042") == "11 *******42"
assert clean.mask_email("ana@example.com") == "a***@example.com"
assert clean.mask("(11) 99999-0042", Kind.PHONE) == "11 *******42"
```

## Limits

- Only the digits 0 to 9 count in tax ids, phones and postal codes. A digit of another script is `not_a_number`.
- Native rules cover Brazil. A postal code for another region raises `ValueError`.
- Time zones are not read, and no date is ever completed with the current year.
