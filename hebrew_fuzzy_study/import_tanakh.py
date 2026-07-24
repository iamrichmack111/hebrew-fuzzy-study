#!/usr/bin/env python3
"""
Download/import a public-domain Hebrew Tanakh (WLC via Open Scriptures)
and the public-domain JPS 1917 English Tanakh from eBible.org.

Hebrew WLC text: Public Domain.
Open Scriptures lemma/morphology annotations: CC BY 4.0.
JPS 1917 English: Public Domain.

The importer stores source/license metadata in SQLite.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unicodedata
import urllib.request
import zipfile
from pathlib import Path
import xml.etree.ElementTree as ET

APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "hebrew.db"

HEBREW_REPO = "https://github.com/openscriptures/morphhb.git"
HEBREW_TAG = "v.2.2"
ENGLISH_ZIP = "https://ebible.org/Scriptures/engjps_vpl.zip"

BOOKS = {
    "Gen": "Genesis", "Exod": "Exodus", "Lev": "Leviticus", "Num": "Numbers",
    "Deut": "Deuteronomy", "Josh": "Joshua", "Judg": "Judges", "Ruth": "Ruth",
    "1Sam": "1 Samuel", "2Sam": "2 Samuel", "1Kgs": "1 Kings", "2Kgs": "2 Kings",
    "1Chr": "1 Chronicles", "2Chr": "2 Chronicles", "Ezra": "Ezra", "Neh": "Nehemiah",
    "Esth": "Esther", "Job": "Job", "Ps": "Psalms", "Prov": "Proverbs",
    "Eccl": "Ecclesiastes", "Song": "Song of Solomon", "Isa": "Isaiah",
    "Jer": "Jeremiah", "Lam": "Lamentations", "Ezek": "Ezekiel", "Dan": "Daniel",
    "Hos": "Hosea", "Joel": "Joel", "Amos": "Amos", "Obad": "Obadiah",
    "Jonah": "Jonah", "Mic": "Micah", "Nah": "Nahum", "Hab": "Habakkuk",
    "Zeph": "Zephaniah", "Hag": "Haggai", "Zech": "Zechariah", "Mal": "Malachi",
}
ALIASES = {
    "GEN":"Gen","EXO":"Exod","EXOD":"Exod","LEV":"Lev","NUM":"Num","DEU":"Deut","DEUT":"Deut",
    "JOS":"Josh","JOSH":"Josh","JDG":"Judg","JUDG":"Judg","RUT":"Ruth","RUTH":"Ruth",
    "1SA":"1Sam","1SAM":"1Sam","2SA":"2Sam","2SAM":"2Sam",
    "1KI":"1Kgs","1KGS":"1Kgs","2KI":"2Kgs","2KGS":"2Kgs",
    "1CH":"1Chr","1CHR":"1Chr","2CH":"2Chr","2CHR":"2Chr",
    "EZR":"Ezra","NEH":"Neh","EST":"Esth","ESTH":"Esth","JOB":"Job",
    "PSA":"Ps","PS":"Ps","PRO":"Prov","PROV":"Prov","ECC":"Eccl","ECCl":"Eccl",
    "SNG":"Song","SONG":"Song","ISA":"Isa","JER":"Jer","LAM":"Lam","EZK":"Ezek","EZE":"Ezek",
    "DAN":"Dan","HOS":"Hos","JOL":"Joel","JOE":"Joel","AMO":"Amos","OBA":"Obad",
    "JON":"Jonah","MIC":"Mic","NAM":"Nah","NAH":"Nah","HAB":"Hab","ZEP":"Zeph",
    "HAG":"Hag","ZEC":"Zech","MAL":"Mal",
}
for code in BOOKS:
    ALIASES[code.upper()] = code

def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]

def norm_hebrew(text: str) -> str:
    text = unicodedata.normalize("NFD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch) and ch not in "־׃")
    return re.sub(r"\s+", " ", text).strip()

def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS verses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        book TEXT NOT NULL, book_code TEXT NOT NULL,
        chapter INTEGER NOT NULL, verse INTEGER NOT NULL,
        reference TEXT NOT NULL, hebrew TEXT NOT NULL DEFAULT '',
        hebrew_norm TEXT NOT NULL DEFAULT '', english TEXT NOT NULL DEFAULT '',
        UNIQUE(book_code,chapter,verse)
    );
    CREATE INDEX IF NOT EXISTS idx_verses_ref ON verses(book_code,chapter,verse);
    CREATE INDEX IF NOT EXISTS idx_verses_hebrew_norm ON verses(hebrew_norm);
    CREATE VIRTUAL TABLE IF NOT EXISTS verses_fts USING fts5(
        reference, english, content='verses', content_rowid='id'
    );
    CREATE TABLE IF NOT EXISTS sources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_key TEXT UNIQUE NOT NULL, title TEXT NOT NULL,
        url TEXT NOT NULL, license TEXT NOT NULL,
        imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """)

