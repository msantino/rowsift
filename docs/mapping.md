# Mapping

`rowsift.suggest` takes a profile and the fields your application declares, and suggests which column feeds each field. The library declares no field of its own: every field comes from you.

## Declare fields

```python
import rowsift

fields = [
    rowsift.Field("name", rowsift.Kind.NAME, required=True, aliases=("Nome", "Nome completo")),
    rowsift.Field("phone", rowsift.Kind.PHONE, aliases=("Celular", "Telefone")),
    rowsift.Field("email", rowsift.Kind.EMAIL, required=True),
    rowsift.Field("plan", rowsift.Kind.CATEGORY, one_of=("Basic", "Plus")),
]
assert fields[0].key == "name"
```

A `rowsift.Field` has a `key` (the name your application uses), a `kind`, and by keyword `required`, `aliases` (other headers the column may carry), `one_of` (for a category) and `options` (cleaning options for this field alone). The key counts as one of its aliases, and headers are compared with case, accents and punctuation ignored.

## Suggest

```python
import rowsift

table = rowsift.read("Nome;Celular;Obs\nAna;(11) 91234-5678;x\n".encode("utf-8"))
profile = rowsift.profile(table)
fields = [
    rowsift.Field("name", rowsift.Kind.NAME, required=True, aliases=("Nome",)),
    rowsift.Field("phone", rowsift.Kind.PHONE, aliases=("Celular",)),
    rowsift.Field("email", rowsift.Kind.EMAIL, required=True),
]

mapping = rowsift.suggest(profile, fields)
name, phone, email = mapping.choices

assert (name.column, name.confidence) == (0, "high")
assert [reason.code for reason in name.reasons] == ["header_matches_alias", "content_fits_kind"]
assert (phone.column, phone.confidence) == (1, "high")
assert email.column is None
assert email.confidence is None
assert [reason.code for reason in email.reasons] == ["required_field_unmatched"]
assert mapping.unmapped == (2,)
```

A `rowsift.Mapping` holds one `Choice` per declared field, in declaration order, the `unmapped` column indexes (so you can offer them as extra attributes) and a `fingerprint` of the headers. A `Choice` has the `column` (or `None`), the `confidence`, the `reasons` as codes with data, and the `alternatives`, the other candidate columns with their own confidence.

- **Confidence** is `high` only when a header equals an alias and the content fits the kind. It is `medium` with one strong signal and the other neutral, and `low` otherwise.
- **A column with a header that says nothing** is suggested only when its kind is one that values alone reveal (a phone, an e-mail, a date and so on) and equals the field kind.
- **A column feeds at most one field.**
- **A required field with no column** has no column and the reason `required_field_unmatched`.

Confidence is a signal to show the person, not a verdict. Show the choices, and let the person change them.

## Change a mapping

`Mapping.assign` and `Mapping.unassign` return a new mapping, keep the rule that a column feeds at most one field, and record the change with the reason `set_by_caller`:

```python
import rowsift

table = rowsift.read("A;B;C\n1;2;3\n".encode("utf-8"))
profile = rowsift.profile(table)
fields = [rowsift.Field("first", rowsift.Kind.INTEGER, aliases=("A",))]
mapping = rowsift.suggest(profile, fields)

moved = mapping.assign("first", 2)
assert moved.choices[0].column == 2
assert moved.choices[0].confidence == "high"
assert moved.choices[0].reasons[0].code == "set_by_caller"
assert 0 in moved.unmapped

cleared = moved.unassign("first")
assert cleared.choices[0].column is None
```

## Save a mapping for the next file

`rowsift.SavedMapping` keeps a mapping as header names, which survive between files. `rowsift.apply_saved` restores it on a new profile **without guessing**:

- When the header fingerprint is the same, every assignment is restored with confidence `high` and the reason `saved_mapping`.
- When it differs, an assignment is restored with confidence `medium` only if a column still has the saved normalized header. The others come back with no column and the reason `saved_header_missing`, carrying the saved `header`. A renamed header is never matched by similarity.

```python
import rowsift

fields = [
    rowsift.Field("name", rowsift.Kind.NAME, aliases=("Nome",)),
    rowsift.Field("phone", rowsift.Kind.PHONE, aliases=("Tel",)),
]

first = rowsift.read("Nome;Tel;Obs\nAna;(11) 91234-5678;x\n".encode("utf-8"))
first_profile = rowsift.profile(first)
mapping = rowsift.suggest(first_profile, fields)

saved = rowsift.SavedMapping.from_mapping(mapping, first_profile)
stored = saved.to_dict()  # plain text, ready for JSON

second = rowsift.read("Obs;Nome;Tel\nx;Bia;(11) 91234-5678\n".encode("utf-8"))
second_profile = rowsift.profile(second)
restored = rowsift.apply_saved(second_profile, fields, rowsift.SavedMapping.from_dict(stored))

assert [(choice.field, choice.column) for choice in restored.choices] == [("name", 1), ("phone", 2)]
assert restored.choices[0].confidence == "medium"
assert restored.choices[0].reasons[0].code == "saved_mapping"
```

## Limits

- Matching is by header text and by content kind. A header written in a language you did not list as an alias is not matched.
- `SavedMapping.from_mapping` raises `ValueError` when the mapping was not made from the profile you pass.
