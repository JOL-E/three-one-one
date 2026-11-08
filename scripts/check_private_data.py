#!/usr/bin/env python3
"""Pre-commit guard: keep real data out of git (this repo goes public).

1. Blocks database and data-export files (.sqlite3, .db, .csv, ...) from being
   committed. Tests build their data inline instead.
2. Blocks files containing any string from `.private-denylist` (repo root,
   gitignored, one entry per line, case-insensitive): your domain, email,
   names, anything personal.

Usage (pre-commit passes the staged file names): check_private_data.py FILE...
"""

import sys
from pathlib import Path

BLOCKED_EXTENSIONS = {".sqlite3", ".sqlite", ".db", ".csv", ".tsv", ".xlsx", ".xls"}
DENYLIST = Path(__file__).resolve().parent.parent / ".private-denylist"


def load_denylist() -> list[str]:
    if not DENYLIST.exists():
        return []
    lines = DENYLIST.read_text(encoding="utf-8").splitlines()
    return [
        line.strip().lower()
        for line in lines
        if line.strip() and not line.startswith("#")
    ]


def main(paths: list[str]) -> int:
    denied = load_denylist()
    problems = []
    for name in paths:
        path = Path(name)
        if path.suffix.lower() in BLOCKED_EXTENSIONS:
            problems.append(f"{name}: data file type ({path.suffix}), don't commit it")
            continue
        if path.name == DENYLIST.name or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8").lower()
        except UnicodeDecodeError:
            continue  # binary file
        # Report only the line number, never the matched value (keeps it out of logs).
        for entry in denied:
            if entry in text:
                line_no = text[: text.index(entry)].count("\n") + 1
                problems.append(
                    f"{name}:{line_no}: contains an entry from .private-denylist"
                )
    if problems:
        print("Private-data check failed:", *problems, sep="\n  ")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
