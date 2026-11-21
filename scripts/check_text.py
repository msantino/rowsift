"""Fail when a tracked text file contains the em dash character.

The project writes plain sentences: commas, colons and lists instead of an
aside set off by a dash. The check covers every tracked file git treats as
text, so it holds for code, tests, fixtures and docs alike.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

EM_DASH = chr(0x2014)


def tracked_files() -> list[Path]:
    listing = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        check=True,
        capture_output=True,
    ).stdout
    return [Path(name) for name in listing.decode().split("\0") if name]


def main() -> int:
    offenders: list[str] = []
    for path in tracked_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError, IsADirectoryError):
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            if EM_DASH in line:
                offenders.append(f"{path}:{number}")
    if offenders:
        print("em dash found:\n  " + "\n  ".join(offenders), file=sys.stderr)
        return 1
    print("text check: clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
