"""Fail when a release tag does not match the version in pyproject.toml.

Usage: check_release_tag.py TAG [PYPROJECT]

The tag is ``v`` followed by the version, for example ``v0.2.0``. The release
workflow runs this before it builds, so a tag on the wrong commit never
publishes.
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

TAG = re.compile(r"v(\d+\.\d+\.\d+(?:(?:a|b|rc)\d+)?)")


def main(argv: list[str]) -> int:
    if len(argv) not in (2, 3):
        print("usage: check_release_tag.py TAG [PYPROJECT]", file=sys.stderr)
        return 2
    tag = argv[1]
    pyproject = Path(argv[2]) if len(argv) == 3 else Path("pyproject.toml")
    match = TAG.fullmatch(tag)
    if match is None:
        print(f"{tag!r} is not a version tag such as v0.2.0", file=sys.stderr)
        return 1
    version = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["version"]
    if match.group(1) != version:
        print(f"tag {tag} does not match the package version {version}", file=sys.stderr)
        return 1
    print(f"tag {tag} matches version {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
