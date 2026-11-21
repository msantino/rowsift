"""Phone cleaner: native rules for Brazil, the ``phone`` extra for other regions."""

from __future__ import annotations

import importlib
import re
from typing import Any

from rowsift.clean._common import change, fail
from rowsift.clean._options import CleanOptions
from rowsift.errors import MissingExtraError
from rowsift.types import Change, ChangeCode, Cleaned, Issue, IssueCode, LineType

__all__ = ["PhoneNumber", "phone"]

_AREA_CODE_LIST = (
    "11 12 13 14 15 16 17 18 19 21 22 24 27 28 31 32 33 34 35 37 38 "
    "41 42 43 44 45 46 47 48 49 51 53 54 55 61 62 63 64 65 66 67 68 69 "
    "71 73 74 75 77 79 81 82 83 84 85 86 87 88 89 91 92 93 94 95 96 97 98 99"
)
_AREA_CODES = frozenset(int(code) for code in _AREA_CODE_LIST.split())
_COUNTRY_CODE = "55"
_MIN_NUMBER_DIGITS = 8
_SPLIT = re.compile(r"\s*[/;|,\n\r]\s*|\s+(?:ou|e|or|and)\s+", re.IGNORECASE)
_FORMATTING = re.compile(r"[\s().\-+]")


class PhoneNumber(str):
    """A phone number in E.164 form, which is also a ``str``.

    It compares, hashes and serializes as the E.164 text. ``line_type`` says
    whether the number is a mobile or a landline, or is ``None`` when the
    ``phone`` extra cannot tell.
    """

    __slots__ = ("_line_type",)
    _line_type: LineType | None

    def __new__(cls, e164: str, line_type: LineType | None) -> PhoneNumber:
        instance = super().__new__(cls, e164)
        instance._line_type = line_type
        return instance

    @property
    def line_type(self) -> LineType | None:
        """Mobile or landline."""
        return self._line_type

    def __reduce__(self) -> tuple[Any, tuple[Any, ...]]:
        return (type(self), (str(self), self._line_type))

    def __repr__(self) -> str:
        return f"PhoneNumber({str(self)!r}, {self._line_type!r})"


def _brazil(segment: str, options: CleanOptions) -> tuple[PhoneNumber, tuple[Change, ...]] | Issue:
    plus = segment.lstrip().startswith("+")
    digits = _FORMATTING.sub("", segment)
    if not (digits.isascii() and digits.isdigit()):
        return Issue(IssueCode.INVALID_PHONE)
    if digits.startswith("0055") and len(digits) in (14, 15):
        digits = digits[2:]
    if plus:
        if not digits.startswith(_COUNTRY_CODE):
            return Issue(IssueCode.INVALID_PHONE)
        digits = digits[2:]
    elif digits.startswith(_COUNTRY_CODE) and len(digits) in (12, 13):
        digits = digits[2:]
    if digits[:1] == "0" and digits[1:2] != "0" and len(digits) in (11, 12):
        digits = digits[1:]  # the trunk prefix some people write before the area code
    count = len(digits)
    if count > 11:
        return Issue(IssueCode.INVALID_PHONE)
    if count < 10:
        return Issue(IssueCode.TOO_SHORT, {"digits": count})
    if int(digits[:2]) not in _AREA_CODES:
        return Issue(IssueCode.INVALID_AREA_CODE)
    area, subscriber = digits[:2], digits[2:]
    changes: tuple[Change, ...] = ()
    if count == 11:
        if subscriber[0] != "9":
            return Issue(IssueCode.INVALID_PHONE)
        line_type = LineType.MOBILE
    elif subscriber[0] in "2345":
        line_type = LineType.LANDLINE
    elif subscriber[0] in "678":
        if not options.insert_ninth_digit:
            return Issue(IssueCode.TOO_SHORT, {"digits": count})
        subscriber = "9" + subscriber
        changes = (change(ChangeCode.NINTH_DIGIT_INSERTED),)
        line_type = LineType.MOBILE
    elif subscriber[0] == "9":
        # Nine digits start with 9: this is a mobile missing its last digit.
        return Issue(IssueCode.TRUNCATED, {"digits": count})
    else:
        return Issue(IssueCode.INVALID_PHONE)
    if options.require_mobile and line_type is not LineType.MOBILE:
        return Issue(IssueCode.NOT_MOBILE)
    return PhoneNumber(f"+{_COUNTRY_CODE}{area}{subscriber}", line_type), changes


