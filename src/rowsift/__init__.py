"""Read spreadsheets written by people and turn them into typed, clean rows."""

from rowsift.profile import ColumnProfile, Profile, ProfileOptions, profile
from rowsift.read import ReadLimits, read

__version__ = "0.0.0"

__all__ = [
    "ColumnProfile",
    "Profile",
    "ProfileOptions",
    "ReadLimits",
    "__version__",
    "profile",
    "read",
]
