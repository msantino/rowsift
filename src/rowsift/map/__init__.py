"""Map: suggest which column feeds each field the application declares.

``suggest`` scores the columns of a profile against the declared ``Field`` values
and returns a ``Mapping``: one ``Choice`` per field with a confidence and the
reasons as codes, the columns no field uses, and the fingerprint of the headers.
A person can change the result with ``Mapping.assign`` and ``Mapping.unassign``.
``SavedMapping`` keeps a mapping between files and ``apply_saved`` restores it
without guessing.
"""

from rowsift.map._fields import Field
from rowsift.map._saved import SavedMapping, apply_saved
from rowsift.map._suggest import suggest
from rowsift.map._types import Alternative, Choice, Mapping

__all__ = [
    "Alternative",
    "Choice",
    "Field",
    "Mapping",
    "SavedMapping",
    "apply_saved",
    "suggest",
]
