"""Helpers shared by the mapping tests."""

from rowsift.profile import ColumnProfile, Profile, RunnerUp, normalize_header
from rowsift.types import Kind


def column(
    index: int,
    header: str,
    kind: Kind = Kind.TEXT,
    share: float = 1.0,
    *,
    runner_up: tuple[Kind, float] | None = None,
    filled: int = 10,
) -> ColumnProfile:
    """A column profile with the fields the mapping reads."""
    return ColumnProfile(
        index=index,
        header=header,
        normalized_header=normalize_header(header) or f"column_{index + 1}",
        kind=kind,
        kind_share=share if filled else 0.0,
        runner_up=RunnerUp(*runner_up) if runner_up else None,
        filled=filled,
        distinct=filled,
        low_cardinality=False,
        top_values=(),
        samples=(),
    )


def profile(*columns: ColumnProfile, header: bool = True) -> Profile:
    """A profile of the given columns."""
    return Profile(
        header_row=0 if header else None,
        data_start=1 if header else 0,
        data_rows=10,
        skipped_rows=(),
        columns=columns,
    )