def hebrew_from_xml(path: Path):
    tree = ET.parse(path)
    root = tree.getroot()
    for verse in root.iter():
        if local_name(verse.tag) != "verse":
            continue
        osis = verse.attrib.get("osisID") or verse.attrib.get("sID")
        if not osis or osis.count(".") < 2:
            continue
        parts = osis.split(".")
        code = parts[0]
        try:
            chapter, number = int(parts[1]), int(parts[2])
        except ValueError:
            continue
        if code not in BOOKS:
            continue
        tokens = []
        for node in verse.iter():
            lname = local_name(node.tag)
            if lname in {"w", "seg"} and node.text:
                tokens.append(node.text.strip())
        text = " ".join(t for t in tokens if t)
        if text:
            yield code, chapter, number, text

def import_hebrew(conn: sqlite3.Connection, repo: Path) -> int:
    count = 0
    for xml in sorted((repo / "wlc").glob("*.xml")):
        for code, ch, vs, text in hebrew_from_xml(xml):
            book = BOOKS[code]
            ref = f"{book} {ch}:{vs}"
            conn.execute("""
                INSERT INTO verses(book,book_code,chapter,verse,reference,hebrew,hebrew_norm)
                VALUES(?,?,?,?,?,?,?)
                ON CONFLICT(book_code,chapter,verse) DO UPDATE SET
                  book=excluded.book, reference=excluded.reference,
                  hebrew=excluded.hebrew, hebrew_norm=excluded.hebrew_norm
            """, (book, code, ch, vs, ref, text, norm_hebrew(text)))
            count += 1
    return count

def parse_vpl_line(line: str):
    line = line.strip().lstrip("\ufeff")
    if not line:
        return None
    patterns = [
        r"^([123]?[A-Za-z]+)\s+(\d+):(\d+)\s+(.+)$",
        r"^([123]?[A-Za-z]+)[.\s]+(\d+)[.:](\d+)\s+(.+)$",
        r"^([123]?[A-Za-z]{2,5})\s+(\d+)\s+(\d+)\s+(.+)$",
    ]
    for pat in patterns:
        m = re.match(pat, line)
        if m:
            raw, ch, vs, text = m.groups()
            code = ALIASES.get(raw.upper())
            if code:
                return code, int(ch), int(vs), text.strip()
    return None

def find_text_files(folder: Path):
    for p in folder.rglob("*"):
        if p.is_file() and p.suffix.lower() in {".txt", ".vpl", ".csv"}:
            yield p

