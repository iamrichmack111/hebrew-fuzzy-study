#!/usr/bin/env python3
from __future__ import annotations

import csv
import itertools
import math
import re
import sqlite3
import unicodedata
from datetime import datetime
from pathlib import Path

from rapidfuzz import fuzz
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import (
    Button, DataTable, Footer, Header, Input, Label, Select,
    Static, TabbedContent, TabPane, TextArea
)

from .paths import database_path, export_dir

DB_PATH = database_path()
EXPORT_DIR = export_dir()

BOOKS = [
    ("Genesis", "Gen"), ("Exodus", "Exod"), ("Leviticus", "Lev"),
    ("Numbers", "Num"), ("Deuteronomy", "Deut"), ("Joshua", "Josh"),
    ("Judges", "Judg"), ("Ruth", "Ruth"), ("1 Samuel", "1Sam"),
    ("2 Samuel", "2Sam"), ("1 Kings", "1Kgs"), ("2 Kings", "2Kgs"),
    ("1 Chronicles", "1Chr"), ("2 Chronicles", "2Chr"), ("Ezra", "Ezra"),
    ("Nehemiah", "Neh"), ("Esther", "Esth"), ("Job", "Job"),
    ("Psalms", "Ps"), ("Proverbs", "Prov"), ("Ecclesiastes", "Eccl"),
    ("Song of Solomon", "Song"), ("Isaiah", "Isa"), ("Jeremiah", "Jer"),
    ("Lamentations", "Lam"), ("Ezekiel", "Ezek"), ("Daniel", "Dan"),
    ("Hosea", "Hos"), ("Joel", "Joel"), ("Amos", "Amos"),
    ("Obadiah", "Obad"), ("Jonah", "Jonah"), ("Micah", "Mic"),
    ("Nahum", "Nah"), ("Habakkuk", "Hab"), ("Zephaniah", "Zeph"),
    ("Haggai", "Hag"), ("Zechariah", "Zech"), ("Malachi", "Mal"),
]

def normalize_latin(value: str) -> str:
    value = (value or "").replace("ʼ", "'").replace("ʻ", "'").replace("ᵉ", "e")
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^a-zA-Z0-9]+", " ", value).lower()
    return re.sub(r"\s+", " ", value).strip()

def normalize_hebrew(value: str) -> str:
    value = unicodedata.normalize("NFD", value or "")
    value = "".join(
        ch for ch in value
        if not unicodedata.combining(ch) and ch not in "־׃"
    )
    return re.sub(r"\s+", " ", value).strip()


