"""Profile a table: where the header is, which rows are data, what each column holds."""

from rowsift.profile._headers import normalize_header
from rowsift.profile._options import ProfileOptions
from rowsift.profile._profile import profile
from rowsift.profile._types import ColumnProfile, Profile, RunnerUp, SkippedRow, TopValue

__all__ = [
    "ColumnProfile",
    "Profile",
    "ProfileOptions",
    "RunnerUp",
    "SkippedRow",
    "TopValue",
    "normalize_header",
    "profile",
]