def import_english(conn: sqlite3.Connection, folder: Path) -> int:
    count = 0
    seen = set()
    for p in find_text_files(folder):
        try:
            text = p.read_text(encoding="utf-8-sig", errors="replace")
        except Exception:
            continue
        for line in text.splitlines():
            parsed = parse_vpl_line(line)
            if not parsed:
                continue
            code, ch, vs, english = parsed
            key = (code, ch, vs)
            if key in seen:
                continue
            seen.add(key)
            book = BOOKS[code]
            ref = f"{book} {ch}:{vs}"
            conn.execute("""
                INSERT INTO verses(book,book_code,chapter,verse,reference,english)
                VALUES(?,?,?,?,?,?)
                ON CONFLICT(book_code,chapter,verse) DO UPDATE SET
                  book=excluded.book, reference=excluded.reference, english=excluded.english
            """, (book, code, ch, vs, ref, english))
            count += 1
    return count

def rebuild_fts(conn: sqlite3.Connection) -> None:
    try:
        conn.execute("INSERT INTO verses_fts(verses_fts) VALUES('rebuild')")
    except sqlite3.OperationalError:
        pass

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(DB_PATH))
    ap.add_argument("--keep-downloads", action="store_true")
    args = ap.parse_args()

    db = Path(args.db).expanduser().resolve()
    if not db.exists():
        print(f"Database not found: {db}", file=sys.stderr)
        return 2
    if not shutil.which("git"):
        print("git is required. On macOS: xcode-select --install", file=sys.stderr)
        return 2

    work = Path(tempfile.mkdtemp(prefix="hebrew-fuzzy-tanakh-"))
    try:
        repo = work / "morphhb"
        print("Downloading Open Scriptures Hebrew Bible (WLC)...")
        subprocess.run([
            "git", "clone", "--depth", "1", "--branch", HEBREW_TAG,
            HEBREW_REPO, str(repo)
        ], check=True)

        engzip = work / "engjps_vpl.zip"
        print("Loading bundled JPS 1917 English Tanakh...")

        bundled_jps = Path(__file__).resolve().parent / "data" / "engjps_vpl.zip"
        if not bundled_jps.exists():
            raise FileNotFoundError(
                f"Bundled JPS archive not found: {bundled_jps}"
            )

        shutil.copy2(bundled_jps, engzip)

        engdir = work / "engjps"
        engdir.mkdir()
        with zipfile.ZipFile(engzip) as zf:
            zf.extractall(engdir)

        conn = sqlite3.connect(db)
        ensure_schema(conn)
        print("Importing Hebrew verses...")
        h = import_hebrew(conn, repo)
        print("Importing English verses...")
        e = import_english(conn, engdir)

        conn.execute("""
            INSERT INTO sources(source_key,title,url,license)
            VALUES('oshb-wlc','Westminster Leningrad Codex via Open Scriptures',?,'WLC text: Public Domain; OSHB annotations: CC BY 4.0')
            ON CONFLICT(source_key) DO UPDATE SET imported_at=CURRENT_TIMESTAMP
        """, (HEBREW_REPO,))
        conn.execute("""
            INSERT INTO sources(source_key,title,url,license)
            VALUES('jps1917','JPS Tanakh 1917 via eBible.org',?,'Public Domain')
            ON CONFLICT(source_key) DO UPDATE SET imported_at=CURRENT_TIMESTAMP
        """, (ENGLISH_ZIP,))
        rebuild_fts(conn)
        conn.commit()

        total = conn.execute("SELECT count(*) FROM verses").fetchone()[0]
        both = conn.execute(
            "SELECT count(*) FROM verses WHERE hebrew<>'' AND english<>''"
        ).fetchone()[0]
        conn.close()

        print(f"Hebrew verse rows processed: {h}")
        print(f"English verse rows processed: {e}")
        print(f"Verses in database: {total}")
        print(f"Rows with both Hebrew + English: {both}")
        if both < 20000:
            print(
                "WARNING: Alignment count is lower than expected. "
                "Hebrew/English versification differs in some passages; "
                "the app preserves source references rather than inventing alignments.",
                file=sys.stderr,
            )
        print("Tanakh import complete.")
        return 0
    finally:
        if args.keep_downloads:
            print(f"Kept downloads at: {work}")
        else:
            shutil.rmtree(work, ignore_errors=True)

if __name__ == "__main__":
    raise SystemExit(main())
