"""Read a spreadsheet: bytes in, a grid of text cells and a report of how it was read out."""

from rowsift.read._limits import ReadLimits
from rowsift.read._read import read

__all__ = ["ReadLimits", "read"]
