"""Read spreadsheets written by people and turn them into typed, clean rows."""

from rowsift.map import (
    Alternative,
    Choice,
    Field,
    Mapping,
    SavedMapping,
    apply_saved,
    suggest,
)
from rowsift.profile import ColumnProfile, Profile, ProfileOptions, profile
from rowsift.read import ReadLimits, read
from rowsift.sift import FieldSummary, Rejection, SiftedRow, SiftResult, Summary, sift
from rowsift.types import Confidence, Kind, Reason, ReasonCode

__version__ = "0.0.0"

__all__ = [
    "Alternative",
    "Choice",
    "ColumnProfile",
    "Confidence",
    "Field",
    "FieldSummary",
    "Kind",
    "Mapping",
    "Profile",
    "ProfileOptions",
    "ReadLimits",
    "Reason",
    "ReasonCode",
    "Rejection",
    "SavedMapping",
    "SiftResult",
    "SiftedRow",
    "Summary",
    "__version__",
    "apply_saved",
    "profile",
    "read",
    "sift",
    "suggest",
]
