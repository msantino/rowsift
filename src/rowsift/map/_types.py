"""Value types of the mapping layer."""

from __future__ import annotations

from dataclasses import dataclass, replace

from rowsift.types import Confidence, Reason, ReasonCode

__all__ = ["Alternative", "Choice", "Mapping"]


@dataclass(frozen=True, slots=True)
class Alternative:
    """Another column a field could take, with the confidence it would carry."""

    column: int
    confidence: Confidence


@dataclass(frozen=True, slots=True)
class Choice:
    """The column suggested for one field.

    Attributes:
        field: the key of the field.
        column: the 0-based index of the suggested column, or ``None`` when no
            column is assigned.
        confidence: how sure the suggestion is, or ``None`` when there is no
            column.
        reasons: the codes, with their data, that produced the suggestion or
            explain why there is none.
        alternatives: the other columns that were candidates for the field, best
            first, each with its own confidence.
    """

    field: str
    column: int | None
    confidence: Confidence | None
    reasons: tuple[Reason, ...] = ()
    alternatives: tuple[Alternative, ...] = ()

    def __post_init__(self) -> None:
        if (self.column is None) != (self.confidence is None):
            raise ValueError("a choice has a column and a confidence, or neither")


@dataclass(frozen=True, slots=True)
class Mapping:
    """Which column feeds which field.

    Attributes:
        choices: one per declared field, in declaration order.
        unmapped: the indexes of the columns no field uses, in table order. The
            caller can offer them as extra attributes, using their profile.
        fingerprint: SHA-256 in hexadecimal of the normalized headers in column
            order, joined by a newline. It does not change with case, accents,
            punctuation or spacing in the headers.

    A column feeds at most one field. ``assign`` and ``unassign`` return a new
    mapping and keep that rule.

    Raises:
        ValueError: if two choices share a field key or a column, a column index
            is negative, ``unmapped`` is not sorted and free of repeats, or a
            column is both assigned and listed as unmapped.
    """

    choices: tuple[Choice, ...]
    unmapped: tuple[int, ...]
    fingerprint: str

    def __post_init__(self) -> None:
        keys = [choice.field for choice in self.choices]
        columns = [choice.column for choice in self.choices if choice.column is not None]
        if len(set(keys)) != len(keys):
            raise ValueError("two choices share a field key")
        if len(set(columns)) != len(columns):
            raise ValueError("a column feeds more than one field")
        if any(index < 0 for index in (*columns, *self.unmapped)):
            raise ValueError("a column index is negative")
        if list(self.unmapped) != sorted(set(self.unmapped)):
            raise ValueError("unmapped must be sorted, without repeats")
        if set(columns) & set(self.unmapped):
            raise ValueError("a column is both assigned and unmapped")

    def assign(self, field_key: str, column_index: int) -> Mapping:
        """Point a field at a column, as the caller decided.

        The new choice has confidence ``high`` and the reason ``set_by_caller``.
        The column the field had before goes to ``unmapped``. A field that held
        the new column loses it, and its choice carries the reason
        ``set_by_caller`` with ``displaced_by`` set to ``field_key``. The column a
        choice gave up, in either case, is added to its alternatives, so a review
        screen can offer it back.

        Raises:
            ValueError: if no choice has the key, or ``column_index`` is not a
                column of the mapping.
            TypeError: if ``column_index`` is not an ``int``.
        """
        if type(column_index) is not int:
            raise TypeError("column_index must be int")
        previous = self._choice(field_key)
        if column_index not in self._columns():
            raise ValueError(f"column {column_index} is not a column of the mapping")
        choices: list[Choice] = []
        for choice in self.choices:
            if choice.field == field_key:
                kept = tuple(a for a in choice.alternatives if a.column != column_index)
                if choice.column not in (None, column_index) and choice.confidence is not None:
                    kept = (*kept, Alternative(choice.column, choice.confidence))
                choice = replace(
                    choice,
                    column=column_index,
                    confidence=Confidence.HIGH,
                    reasons=(Reason(ReasonCode.SET_BY_CALLER),),
                    alternatives=kept,
                )
            elif choice.column == column_index and choice.confidence is not None:
                lost = choice.confidence
                choice = replace(
                    choice,
                    column=None,
                    confidence=None,
                    reasons=(Reason(ReasonCode.SET_BY_CALLER, {"displaced_by": field_key}),),
                    alternatives=(*choice.alternatives, Alternative(column_index, lost)),
                )
            choices.append(choice)
        freed = {previous.column} - {None, column_index}
        return self._rebuilt(choices, freed)

    def unassign(self, field_key: str) -> Mapping:
        """Take the column away from a field, as the caller decided.

        The choice has no column and the reason ``set_by_caller``, and the column
        goes to ``unmapped``.

        Raises:
            ValueError: if no choice has the key.
        """
        previous = self._choice(field_key)
        choices = [
            replace(
                choice,
                column=None,
                confidence=None,
                reasons=(Reason(ReasonCode.SET_BY_CALLER),),
            )
            if choice.field == field_key
            else choice
            for choice in self.choices
        ]
        freed = {previous.column} - {None}
        return self._rebuilt(choices, freed)

    def _choice(self, field_key: str) -> Choice:
        for choice in self.choices:
            if choice.field == field_key:
                return choice
        raise ValueError(f"no field with the key {field_key!r}")

    def _columns(self) -> set[int]:
        assigned = {choice.column for choice in self.choices if choice.column is not None}
        return assigned | set(self.unmapped)

    def _rebuilt(self, choices: list[Choice], freed: set[int | None]) -> Mapping:
        assigned = {choice.column for choice in choices if choice.column is not None}
        unmapped = sorted((set(self.unmapped) | {c for c in freed if c is not None}) - assigned)
        return Mapping(tuple(choices), tuple(unmapped), self.fingerprint)
