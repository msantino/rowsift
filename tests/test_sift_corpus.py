"""Every sifting fixture goes file in, ``SiftResult`` out, and is compared with the file beside it.

Each ``<name>.expected.json`` holds the fields to declare, optional column
assignments the way a person would make them on a review screen, and the
expected result.
"""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

import rowsift
from rowsift import Field, Kind, SiftResult, read, sift, suggest
from rowsift.clean import CleanOptions
from rowsift.types import DayMonth, Issue

FIXTURES = Path(__file__).parent / "fixtures" / "sifting"
EXPECTED = sorted(FIXTURES.glob("*.expected.json"), key=lambda path: path.name)


def fixture_of(expected: Path) -> Path:
    stem = expected.name.removesuffix(".expected.json")
    (match,) = (path for path in expected.parent.glob(f"{stem}.*") if path != expected)
    return match


def encode_value(value: object) -> Any:
    """A cleaned value as JSON: text and numbers as they are, the rest by name."""
    if isinstance(value, DayMonth):
        return {"day": value.day, "month": value.month}
    if isinstance(value, Decimal):
        return {"decimal": str(value)}
    if isinstance(value, date):
        return {"date": value.isoformat()}
    if value is None or isinstance(value, bool | int | float):
        return value
    return str(value)


def encode_issue(issue: Issue) -> dict[str, Any]:
    return {"code": str(issue.code), "data": dict(issue.data)}


def encode(result: SiftResult) -> dict[str, Any]:
    """The result as the JSON the expected file holds."""
    return {
        "rows": [
            {
                "number": row.number,
                "values": {key: encode_value(value) for key, value in row.values.items()},
                "extras": dict(row.extras),
                "changes": {
                    key: [{"code": str(c.code), "data": dict(c.data)} for c in changes]
                    for key, changes in row.changes.items()
                },
                "issues": {key: encode_issue(issue) for key, issue in row.issues.items()},
            }
            for row in result.rows
        ],
        "rejected": [
            {"number": r.number, "field": r.field, "issue": encode_issue(r.issue)}
            for r in result.rejected
        ],
        "summary": {
            "data_rows": result.summary.data_rows,
            "kept": result.summary.kept,
            "rejected": result.summary.rejected,
            "fields": {
                key: {
                    "filled": item.filled,
                    "changes": {str(code): count for code, count in item.changes.items()},
                    "issues": {str(code): count for code, count in item.issues.items()},
                }
                for key, item in result.summary.fields.items()
            },
        },
    }


def sift_fixture(expected_path: Path) -> SiftResult:
    """Run the whole pipeline over the fixture the way an application would."""
    spec: dict[str, Any] = json.loads(expected_path.read_text(encoding="utf-8"))
    fields = [
        Field(
            item["key"],
            Kind(item["kind"]),
            required=item.get("required", False),
            aliases=tuple(item.get("aliases", ())),
            one_of=tuple(item["one_of"]) if "one_of" in item else None,
        )
        for item in spec["fields"]
    ]
    table = read(fixture_of(expected_path).read_bytes())
    profile = rowsift.profile(table)
    mapping = suggest(profile, fields)
    for key, column in spec.get("assign", {}).items():
        mapping = mapping.assign(key, column)
    options = CleanOptions(**spec["options"]) if "options" in spec else None
    return sift(table, profile, mapping, fields, options=options)


def test_every_fixture_is_paired_with_an_expected_result() -> None:
    assert EXPECTED
    for expected in EXPECTED:
        assert fixture_of(expected).is_file()


@pytest.mark.parametrize("expected_path", EXPECTED, ids=lambda path: path.name.split(".")[0])
def test_fixture_sifts_as_expected(expected_path: Path) -> None:
    spec: dict[str, Any] = json.loads(expected_path.read_text(encoding="utf-8"))
    assert encode(sift_fixture(expected_path)) == spec["expected"]


@pytest.mark.parametrize("expected_path", EXPECTED, ids=lambda path: path.name.split(".")[0])
def test_fixture_sifts_the_same_twice(expected_path: Path) -> None:
    assert sift_fixture(expected_path) == sift_fixture(expected_path)
