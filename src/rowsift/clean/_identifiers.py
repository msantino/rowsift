"""CPF, CNPJ, postal code and e-mail cleaners."""

from __future__ import annotations

import re
from collections.abc import Callable

from rowsift.clean._common import change, fail
from rowsift.clean._options import CleanOptions
from rowsift.types import ChangeCode, Cleaned, IssueCode

__all__ = ["cnpj", "cpf", "email", "postal_code"]

_FORMATTED_DIGITS = re.compile(r"[0-9.\-/\s]+")
_ASCII_DIGITS = "0123456789"
_CPF_LENGTH = 11
_CNPJ_LENGTH = 14
_CPF_MIN_DIGITS = 9  # at most two leading zeros are restored
_CNPJ_MIN_DIGITS = 12
_POSTAL_LENGTH = 8
_POSTAL_MIN_DIGITS = 7  # at most one leading zero is restored
_CPF_WEIGHTS = (10, 9, 8, 7, 6, 5, 4, 3, 2)
_CNPJ_WEIGHTS = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
_EMAIL_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?")
_EMAIL_MAX_LENGTH = 254
_EMAIL_MAX_LOCAL = 64
_EMAIL_MAX_LABEL = 63


def _check_digit(digits: str, weights: tuple[int, ...]) -> str:
    total = sum(int(d) * w for d, w in zip(digits, weights, strict=True))
    remainder = total % 11
    return str(0 if remainder < 2 else 11 - remainder)


def _valid_cpf(digits: str) -> bool:
    if len(set(digits)) == 1:
        return False
    first = _check_digit(digits[:9], _CPF_WEIGHTS)
    second = _check_digit(digits[:9] + first, (11, *_CPF_WEIGHTS))
    return digits[9:] == first + second


def _valid_cnpj(digits: str) -> bool:
    if len(set(digits)) == 1:
        return False
    first = _check_digit(digits[:12], _CNPJ_WEIGHTS)
    second = _check_digit(digits[:12] + first, (6, *_CNPJ_WEIGHTS))
    return digits[12:] == first + second


def _tax_id(value: str, length: int, minimum: int, valid: Callable[[str], bool]) -> Cleaned[str]:
    text = value.strip()
    if not text:
        return Cleaned()
    if not _FORMATTED_DIGITS.fullmatch(text):
        return fail(IssueCode.NOT_A_NUMBER)
    digits = "".join(char for char in text if char in _ASCII_DIGITS)
    if len(digits) > length or len(digits) < minimum:
        return fail(IssueCode.INVALID_LENGTH, digits=len(digits), expected=length)
    if len(digits) == length:
        if valid(digits):
            return Cleaned(digits)
        return fail(IssueCode.INVALID_CHECK_DIGIT)
    padded = digits.rjust(length, "0")
    if valid(padded):
        return Cleaned(padded, changes=(change(ChangeCode.LEADING_ZEROS_RESTORED),))
    return fail(IssueCode.INVALID_LENGTH, digits=len(digits), expected=length)


def cpf(value: str, options: CleanOptions | None = None) -> Cleaned[str]:
    """A CPF as its 11 digits.

    Dots, dashes and spaces are removed. The two check digits are verified and
    a sequence of one repeated digit is refused, both as the issue
    ``invalid_check_digit``. A value of 9 or 10 digits is padded with the
    leading zeros a spreadsheet drops, only when the padded value passes the
    check digits, and the change ``leading_zeros_restored`` is reported.
    Otherwise a wrong digit count is the issue ``invalid_length`` and any other
    character, including a digit of another script, is ``not_a_number``. Only the
    digits 0 to 9 are supported.
    """
    return _tax_id(value, _CPF_LENGTH, _CPF_MIN_DIGITS, _valid_cpf)


def cnpj(value: str, options: CleanOptions | None = None) -> Cleaned[str]:
    """A CNPJ as its 14 digits.

    Dots, dashes, slashes and spaces are removed. The two check digits are
    verified and a sequence of one repeated digit is refused, both as the issue
    ``invalid_check_digit``. A value of 12 or 13 digits is padded with the
    leading zeros a spreadsheet drops, only when the padded value passes the
    check digits, and the change ``leading_zeros_restored`` is reported.
    Otherwise a wrong digit count is the issue ``invalid_length`` and any other
    character, including a digit of another script, is ``not_a_number``. Only the
    digits 0 to 9 are supported.
    """
    return _tax_id(value, _CNPJ_LENGTH, _CNPJ_MIN_DIGITS, _valid_cnpj)


def postal_code(value: str, options: CleanOptions | None = None) -> Cleaned[str]:
    """A Brazilian postal code (CEP) as its 8 digits.

    A dash, dots and spaces are removed. A 7-digit value is padded with the
    leading zero a spreadsheet drops and the change ``leading_zeros_restored``
    is reported. Any other digit count is the issue ``invalid_length`` and any
    other character is ``not_a_number``.

    Raises:
        ValueError: if ``options.region`` is not ``BR``, the only region with
            native rules.
    """
    options = options or CleanOptions()
    if options.region != "BR":
        raise ValueError("postal codes have native rules for region BR only")
    text = value.strip()
    if not text:
        return Cleaned()
    if not _FORMATTED_DIGITS.fullmatch(text):
        return fail(IssueCode.NOT_A_NUMBER)
    digits = "".join(char for char in text if char in _ASCII_DIGITS)
    if len(digits) == _POSTAL_LENGTH:
        return Cleaned(digits)
    if len(digits) == _POSTAL_MIN_DIGITS:
        return Cleaned(
            digits.rjust(_POSTAL_LENGTH, "0"),
            changes=(change(ChangeCode.LEADING_ZEROS_RESTORED),),
        )
    return fail(IssueCode.INVALID_LENGTH, digits=len(digits), expected=_POSTAL_LENGTH)


def email(value: str, options: CleanOptions | None = None) -> Cleaned[str]:
    """An e-mail address, trimmed, with the domain in lowercase.

    The address needs exactly one ``@``, a non-empty local part without spaces
    and a domain of at least two labels made of letters, digits and inner
    hyphens. The whole address has at most 254 characters, the local part 64
    and each label 63. A local part that starts or ends with a dot or holds two
    dots in a row is refused. Anything else is the issue ``invalid_email``. The
    local part is kept as written. Quoted local parts and internationalized domains are not
    supported and are refused.
    """
    text = value.strip()
    if not text:
        return Cleaned()
    local, at, domain = text.partition("@")
    domain = domain.lower()
    labels = domain.split(".")
    ok = (
        at == "@"
        and len(text) <= _EMAIL_MAX_LENGTH
        and 0 < len(local) <= _EMAIL_MAX_LOCAL
        and not (local.startswith(".") or local.endswith(".") or ".." in local)
        and not any(char.isspace() or char in '"@,;<>()' for char in local)
        and len(labels) >= 2  # a dotted domain
        and all(
            len(label) <= _EMAIL_MAX_LABEL and _EMAIL_LABEL.fullmatch(label) for label in labels
        )
        and not labels[-1].isdigit()
    )
    return Cleaned(f"{local}@{domain}") if ok else fail(IssueCode.INVALID_EMAIL)