SCHOLAR_TOPICS = {
    "prefixes": """[b]Common Biblical Hebrew Prefixes[/b]

Hebrew frequently attaches short grammatical elements directly to the front of a word.

[b]ו־  wə-/û-/waw[/b]
Usually a conjunction: “and,” “but,” or a discourse connector. Its vocalization changes with phonological context.

[b]ב־  bə-/ba-[/b]
Preposition commonly expressing “in,” “at,” “by,” or “with.” The exact English rendering depends on context.

[b]כ־  kə-/ka-[/b]
Often “as,” “like,” or “according to.”

[b]ל־  lə-/la-[/b]
Often “to,” “for,” “toward,” or marks purpose/relationship.

[b]מ־  mi-/min[/b]
Often “from,” “out of,” or comparative “than.” Assimilation can affect the following consonant.

[b]ה־  ha-[/b]
Commonly the definite article “the.” A visually similar ה can also participate in other grammatical forms, so form must be analyzed in context.

[b]ש־[/b]
In later Biblical Hebrew and related usage, may function as a relative element “that/which.”

[b]Scholar caution[/b]
Do not mechanically remove an initial letter and assume it is a prefix. The same consonant may belong to the lexical root. Reliable analysis uses morphology, vocalization, syntax, and lexical evidence.
""",

    "suffixes": """[b]Common Biblical Hebrew Suffixes[/b]

Hebrew commonly attaches pronominal and inflectional information to the end of words.

[b]Pronominal suffixes[/b]
These can mark possession on nouns or objects on verbs/prepositions.

Typical values include:
־י      my / me
־ךָ     your (masculine singular)
־ךְ     your (feminine singular)
־וֹ     his / him
־הּ / ־ָהּ   her
־נוּ    our / us
־כֶם    your (masculine plural)
־כֶן    your (feminine plural)
־הֶם / ־ם   their / them (masculine)
־הֶן / ־ן   their / them (feminine)

[b]Nominal endings[/b]
־ים     commonly masculine plural
־ות     commonly feminine plural
־ה      often feminine singular, but not universally
־ת      may mark feminine forms or belong to the lexical form

[b]Verbal endings[/b]
Perfect/suffix-conjugation forms often encode person, gender, and number through endings such as ־תִּי, ־תָּ, ־תְּ, ־נוּ, ־תֶם, and others.

[b]Scholar caution[/b]
A suffix is not just “extra letters.” It can change grammatical person, possession, number, gender, or syntactic function. Proper parsing should be driven by morphology, not string chopping.
""",

    "transliteration": """[b]Transliteration Guide[/b]

Transliteration represents Hebrew with Latin characters. It is a scholarly convention, not the Hebrew text itself.

[b]Why systems differ[/b]
Different publishers distinguish Hebrew sounds and historical letters with different levels of precision. SBL provides both academic and general-purpose Hebrew transliteration systems.

Common conventions you may encounter:

ʾ or ʼ    א  aleph
ʿ or ʻ    ע  ayin
ḥ         ח  het in many academic systems
kh / ḵ    כ/ך without dagesh
sh / š    שׁ
s / ś     שׂ in systems that distinguish sin
ṣ / ts / tz  צ
q         ק in academic systems
k         כּ
ə / ǝ     vocal shewa in some academic systems

Strong's-style pronunciation fields such as:
  ber-aw-kaw'
are pronunciation aids, not modern academic transliteration.

A form such as:
  bərāḵâ
tries to preserve more linguistic information.

[b]Best practice[/b]
Always display the Hebrew script alongside transliteration, and identify which transliteration convention is being used.
""",

    "morphology": """[b]Roots, Stems, and Morphology[/b]

Many Biblical Hebrew words are discussed in relation to consonantal roots, often represented with three consonants.

Example:
  ברך  B-R-K

A root is not itself a complete translation. Related words can develop different senses, and the same root appears in different grammatical patterns.

[b]Binyanim / verbal stems[/b]
Common labels include:
qal
niphal
piel
pual
hiphil
hophal
hithpael

These patterns can affect voice, valency, intensity, causation, reflexivity, and other grammatical/lexical properties. They should not be reduced to a single fixed English formula.

[b]Other information scholars inspect[/b]
• person
• gender
• number
• state (absolute/construct)
• tense-aspect/mood categories
• attached conjunctions/prepositions/articles
• pronominal suffixes
• syntactic role
• discourse context

[b]Important[/b]
The dictionary headword, the surface form in a verse, and the underlying root may all look different. The future verse analyzer should use morphological data rather than guessing from spelling alone.
""",

    "translation": """[b]Translation Approaches[/b]

Translation strategies are better understood as overlapping priorities than as a simple “good vs bad” scale.

[b]Formal / source-oriented correspondence[/b]
Prioritizes preserving wording, grammatical relationships, and source-text structure where practical. A highly formal rendering can expose features of Hebrew but may sound less natural in English.

[b]Dynamic / functional equivalence[/b]
Associated especially with Eugene Nida. Prioritizes communicating the source message naturally to the receiving audience rather than mirroring source-language form.

[b]Idiomatic translation[/b]
Uses normal target-language expressions when a direct structural rendering would be confusing or unnatural.

[b]Paraphrase[/b]
Re-expresses meaning more freely and generally includes a higher degree of interpretation.

[b]Interlinear / gloss[/b]
A study aid aligning source forms with compact glosses. It is useful for analysis but is not the same thing as a polished translation.

[b]Scholar caution[/b]
“Literal” is not a synonym for “accurate.” Languages divide meaning differently, and a formally close rendering can still miscommunicate. Conversely, a freer rendering necessarily makes more interpretive decisions visible or invisible.
""",

    "skopos": """[b]Skopos Theory[/b]

Skopos is Greek for “purpose.” In translation studies, Skopos theory is associated especially with Hans J. Vermeer and Katharina Reiss.

Its central concern is the purpose or function of the translational action in the target setting.

Questions include:

• Who is the intended reader?
• What is the translation for?
• Is it for liturgy, scholarship, beginners, literary reading, children, or interlinear study?
• Which source-text features must remain visible for that purpose?
• Which target-language conventions should take priority?

[b]Example[/b]
A Hebrew-English interlinear and a children’s Bible may responsibly make very different translation decisions because their purposes differ.

[b]Not the same as “free translation”[/b]
Skopos theory does not simply mean “translate however you want.” It provides a functional framework for evaluating choices in relation to an intended purpose and target context.

[b]In this app[/b]
The Tanakh Reader should therefore keep separate layers:
Hebrew source text → morphology/lexicon → English version → translator/translation-purpose notes.
""",

    "textcritical": """[b]Text-Critical and Lexical Cautions[/b]

A scholarly reader should keep several layers distinct.

[b]1. Manuscript/textual form[/b]
The Hebrew text displayed is a particular textual tradition/edition.

[b]2. Vocalization[/b]
Masoretic vowel and cantillation marks represent a reading tradition layered onto the consonantal text.

[b]3. Morphological analysis[/b]
Parsing identifies grammatical form. It is analysis, not translation.

[b]4. Lexical gloss[/b]
A dictionary gloss lists possible senses. It does not determine which sense is correct in every verse.

[b]5. Translation[/b]
An English version makes interpretive decisions involving syntax, semantics, discourse, idiom, audience, and theology/literary context.

[b]6. Your notes[/b]
Personal or scholarly observations should remain clearly distinguishable from dictionary data and source text.

[b]Rule for this application[/b]
Never display an English translation as though it were simply “the meaning” of an isolated Hebrew word.
""",

    "sources": """[b]Research Basis[/b]

This Scholar section is a compact study reference, not a replacement for a full Biblical Hebrew grammar or translation-studies textbook.

Primary reference families used for the design:

• Society of Biblical Literature, SBL Handbook of Style and Student Supplement:
  Hebrew transliteration conventions; distinction between academic and general-purpose systems.

• SBL Press Biblical Hebrew grammar resources:
  language should be treated as a coherent grammatical system rather than merely a list of word equivalents.

• Eugene A. Nida, Toward a Science of Translating:
  formal correspondence and dynamic equivalence/correspondence.

• Katharina Reiss and Hans J. Vermeer, Skopos theory:
  translation as purposeful translational action.

[b]Application principle[/b]
The app should show source text, lexical data, morphology, translation, and user interpretation as separate layers.
"""
}

