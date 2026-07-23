#!/usr/bin/env python3

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "hebrew.db"


def main() -> int:
    print("Hebrew Fuzzy Study Doctor")
    print("=" * 30)

    checks = []

    checks.append(("Python", sys.version.split()[0], sys.version_info >= (3, 11)))
    checks.append(("Database exists", str(DB_PATH), DB_PATH.exists()))

    if DB_PATH.exists():
        try:
            conn = sqlite3.connect(DB_PATH)

            words = conn.execute(
                "SELECT COUNT(*) FROM words"
            ).fetchone()[0]

            try:
                verses = conn.execute(
                    "SELECT COUNT(*) FROM verses"
                ).fetchone()[0]
            except sqlite3.OperationalError:
                verses = 0

            try:
                word_notes = conn.execute(
                    "SELECT COUNT(*) FROM word_notes"
                ).fetchone()[0]
            except sqlite3.OperationalError:
                word_notes = 0

            try:
                verse_notes = conn.execute(
                    "SELECT COUNT(*) FROM verse_notes"
                ).fetchone()[0]
            except sqlite3.OperationalError:
                verse_notes = 0

            conn.close()

            checks.append(("Dictionary entries", f"{words:,}", words >= 8000))
            checks.append(("Tanakh verses", f"{verses:,}", True))
            checks.append(("Word notes", str(word_notes), True))
            checks.append(("Verse notes", str(verse_notes), True))

        except sqlite3.Error as exc:
            checks.append(("SQLite", str(exc), False))

    failed = False

    for name, value, ok in checks:
        status = "PASS" if ok else "FAIL"
        print(f"{status:4}  {name:22} {value}")
        if not ok:
            failed = True

    print()

    if failed:
        print("Doctor found a problem.")
        return 1

    print("Core application checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
