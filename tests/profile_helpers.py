"""Helpers shared by the profiling tests."""

from rowsift.types import FileFormat, ReadReport, Table


def table(*rows: tuple[str, ...]) -> Table:
    """A table from rows, padded to the widest one."""
    width = max((len(row) for row in rows), default=0)
    padded = tuple(row + ("",) * (width - len(row)) for row in rows)
    report = ReadReport(
        format=FileFormat.CSV,
        encoding="utf-8",
        delimiter=";",
        row_count=len(padded),
        column_count=width,
    )
    return Table(padded, report)


def phone(number: int) -> str:
    """A synthetic mobile number in the unassigned-looking 99999 range."""
    return f"(11) 99999-{number:04d}"