class HebrewFuzzy(App):
    TITLE = "Hebrew Fuzzy Study"
    SUB_TITLE = "Dictionary • Tanakh Reader • Notes • Export"

    CSS = """
    Screen { layout: vertical; }
    #search, #verse-search { margin: 0 1; }
    #status, #tanakh-status { height: auto; margin: 0 1; }
    #results, #selected, #perms, #notes-table, #verses-table, #verse-notes-table { height: 1fr; }
    #detail { padding: 1 2; overflow-y: auto; }
    #chapter-controls { height: auto; }
    #book-select { width: 2fr; }
    #chapter-input { width: 1fr; }
    #reader { height: 12; }
    #hebrew-pane, #english-pane {
        width: 1fr;
        padding: 1 2;
        border: solid $secondary;
        overflow-y: auto;
    }
    #verse-note-tag { width: 1fr; }
    #verse-note-body { height: 7; }
    #scholar-topic { margin: 1; }
    #scholar-content {
        height: 1fr;
        padding: 1 2;
        overflow-y: auto;
        border: solid $secondary;
    }
    #selection-actions, #perm-actions { height: auto; }
    #verse-note-controls, #note-controls { height: auto; }
    #note-tag, #note-verse { width: 1fr; }
    #note-body { height: 9; }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("ctrl+l", "focus_search", "Search"),
        Binding("space", "toggle_selected", "Select"),
        Binding("p", "show_permutations", "Permute"),
        Binding("v", "find_verses", "Verses"),
        Binding("n", "open_notes", "Word Notes"),
        Binding("r", "open_reader", "Reader"),
        Binding("e", "export_verse_notes", "Verse Export"),
        Binding("x", "export_selected_words", "Export Words"),
        Binding("shift+x", "export_permutations", "Export Perms"),
        Binding("escape", "focus_search", "Search"),
    ]

    def __init__(self):
        super().__init__()
        self.conn = sqlite3.connect(DB_PATH)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.ensure_schema()
        self.rows = self.conn.execute("SELECT * FROM words ORDER BY entry_no").fetchall()
        self.selected_ids: list[int] = []
        self.active_word_id: int | None = None
        self.active_verse_id: int | None = None

    def ensure_schema(self) -> None:
        self.conn.executescript("""
        CREATE TABLE IF NOT EXISTS word_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word_id INTEGER NOT NULL,
            tag TEXT NOT NULL DEFAULT '',
            verse_reference TEXT NOT NULL DEFAULT '',
            note TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(word_id) REFERENCES words(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS verse_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            verse_id INTEGER NOT NULL,
            tag TEXT NOT NULL DEFAULT '',
            note TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(verse_id) REFERENCES verses(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS verses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book TEXT NOT NULL, book_code TEXT NOT NULL,
            chapter INTEGER NOT NULL, verse INTEGER NOT NULL,
            reference TEXT NOT NULL, hebrew TEXT NOT NULL DEFAULT '',
            hebrew_norm TEXT NOT NULL DEFAULT '', english TEXT NOT NULL DEFAULT '',
            UNIQUE(book_code,chapter,verse)
        );
        """)
        self.conn.commit()

    def compose(self) -> ComposeResult:
        yield Header()
        yield Input(
            placeholder="Dictionary pronunciation search: bera, berak, abee...",
            id="search"
        )
        yield Label("Type to search • R reader • V word→verses • N notes • E export verse notes", id="status")

        with TabbedContent(initial="search_tab"):
            with TabPane("Search", id="search_tab"):
                yield DataTable(id="results", cursor_type="row", zebra_stripes=True)

            with TabPane("Detail", id="detail_tab"):
                yield Static("Highlight a dictionary result.", id="detail")

            with TabPane("Word Notes", id="notes_tab"):
                yield Static("Choose a word from Search.", id="note-word")
                with Horizontal(id="note-controls"):
                    yield Input(placeholder="Tag", id="note-tag")
                    yield Input(placeholder="Verse reference, e.g. Genesis 12:2", id="note-verse")
                    yield Button("Save Word Note", id="save-word-note", variant="primary")
                yield TextArea(id="note-body")
                yield DataTable(id="notes-table", cursor_type="row", zebra_stripes=True)

            with TabPane("Tanakh Reader", id="tanakh_tab"):
                yield Label("", id="tanakh-status")
                with Horizontal(id="chapter-controls"):
                    yield Select([(name, code) for name, code in BOOKS], value="Gen", id="book-select")
                    yield Input(value="1", placeholder="Chapter", id="chapter-input")
                    yield Button("Load Chapter", id="load-chapter", variant="primary")
                yield Input(
                    placeholder="Search English text/reference or Hebrew text",
                    id="verse-search"
                )
                yield DataTable(id="verses-table", cursor_type="row", zebra_stripes=True)
                with Horizontal(id="reader"):
                    yield Static("Hebrew verse", id="hebrew-pane")
                    yield Static("English verse", id="english-pane")

                with Horizontal(id="verse-note-controls"):
                    yield Input(placeholder="Verse note tag", id="verse-note-tag")
                    yield Button("Save Verse Note", id="save-verse-note", variant="primary")
                    yield Button("Export Verse Notes", id="export-verse-notes")
                yield TextArea(id="verse-note-body")
                yield DataTable(id="verse-notes-table", cursor_type="row", zebra_stripes=True)

            with TabPane("Scholar", id="scholar_tab"):
                yield Select(
                    [
                        ("Hebrew Prefixes", "prefixes"),
                        ("Hebrew Suffixes", "suffixes"),
                        ("Transliteration", "transliteration"),
                        ("Roots & Morphology", "morphology"),
                        ("Translation Approaches", "translation"),
                        ("Skopos Theory", "skopos"),
                        ("Text-Critical Cautions", "textcritical"),
                        ("Research Sources", "sources"),
                    ],
                    value="prefixes",
                    id="scholar-topic",
                )
                yield Static("", id="scholar-content")

            with TabPane("Selected", id="selected_tab"):
                with Horizontal(id="selection-actions"):
                    yield Button("Export Selected Words", id="export-selected", variant="primary")
                    yield Static("Up to 10 words may be selected.")
                yield DataTable(id="selected", cursor_type="row", zebra_stripes=True)

            with TabPane("Permutations", id="perm_tab"):
                with Horizontal(id="perm-actions"):
                    yield Button("Export Permutations", id="export-permutations", variant="primary")
                    yield Static("Preview is capped for safety; export rules depend on permutation count.")
                yield DataTable(id="perms", cursor_type="row", zebra_stripes=True)

        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#results", DataTable).add_columns(
            "Strong", "Hebrew", "Pronunciation", "Transliteration", "Meaning"
        )
        self.query_one("#notes-table", DataTable).add_columns("Tag", "Verse", "Note", "Created")
        self.query_one("#verses-table", DataTable).add_columns("Verse", "Hebrew", "English")
        self.query_one("#verse-notes-table", DataTable).add_columns("Tag", "Note", "Created")
        self.query_one("#selected", DataTable).add_columns("Strong", "Hebrew", "Pronunciation", "Meaning")
        self.query_one("#perms", DataTable).add_columns("#", "Hebrew phrase", "Pronunciation order")

        count = self.conn.execute("SELECT count(*) FROM verses").fetchone()[0]
        both = self.conn.execute(
            "SELECT count(*) FROM verses WHERE hebrew<>'' AND english<>''"
        ).fetchone()[0]
        if count == 0:
            self.query_one("#tanakh-status", Label).update(
                "[b]Tanakh not imported.[/b] Run: [b]hebrew-fuzzy-import-tanakh[/b] in Terminal, then restart the app."
            )
        else:
            self.query_one("#tanakh-status", Label).update(
                f"{count:,} verse rows loaded • {both:,} have both Hebrew + English"
            )
            self.load_chapter("Gen", 1)

        self.query_one("#search", Input).focus()
        self.run_search("")
        self.query_one("#scholar-content", Static).update(SCHOLAR_TOPICS["prefixes"])

    def action_focus_search(self) -> None:
        self.query_one(TabbedContent).active = "search_tab"
        self.query_one("#search", Input).focus()

    def action_open_reader(self) -> None:
        self.query_one(TabbedContent).active = "tanakh_tab"

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "scholar-topic":
            topic = str(event.value)
            self.query_one("#scholar-content", Static).update(
                SCHOLAR_TOPICS.get(topic, "Scholar topic unavailable.")
            )

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search":
            self.run_search(event.value)
        elif event.input.id == "verse-search":
            self.search_verses(event.value)

    def score(self, q: str, row: sqlite3.Row) -> float:
        if not q:
            return 1
        p = row["pronunciation_norm"] or ""
        x = row["transliteration_norm"] or ""
        sid = (row["strong_id"] or "").lower()
        definition = normalize_latin(row["definitions"] or "")
        bonus = 0
        if p.startswith(q): bonus += 70
        elif q in p: bonus += 55
        if x.startswith(q): bonus += 45
        elif q in x: bonus += 35
        if q == sid: bonus += 100
        return bonus + max(
            fuzz.WRatio(q, p),
            fuzz.WRatio(q, x) * 0.90,
            fuzz.partial_ratio(q, definition) * 0.40,
        )

    def run_search(self, raw: str) -> None:
        q = normalize_latin(raw)
        scored = [(self.score(q, r), r) for r in self.rows]
        if q:
            scored = [pair for pair in scored if pair[0] >= 48]
            scored.sort(key=lambda pair: (-pair[0], pair[1]["entry_no"]))
            scored = scored[:150]
        else:
            scored = scored[:100]

        table = self.query_one("#results", DataTable)
        table.clear()
        for _, r in scored:
            meaning = (r["definitions"] or "").splitlines()[0] if r["definitions"] else ""
            table.add_row(
                r["strong_id"], r["hebrew"], r["pronunciation"],
                r["transliteration"], meaning, key=str(r["id"])
            )
        if scored:
            self.set_active_word(scored[0][1])

    def row_from_key(self, key) -> sqlite3.Row | None:
        if key is None:
            return None
        try:
            rid = int(str(key.value if hasattr(key, "value") else key))
        except (TypeError, ValueError):
            return None
        return self.conn.execute("SELECT * FROM words WHERE id=?", (rid,)).fetchone()

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.data_table.id == "results":
            row = self.row_from_key(event.row_key)
            if row:
                self.set_active_word(row)
        elif event.data_table.id == "verses-table":
            try:
                rid = int(str(event.row_key.value))
            except Exception:
                return
            row = self.conn.execute("SELECT * FROM verses WHERE id=?", (rid,)).fetchone()
            if row:
                self.set_active_verse(row)

    def set_active_word(self, r: sqlite3.Row) -> None:
        self.active_word_id = r["id"]
        self.query_one("#detail", Static).update(
            f"[b]{r['lemma'] or r['hebrew']}[/b]\n\n"
            f"Strong: {r['strong_id']}\n"
            f"Hebrew: {r['hebrew']}\n"
            f"Pronunciation: {r['pronunciation']}\n"
            f"Transliteration: {r['transliteration']}\n"
            f"Morphology: {r['morphology']}\n\n"
            f"[b]Definitions[/b]\n{r['definitions'] or '—'}\n\n"
            f"[b]Dictionary Notes[/b]\n{r['notes'] or '—'}"
        )
        self.query_one("#note-word", Static).update(
            f"[b]{r['lemma'] or r['hebrew']}[/b]  {r['strong_id']}  •  {r['pronunciation']}"
        )
        self.refresh_word_notes()

    def set_active_verse(self, row: sqlite3.Row) -> None:
        self.active_verse_id = row["id"]
        self.query_one("#hebrew-pane", Static).update(
            f"[b]{row['reference']}[/b]\n\n{row['hebrew'] or 'No Hebrew text for this row.'}"
        )
        self.query_one("#english-pane", Static).update(
            f"[b]{row['reference']}[/b]\n\n{row['english'] or 'No English text for this row.'}"
        )
        self.refresh_verse_notes()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "save-word-note":
            self.save_word_note()
        elif bid == "load-chapter":
            code = self.query_one("#book-select", Select).value
            try:
                chapter = int(self.query_one("#chapter-input", Input).value)
            except ValueError:
                self.query_one("#status", Label).update("Chapter must be a number.")
                return
            self.load_chapter(str(code), chapter)
        elif bid == "save-verse-note":
            self.save_verse_note()
        elif bid == "export-verse-notes":
            self.action_export_verse_notes()
        elif bid == "export-selected":
            self.action_export_selected_words()
        elif bid == "export-permutations":
            self.action_export_permutations()

    def load_chapter(self, book_code: str, chapter: int) -> None:
        rows = self.conn.execute("""
            SELECT * FROM verses
            WHERE book_code=? AND chapter=?
            ORDER BY verse
        """, (book_code, chapter)).fetchall()
        table = self.query_one("#verses-table", DataTable)
        table.clear()
        for r in rows:
            table.add_row(str(r["verse"]), r["hebrew"], r["english"], key=str(r["id"]))
        if rows:
            self.set_active_verse(rows[0])
            self.query_one("#tanakh-status", Label).update(
                f"[b]{rows[0]['book']} {chapter}[/b] • {len(rows)} verses • Hebrew and English side by side below"
            )
        else:
            count = self.conn.execute("SELECT count(*) FROM verses").fetchone()[0]
            if count == 0:
                self.query_one("#tanakh-status", Label).update(
                    "[b]Tanakh not imported.[/b] Run [b]hebrew-fuzzy-import-tanakh[/b] and restart."
                )
            else:
                self.query_one("#tanakh-status", Label).update("No verses found for that chapter.")

    def search_verses(self, raw: str) -> None:
        q = raw.strip()
        if len(q) < 2:
            return
        table = self.query_one("#verses-table", DataTable)
        table.clear()

        if any("\u0590" <= ch <= "\u05FF" for ch in q):
            nq = normalize_hebrew(q)
            rows = self.conn.execute("""
                SELECT * FROM verses
                WHERE instr(hebrew_norm, ?) > 0
                ORDER BY id LIMIT 200
            """, (nq,)).fetchall()
        else:
            rows = self.conn.execute("""
                SELECT * FROM verses
                WHERE reference LIKE ? OR english LIKE ?
                ORDER BY id LIMIT 200
            """, (f"%{q}%", f"%{q}%")).fetchall()

        for r in rows:
            table.add_row(r["reference"], r["hebrew"], r["english"], key=str(r["id"]))
        if rows:
            self.set_active_verse(rows[0])
        self.query_one("#tanakh-status", Label).update(f"{len(rows)} verse search result(s).")

    def action_find_verses(self) -> None:
        if not self.active_word_id:
            return
        word = self.conn.execute(
            "SELECT * FROM words WHERE id=?", (self.active_word_id,)
        ).fetchone()
        target = normalize_hebrew(word["hebrew"] or word["lemma"] or "")
        rows = self.conn.execute("""
            SELECT * FROM verses
            WHERE instr(hebrew_norm, ?) > 0
            ORDER BY id LIMIT 200
        """, (target,)).fetchall()

        table = self.query_one("#verses-table", DataTable)
        table.clear()
        for r in rows:
            table.add_row(r["reference"], r["hebrew"], r["english"], key=str(r["id"]))
        self.query_one(TabbedContent).active = "tanakh_tab"
        if rows:
            self.set_active_verse(rows[0])
        self.query_one("#tanakh-status", Label).update(
            f"{len(rows)} verse(s) contain {word['hebrew']}."
            if rows else
            "No matches. If the Tanakh count is 0, run hebrew-fuzzy-import-tanakh first."
        )

    def action_open_notes(self) -> None:
        self.query_one(TabbedContent).active = "notes_tab"

    def save_word_note(self) -> None:
        if not self.active_word_id:
            return
        tag = self.query_one("#note-tag", Input).value.strip()
        verse = self.query_one("#note-verse", Input).value.strip()
        note = self.query_one("#note-body", TextArea).text.strip()
        if not (tag or verse or note):
            return
        self.conn.execute(
            "INSERT INTO word_notes(word_id,tag,verse_reference,note) VALUES(?,?,?,?)",
            (self.active_word_id, tag, verse, note)
        )
        self.conn.commit()
        self.query_one("#note-tag", Input).value = ""
        self.query_one("#note-verse", Input).value = ""
        self.query_one("#note-body", TextArea).text = ""
        self.refresh_word_notes()

    def refresh_word_notes(self) -> None:
        table = self.query_one("#notes-table", DataTable)
        table.clear()
        if not self.active_word_id:
            return
        rows = self.conn.execute("""
            SELECT * FROM word_notes WHERE word_id=? ORDER BY id DESC
        """, (self.active_word_id,)).fetchall()
        for r in rows:
            table.add_row(
                r["tag"], r["verse_reference"],
                r["note"].replace("\n", " ")[:100], r["created_at"],
                key=str(r["id"])
            )

    def save_verse_note(self) -> None:
        if not self.active_verse_id:
            self.query_one("#tanakh-status", Label).update("Select a verse first.")
            return
        tag = self.query_one("#verse-note-tag", Input).value.strip()
        note = self.query_one("#verse-note-body", TextArea).text.strip()
        if not (tag or note):
            self.query_one("#tanakh-status", Label).update("Enter a tag or note.")
            return
        self.conn.execute(
            "INSERT INTO verse_notes(verse_id,tag,note) VALUES(?,?,?)",
            (self.active_verse_id, tag, note)
        )
        self.conn.commit()
        self.query_one("#verse-note-tag", Input).value = ""
        self.query_one("#verse-note-body", TextArea).text = ""
        self.refresh_verse_notes()
        self.query_one("#tanakh-status", Label).update("Verse note saved.")

    def refresh_verse_notes(self) -> None:
        table = self.query_one("#verse-notes-table", DataTable)
        table.clear()
        if not self.active_verse_id:
            return
        rows = self.conn.execute("""
            SELECT * FROM verse_notes WHERE verse_id=? ORDER BY id DESC
        """, (self.active_verse_id,)).fetchall()
        for r in rows:
            table.add_row(
                r["tag"], r["note"].replace("\n", " ")[:120],
                r["created_at"], key=str(r["id"])
            )

    def action_export_verse_notes(self) -> None:
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        csv_path = EXPORT_DIR / f"verse-notes-{stamp}.csv"
        md_path = EXPORT_DIR / f"verse-notes-{stamp}.md"

        rows = self.conn.execute("""
            SELECT
                v.reference, v.hebrew, v.english,
                n.tag, n.note, n.created_at
            FROM verse_notes n
            JOIN verses v ON v.id=n.verse_id
            ORDER BY v.id, n.id
        """).fetchall()

        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["reference", "hebrew", "english", "tag", "note", "created_at"])
            for r in rows:
                writer.writerow([
                    r["reference"], r["hebrew"], r["english"],
                    r["tag"], r["note"], r["created_at"]
                ])

        with md_path.open("w", encoding="utf-8") as f:
            f.write("# Hebrew Fuzzy Study — Verse Notes\n\n")
            for r in rows:
                f.write(f"## {r['reference']}\n\n")
                f.write(f"**Hebrew:** {r['hebrew']}\n\n")
                f.write(f"**English:** {r['english']}\n\n")
                if r["tag"]:
                    f.write(f"**Tag:** {r['tag']}\n\n")
                f.write(f"{r['note']}\n\n")
                f.write(f"_Saved: {r['created_at']}_\n\n---\n\n")

        self.query_one("#tanakh-status", Label).update(
            f"Exported {len(rows)} verse note(s): {csv_path} and {md_path}"
        )

    def current_result(self) -> sqlite3.Row | None:
        table = self.query_one("#results", DataTable)
        if table.row_count == 0:
            return None
        cell = table.coordinate_to_cell_key(table.cursor_coordinate)
        return self.row_from_key(cell.row_key)

    def action_toggle_selected(self) -> None:
        row = self.current_result()
        if not row:
            return
        rid = row["id"]
        if rid in self.selected_ids:
            self.selected_ids.remove(rid)
        elif len(self.selected_ids) < 10:
            self.selected_ids.append(rid)
        else:
            self.query_one("#status", Label).update(
                "Selection limit is 10 words. 10! = 3,628,800 permutations, so previews/exports are safety-limited."
            )
            return
        self.refresh_selected()

    def refresh_selected(self) -> None:
        table = self.query_one("#selected", DataTable)
        table.clear()
        for rid in self.selected_ids:
            r = self.conn.execute("SELECT * FROM words WHERE id=?", (rid,)).fetchone()
            meaning = (r["definitions"] or "").splitlines()[0] if r["definitions"] else ""
            table.add_row(r["strong_id"], r["hebrew"], r["pronunciation"], meaning, key=str(rid))

    def action_show_permutations(self) -> None:
        table = self.query_one("#perms", DataTable)
        table.clear()
        if not self.selected_ids:
            self.query_one("#status", Label).update("Select at least one word first.")
            return

        words = [
            self.conn.execute("SELECT * FROM words WHERE id=?", (rid,)).fetchone()
            for rid in self.selected_ids
        ]
        total = math.factorial(len(words))
        preview_limit = 5000

        for i, perm in enumerate(itertools.islice(itertools.permutations(words), preview_limit), 1):
            table.add_row(
                str(i),
                " ".join(r["hebrew"] for r in perm),
                " ".join(r["pronunciation"] for r in perm),
            )

        self.query_one(TabbedContent).active = "perm_tab"
        if total > preview_limit:
            self.query_one("#status", Label).update(
                f"Showing first {preview_limit:,} of {total:,} permutations. "
                "The preview is capped to keep the TUI responsive."
            )
        else:
            self.query_one("#status", Label).update(
                f"Showing all {total:,} permutations."
            )

    def action_export_selected_words(self) -> None:
        if not self.selected_ids:
            self.query_one("#status", Label).update("No selected words to export.")
            return

        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        csv_path = EXPORT_DIR / f"selected-words-{stamp}.csv"
        md_path = EXPORT_DIR / f"selected-words-{stamp}.md"

        words = [
            self.conn.execute("SELECT * FROM words WHERE id=?", (rid,)).fetchone()
            for rid in self.selected_ids
        ]

        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "strong_id", "hebrew", "lemma", "pronunciation",
                "transliteration", "morphology", "definitions"
            ])
            for r in words:
                writer.writerow([
                    r["strong_id"], r["hebrew"], r["lemma"], r["pronunciation"],
                    r["transliteration"], r["morphology"], r["definitions"]
                ])

        with md_path.open("w", encoding="utf-8") as f:
            f.write("# Hebrew Fuzzy Study — Selected Words\n\n")
            for r in words:
                f.write(f"## {r['strong_id']} — {r['lemma'] or r['hebrew']}\n\n")
                f.write(f"- Hebrew: {r['hebrew']}\n")
                f.write(f"- Pronunciation: {r['pronunciation']}\n")
                f.write(f"- Transliteration: {r['transliteration']}\n")
                f.write(f"- Morphology: {r['morphology']}\n\n")
                f.write(f"{r['definitions'] or ''}\n\n---\n\n")

        self.query_one("#status", Label).update(
            f"Exported {len(words)} selected word(s): {csv_path} and {md_path}"
        )

    def action_export_permutations(self) -> None:
        if not self.selected_ids:
            self.query_one("#status", Label).update("No selected words to permute/export.")
            return

        words = [
            self.conn.execute("SELECT * FROM words WHERE id=?", (rid,)).fetchone()
            for rid in self.selected_ids
        ]
        total = math.factorial(len(words))

        # Safety policy:
        # <= 8 words: export every permutation (8! = 40,320).
        # 9-10 words: export the first 100,000 only and clearly mark it as capped.
        full_export_limit = math.factorial(8)
        capped_export_limit = 100_000
        export_count = total if total <= full_export_limit else min(total, capped_export_limit)
        complete = export_count == total

        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        csv_path = EXPORT_DIR / f"permutations-{stamp}.csv"
        md_path = EXPORT_DIR / f"permutations-{stamp}.md"

        iterator = itertools.islice(itertools.permutations(words), export_count)

        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "permutation_number", "hebrew", "pronunciation",
                "strong_ids", "complete_export", "total_possible"
            ])
            for i, perm in enumerate(iterator, 1):
                writer.writerow([
                    i,
                    " ".join(r["hebrew"] for r in perm),
                    " ".join(r["pronunciation"] for r in perm),
                    " ".join(r["strong_id"] for r in perm),
                    "yes" if complete else "no",
                    total,
                ])

        iterator = itertools.islice(itertools.permutations(words), export_count)
        with md_path.open("w", encoding="utf-8") as f:
            f.write("# Hebrew Fuzzy Study — Permutations\n\n")
            f.write(f"- Selected words: {len(words)}\n")
            f.write(f"- Total mathematically possible: {total:,}\n")
            f.write(f"- Exported: {export_count:,}\n")
            f.write(f"- Complete export: {'Yes' if complete else 'No — safety cap applied'}\n\n")
            for i, perm in enumerate(iterator, 1):
                f.write(
                    f"{i}. **{' '.join(r['hebrew'] for r in perm)}**  "
                    f"— {' '.join(r['pronunciation'] for r in perm)}\n"
                )

        if complete:
            msg = f"Exported all {total:,} permutations."
        else:
            msg = (
                f"{total:,} permutations are possible; safely exported the first "
                f"{export_count:,}. Full 9!/10! export is intentionally blocked."
            )
        self.query_one("#status", Label).update(
            f"{msg} Files: {csv_path} and {md_path}"
        )

    def on_unmount(self) -> None:
        self.conn.close()

if __name__ == "__main__":
    HebrewFuzzy().run()


def main():
    app = HebrewFuzzy()
    app.run()


if __name__ == "__main__":
    main()
