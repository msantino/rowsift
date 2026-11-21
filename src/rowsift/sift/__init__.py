"""Sift: apply a mapping to a table and get typed rows, rejections and counts.

``sift`` cleans every data row with the kind of each mapped field. It keeps the
rows whose required fields are good, lists the others as rejections with the
issue code, and counts every outcome. It has no side effect, so a caller can
run it as a preview and again as the final pass.
"""

from rowsift.sift._sift import sift
from rowsift.sift._types import FieldSummary, Rejection, SiftedRow, SiftResult, Summary

__all__ = [
    "FieldSummary",
    "Rejection",
    "SiftResult",
    "SiftedRow",
    "Summary",
    "sift",
]
