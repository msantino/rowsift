"""Saved mappings: keep a person's choices and apply them to the next file."""

from __future__ import annotations

from collections.abc import Mapping as MappingABC
from collections.abc import Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from rowsift.map._fields import Field
from rowsift.map._suggest import check_fields, fingerprint_of
from rowsift.map._types import Choice, Mapping
from rowsift.profile import Profile
from rowsift.types import Confidence, Reason, ReasonCode

__all__ = ["SavedMapping", "apply_saved"]


@dataclass(frozen=True, slots=True)
class SavedMapping:
    """A mapping reduced to what survives between files: header names.

    Attributes:
        fingerprint: the header fingerprint of the file it was saved from.
        assignments: for each field key, the normalized header of the column it
            was mapped to. A field with no column is not listed. Copied into a
            read-only mapping.

    Raises:
        TypeError: if the fingerprint is not ``str`` or an assignment is not a
            ``str`` to ``str`` pair.
        ValueError: if two fields point at the same header.
    """

    fingerprint: str
    assignments: MappingABC[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if type(self.fingerprint) is not str:
            raise TypeError("fingerprint must be str")
        copied = dict(self.assignments)
        for key, header in copied.items():
            if type(key) is not str or type(header) is not str:
                raise TypeError("assignments must map str to str")
        if len(set(copied.values())) != len(copied):
            raise ValueError("two fields are saved on the same header")
        object.__setattr__(self, "assignments", MappingProxyType(copied))

    def __hash__(self) -> int:
        return hash((self.fingerprint, frozenset(self.assignments.items())))

    def __reduce__(self) -> tuple[Any, tuple[Any, ...]]:
        return (type(self), (self.fingerprint, dict(self.assignments)))

    @classmethod
    def from_mapping(cls, mapping: Mapping, profile: Profile) -> SavedMapping:
        """Save the assigned columns of ``mapping`` by their normalized header.

        Raises:
            ValueError: if the fingerprint of ``profile`` differs from the one of
                ``mapping``, that is, the mapping was not made from this profile.
        """
        if fingerprint_of(profile) != mapping.fingerprint:
            raise ValueError("the mapping was not made from this profile: fingerprints differ")
        headers = {column.index: column.normalized_header for column in profile.columns}
        assignments: dict[str, str] = {}
        for choice in mapping.choices:
            if choice.column is None:
                continue
            assignments[choice.field] = headers[choice.column]
        return cls(mapping.fingerprint, assignments)

    def to_dict(self) -> dict[str, Any]:
        """A plain dictionary of text, ready for JSON: ``fingerprint`` and ``assignments``."""
        return {"fingerprint": self.fingerprint, "assignments": dict(self.assignments)}

    @classmethod
    def from_dict(cls, data: MappingABC[str, Any]) -> SavedMapping:
        """Read what ``to_dict`` wrote.

        Raises:
            ValueError: if a key is missing, or two fields share a header.
            TypeError: if a value is not of the expected type.
        """
        try:
            fingerprint = data["fingerprint"]
            assignments = data["assignments"]
        except KeyError as error:
            raise ValueError(f"a saved mapping needs the key {error.args[0]!r}") from None
        if not isinstance(assignments, MappingABC):
            raise TypeError("assignments must be a mapping")
        return cls(fingerprint, dict(assignments))


def apply_saved(profile: Profile, fields: Sequence[Field], saved: SavedMapping) -> Mapping:
    """Restore a saved mapping onto a new profile, without guessing.

    When the fingerprint of the profile equals the saved one, every assignment is
    restored with confidence ``high`` and the reason ``saved_mapping``. When it
    differs, an assignment is restored, with confidence ``medium`` and the same
    reason, only if a column still has the saved normalized header. The others
    come back with no column and the reason ``saved_header_missing``, carrying the
    saved header. A renamed header is never matched by similarity.

    A field the saved mapping does not list comes back with no column, and the
    reason ``required_field_unmatched`` when it is required. An optional field
    the saved mapping does not list has no reasons, as in ``suggest``. A saved key that no
    field declares is ignored.

    Raises:
        ValueError: if two fields have the same key.
    """
    check_fields(fields)
    same_layout = fingerprint_of(profile) == saved.fingerprint
    by_header = {column.normalized_header: column.index for column in profile.columns}
    confidence = Confidence.HIGH if same_layout else Confidence.MEDIUM
    choices: list[Choice] = []
    for field_ in fields:
        header = saved.assignments.get(field_.key)
        if header is None:
            reasons = (Reason(ReasonCode.REQUIRED_FIELD_UNMATCHED),) if field_.required else ()
            choices.append(Choice(field_.key, None, None, reasons))
        elif header in by_header:
            reason = Reason(ReasonCode.SAVED_MAPPING)
            choices.append(Choice(field_.key, by_header[header], confidence, (reason,)))
        else:
            reason = Reason(ReasonCode.SAVED_HEADER_MISSING, {"header": header})
            choices.append(Choice(field_.key, None, None, (reason,)))
    used = {choice.column for choice in choices if choice.column is not None}
    unmapped = tuple(column.index for column in profile.columns if column.index not in used)
    return Mapping(tuple(choices), unmapped, fingerprint_of(profile))
