"""Every reading fixture is read and compared with the grid and report written next to it."""

import json
from pathlib import Path
from typing import Any

import pytest

from rowsift import read
from rowsift.errors import LimitExceededError

pytest.importorskip("openpyxl")
pytest.importorskip("xlrd")

FIXTURES = Path(__file__).parent / "fixtures" / "reading"
EXPECTED = sorted(FIXTURES.rglob("*.expected.json"), key=lambda path: path.as_posix())


def fixture_of(expected: Path) -> Path:
    stem = expected.name.removesuffix(".expected.json")
    (match,) = (path for path in expected.parent.glob(f"{stem}.*") if path != expected)
    return match


def test_every_fixture_is_paired_with_an_expected_result() -> None:
    assert EXPECTED
    for expected in EXPECTED:
        assert fixture_of(expected).is_file()


@pytest.mark.parametrize(
    "expected_path", EXPECTED, ids=lambda path: path.relative_to(FIXTURES).as_posix()
)
def test_fixture_reads_as_expected(expected_path: Path) -> None:
    expected: dict[str, Any] = json.loads(expected_path.read_text(encoding="utf-8"))
    data = fixture_of(expected_path).read_bytes()
    read_args: dict[str, Any] = expected.get("read_args", {})
    if "error" in expected:
        with pytest.raises(LimitExceededError) as caught:
            read(data, **read_args)
        assert caught.value.limit == expected["error"]["limit"]
        return
    table = read(data, **read_args)
    assert [list(row) for row in table.rows] == expected["rows"]
    report = table.report
    wanted = expected["report"]
    assert str(report.format) == wanted["format"]
    assert report.encoding == wanted["encoding"]
    assert report.delimiter == wanted["delimiter"]
    assert report.sheet == wanted["sheet"]
    assert list(report.sheets) == wanted["sheets"]
    assert report.row_count == wanted["row_count"]
    assert report.column_count == wanted["column_count"]
    assert [str(note) for note in report.notes] == wanted["notes"]
