"""Masking of values meant for display.

Every function takes the text as written and returns text that is safe to show.
A value that does not have the shape its kind expects is hidden entirely: the
functions fail closed, so a note, an e-mail or a number typed into the wrong
column does not leak.
"""

from __future__ import annotations

import re

from rowsift.types import Kind

__all__ = ["mask", "mask_cnpj", "mask_cpf", "mask_email", "mask_name", "mask_phone"]

_PARTICLES = frozenset({"da", "de", "do", "das", "dos", "e"})
_TAX_ID_SHAPE = re.compile(r"[0-9.\-/\s]+")
_KEPT_TAX_DIGITS = 2
_NAME_PUNCTUATION = frozenset(" .'\u2019-")


def _hide(text: str) -> str:
    return "".join("*" if char.isalnum() else char for char in text)


def mask_phone(text: str) -> str:
    """Keep the area code and the last 2 digits of a Brazilian phone number.

    ``(11) 99999-0042`` becomes ``11 *******42``. A value that does not hold a
    10 or 11 digit number, after an optional country code, is hidden entirely.
    """
    digits = "".join(char for char in text if char in "0123456789")
    if text.lstrip().startswith("+") and not digits.startswith("55"):
        return _hide(text)  # another country: the leading digits are no Brazilian area code
    if digits.startswith("55") and len(digits) in (12, 13):
        digits = digits[2:]
    letters = any(char.isalpha() for char in text)
    if letters or len(digits) not in (10, 11):
        return _hide(text)
    return f"{digits[:2]} {'*' * (len(digits) - 4)}{digits[-2:]}"


def _mask_tax_id(text: str) -> str:
    if not _TAX_ID_SHAPE.fullmatch(text):
        return _hide(text)
    total = sum(char in "0123456789" for char in text)
    seen = 0
    out: list[str] = []
    for char in text:
        if char in "0123456789":
            seen += 1
            out.append(char if seen > total - _KEPT_TAX_DIGITS else "*")
        else:
            out.append(char)
    return "".join(out)


def mask_cpf(text: str) -> str:
    """Keep the last 2 digits of a CPF and its punctuation: ``***.***.***-09``."""
    return _mask_tax_id(text)


def mask_cnpj(text: str) -> str:
    """Keep the last 2 digits of a CNPJ and its punctuation."""
    return _mask_tax_id(text)


def mask_email(text: str) -> str:
    """Keep the first character of the local part and the domain: ``a***@example.com``.

    A value that is not of the form ``local@domain`` is hidden entirely.
    """
    local, at, domain = text.strip().partition("@")
    if at != "@" or not local or not domain or "@" in domain or any(c.isspace() for c in text):
        return _hide(text)
    return f"{local[0]}***@{domain}"


def mask_name(text: str) -> str:
    """Keep the first name and the initials of the rest: ``Helena P. A.``.

    The particles ``da``, ``de``, ``do``, ``das``, ``dos`` and ``e`` are dropped
    from the initials. A value with a character other than letters, spaces,
    dots, apostrophes and hyphens (a digit, an ``@``, a colon) is not a name and
    is hidden entirely.
    """
    words = text.split()
    if not words:
        return text
    if not all(char.isalpha() or char in _NAME_PUNCTUATION for char in text):
        return _hide(text)
    initials = [f"{word[0].upper()}." for word in words[1:] if word.lower() not in _PARTICLES]
    return " ".join([words[0], *initials])


def mask(text: str, kind: Kind) -> str:
    """Mask a value according to its kind.

    Phones, CPFs, CNPJs, e-mails and names are masked by the rules of
    ``mask_phone``, ``mask_cpf``, ``mask_cnpj``, ``mask_email`` and
    ``mask_name``. Every other kind has no masking rule and is returned as
    written.
    """
    match kind:
        case Kind.PHONE:
            return mask_phone(text)
        case Kind.CPF:
            return mask_cpf(text)
        case Kind.CNPJ:
            return mask_cnpj(text)
        case Kind.EMAIL:
            return mask_email(text)
        case Kind.NAME:
            return mask_name(text)
        case _:
            return text