def _load_library() -> Any:
    try:
        return importlib.import_module("phonenumbers")
    except ImportError:
        raise MissingExtraError("phone") from None


def _elsewhere(
    segment: str, options: CleanOptions
) -> tuple[PhoneNumber, tuple[Change, ...]] | Issue:
    library = _load_library()
    try:
        parsed = library.parse(segment, options.region)
    except library.NumberParseException:
        return Issue(IssueCode.INVALID_PHONE)
    if not library.is_valid_number(parsed):
        return Issue(IssueCode.INVALID_PHONE)
    kind = library.number_type(parsed)
    line_type: LineType | None = None
    if kind == library.PhoneNumberType.MOBILE:
        line_type = LineType.MOBILE
    elif kind == library.PhoneNumberType.FIXED_LINE:
        line_type = LineType.LANDLINE
    if options.require_mobile and line_type is not LineType.MOBILE:
        return Issue(IssueCode.NOT_MOBILE)
    e164 = library.format_number(parsed, library.PhoneNumberFormat.E164)
    return PhoneNumber(e164, line_type), ()


def phone(value: str, options: CleanOptions | None = None) -> Cleaned[PhoneNumber]:
    """A phone number in E.164 form.

    With region ``BR`` (the default) the rules are native: formatting and an
    optional country code (``+55``, ``55``, ``0055``) and trunk zero are
    removed, the area code must be one of the national list, and the number is
    classified as mobile (11 digits, or 10 digits whose subscriber part starts
    with 6, 7 or 8) or landline (starts with 2 to 5). A mobile written with 8
    subscriber digits gets the ninth digit when ``options.insert_ninth_digit``
    is true, reported as ``ninth_digit_inserted``. A number is never completed
    otherwise: a 10-digit number whose subscriber part starts with 9 is the
    issue ``truncated``, fewer than 10 digits is ``too_short`` (so is an 8-digit mobile pattern when
    ``insert_ninth_digit`` is false), an unknown area code is
    ``invalid_area_code``, a landline with ``require_mobile`` is
    ``not_mobile``, and any other shape (letters, scientific notation, a
    foreign country code, too many digits) is ``invalid_phone``.

    Several numbers in one cell, separated by ``/``, ``;``, ``|``, ``,``, a line
    break or the words ``ou`` and ``e``, give the first valid one and the change
    ``multiple_values`` with the count of fragments that have at least 8 digits
    (an extension such as ``ramal 12`` after a separator is not counted). An
    extension written in the same fragment as the number, as in
    ``(11) 99999-0042 ramal 12``, is the issue ``invalid_phone``. If none is
    valid the issue is the first number's.

    The result's value is a ``str`` with a ``line_type`` attribute. For another
    region the ``phone`` extra is used, and ``MissingExtraError`` is raised when
    it is not installed.

    Raises:
        MissingExtraError: for a region other than ``BR`` without the extra,
            whatever the cell holds.
    """
    options = options or CleanOptions()
    if options.region != "BR":
        _load_library()  # fail on a missing extra whatever the cell holds
    candidates = [part for part in _SPLIT.split(value) if any(c.isdigit() for c in part)]
    if not candidates:
        if not value.strip():
            return Cleaned()
        return fail(IssueCode.INVALID_PHONE)
    # Only a fragment with enough digits to be a number counts: "ramal 12" does not.
    count = sum(sum(c.isdigit() for c in part) >= _MIN_NUMBER_DIGITS for part in candidates)
    clean_one = _brazil if options.region == "BR" else _elsewhere
    first_issue: Issue | None = None
    for candidate in candidates:
        outcome = clean_one(candidate, options)
        if isinstance(outcome, Issue):
            first_issue = first_issue or outcome
            continue
        number, changes = outcome
        if count > 1:
            changes = (*changes, change(ChangeCode.MULTIPLE_VALUES, count=count))
        return Cleaned(number, changes=changes)
    return Cleaned(issue=first_issue)
