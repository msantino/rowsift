"""Options of the profile layer."""

from __future__ import annotations

from dataclasses import dataclass, field

from rowsift.clean import CleanOptions

__all__ = ["ProfileOptions"]


@dataclass(frozen=True, slots=True, kw_only=True)
class ProfileOptions:
    """Every knob of ``profile``. All are passed by keyword.

    Attributes:
        header_scan_rows: how many non-empty rows are examined as header
            candidates.
        kind_threshold: the share of non-empty sampled values a kind must fit
            for a column to take it, above 0 and at most 1.
        sample_rows: how many data rows are read to infer the kind.
        low_cardinality_min_filled: a column needs at least this many filled
            cells to be low-cardinality.
        low_cardinality_max_distinct: and at most this many distinct values.
        low_cardinality_max_share: and at most this share of distinct values
            over filled cells.
        sample_count: how many distinct sample values to keep per column.
        mask_samples: mask samples and top values by the kind of the column.
            Turn it off only for values that are safe to display.
        clean: the options the cleaners run with while inferring kinds, such as
            the order of the day and the month.

    Raises:
        ValueError: if a value is outside what the attribute allows.
    """

    header_scan_rows: int = 20
    kind_threshold: float = 0.8
    sample_rows: int = 5000
    low_cardinality_min_filled: int = 20
    low_cardinality_max_distinct: int = 12
    low_cardinality_max_share: float = 0.05
    sample_count: int = 3
    mask_samples: bool = True
    clean: CleanOptions = field(default_factory=CleanOptions)

    def __post_init__(self) -> None:
        for name in (
            "header_scan_rows",
            "sample_rows",
            "low_cardinality_min_filled",
            "low_cardinality_max_distinct",
            "sample_count",
        ):
            value = getattr(self, name)
            if type(value) is not int or value < (1 if name.endswith("rows") else 0):
                raise ValueError(f"{name} must be a whole number in range")
        for name in ("kind_threshold", "low_cardinality_max_share"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int | float):
                raise ValueError(f"{name} must be a number")
        if not 0 < self.kind_threshold <= 1:
            raise ValueError("kind_threshold must be above 0 and at most 1")
        if not 0 <= self.low_cardinality_max_share <= 1:
            raise ValueError("low_cardinality_max_share must be between 0 and 1")
        if type(self.mask_samples) is not bool:
            raise ValueError("mask_samples must be a bool")
        if not isinstance(self.clean, CleanOptions):
            raise ValueError("clean must be a CleanOptions")
