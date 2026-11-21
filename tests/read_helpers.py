"""Helpers shared by the reading tests."""

from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures" / "reading"


def fixture(folder: str, name: str) -> bytes:
    """The bytes of one reading fixture."""
    return (FIXTURES / folder / name).read_bytes()
