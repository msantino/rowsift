"""Text, name, boolean and category cleaners."""

from __future__ import annotations

import re

from rowsift.clean._common import change, fail, fold
from rowsift.clean._options import CleanOptions
from rowsift.types import ChangeCode, Cleaned, IssueCode

__all__ = ["boolean", "category", "name", "text"]

_PARTICLES = frozenset({"da", "de", "do", "das", "dos", "e"})
_TRUE_WORDS = frozenset({"sim", "s", "yes", "y", "true", "t", "1", "verdadeiro"})
_FALSE_WORDS = frozenset({"nao", "n", "no", "false", "f", "0", "falso"})
_WORD_START = re.compile(r"(^|[-'\u2019])([^\W\d_])")


def text(value: str, options: CleanOptions | None = None) -> Cleaned[str]:
    """Free text, trimmed.

    Returns no value for an empty or whitespace-only input. Interior
    whitespace is kept as written.
    """
    stripped = value.strip()
    return Cleaned(stripped) if stripped else Cleaned()


def _capitalize(word: str) -> str:
    return _WORD_START.sub(lambda m: m.group(1) + m.group(2).upper(), word.lower())


def _same_letters(recased: str, original: str) -> bool:
    """Recasing must not change the letters: ``ß`` to ``SS`` is not a case change."""
    return len(recased) == len(original) and recased.casefold() == original.casefold()


def name(value: str, options: CleanOptions | None = None) -> Cleaned[str]:
    """A person's name with whitespace collapsed.

    With ``name_case="title"`` (the default) a name written entirely in
    uppercase or entirely in lowercase is recased, keeping the particles
    ``da``, ``de``, ``do``, ``das``, ``dos`` and ``e`` in lowercase after the
    first word, and the change ``case_changed`` is reported. A name in mixed
    case is kept as written, and so is a name whose recasing would change the
    letters, such as ``ß``.
    """
    options = options or CleanOptions()
    words = value.split()
    if not words:
        return Cleaned()
    collapsed = " ".join(words)
    letters = [char for char in collapsed if char.isalpha()]
    single_case = bool(letters) and (collapsed.isupper() or collapsed.islower())
    if options.name_case != "title" or not single_case:
        return Cleaned(collapsed)
    recased = " ".join(
        word.lower() if index and word.lower() in _PARTICLES else _capitalize(word)
        for index, word in enumerate(words)
    )
    if recased == collapsed or not _same_letters(recased, collapsed):
        return Cleaned(collapsed)
    return Cleaned(recased, changes=(change(ChangeCode.CASE_CHANGED),))


def boolean(value: str, options: CleanOptions | None = None) -> Cleaned[bool]:
    """A yes or no.

    True words: ``sim``, ``s``, ``yes``, ``y``, ``true``, ``t``, ``1``,
    ``verdadeiro``. False words: ``nao``, ``n``, ``no``, ``false``, ``f``,
    ``0``, ``falso``. Case and accents are ignored, and only ASCII digits
    count. Anything else is the issue ``not_a_boolean``.
    """
    stripped = value.strip()
    if not stripped:
        return Cleaned()
    word = fold(stripped, compatibility=False)
    if word in _TRUE_WORDS:
        return Cleaned(True)
    if word in _FALSE_WORDS:
        return Cleaned(False)
    return fail(IssueCode.NOT_A_BOOLEAN)


def category(value: str, options: CleanOptions | None = None) -> Cleaned[str]:
    """One of the allowed values, in its declared spelling.

    Matching ignores case, accents and repeated whitespace. A value that
    matches no entry of ``options.one_of`` is the issue
    ``not_in_allowed_values``. Without ``one_of`` any text is accepted, trimmed.
    """
    options = options or CleanOptions()
    stripped = value.strip()
    if not stripped:
        return Cleaned()
    if options.one_of is None:
        return Cleaned(stripped)
    wanted = fold(stripped)
    for allowed in options.one_of:
        if fold(allowed) == wanted:
            return Cleaned(allowed)
    return fail(IssueCode.NOT_IN_ALLOWED_VALUES)
