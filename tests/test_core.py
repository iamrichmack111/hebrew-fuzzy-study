from pathlib import Path
import sqlite3

from hebrew_tui import normalize_hebrew, normalize_latin, SCHOLAR_TOPICS


def test_latin_normalization():
    assert normalize_latin("ʼĂbîyshag") == "abiyshag"


def test_hebrew_normalization_removes_points():
    assert normalize_hebrew("בְּרָכָה") == "ברכה"


def test_scholar_reference_present():
    required = {
        "prefixes",
        "suffixes",
        "transliteration",
        "morphology",
        "translation",
        "skopos",
        "textcritical",
        "sources",
    }

    assert required.issubset(SCHOLAR_TOPICS)


def test_dictionary_database_exists():
    db = Path(__file__).resolve().parents[1] / "hebrew.db"

    assert db.exists()


def test_dictionary_has_expected_entries():
    db = Path(__file__).resolve().parents[1] / "hebrew.db"

    conn = sqlite3.connect(db)

    count = conn.execute(
        "SELECT COUNT(*) FROM words"
    ).fetchone()[0]

    conn.close()

    assert count >= 8000


def test_notes_tables_exist():
    db = Path(__file__).resolve().parents[1] / "hebrew.db"

    conn = sqlite3.connect(db)

    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }

    conn.close()

    assert "word_notes" in tables
    assert "verse_notes" in tables
