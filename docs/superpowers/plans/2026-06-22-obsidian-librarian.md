# Obsidian Librarian Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone `librarian` Obsidian skill (plus a companion agent) that bridges a vault of book notes and a BibTeX `.bib` file — keeping them in sync, enriching metadata, auditing integrity, exporting citations, and maintaining a collating Base.

**Architecture:** The skill is the DNA (a `SKILL.md` router → `references/` mode playbooks → `templates/`), mirroring the existing `generous-ledger-skill`. All instance state lives visibly in the consumer's vault under a configurable folder (default `Library/`), never in the skill. The fiddly, deterministic work (`.bib` parse/write, citekey minting, ISBN checksums, CSV import) is done by a single dependency-free Python CLI, `scripts/bibtools.py`, which the mode playbooks shell out to. Vault I/O goes through the `obsidian-cli` skill; the LLM handles judgment, prose, enrichment, and conversation.

**Tech Stack:** Markdown skill files; Python 3 standard library only at runtime (`re`, `csv`, `json`, `argparse`); `pytest` for development tests; Obsidian CLI for vault I/O; WebFetch (an LLM tool, not the script) for enrichment.

## Global Constraints

These apply to every task; copied verbatim from the spec.

- **Vault is canonical.** `.bib`→vault is an explicit on-command operation, never automatic.
- **Never auto-delete** a `.bib` entry or a note. Orphans are *reported*, never removed.
- **Citekey scheme: AuthorYear** (e.g. `MacIntyre1981`), with `a`/`b`/`c` suffix on collision.
- **Runtime dependency-free:** `bibtools.py` uses only the Python 3 standard library. `pytest` is a dev-only dependency.
- **Standalone skill** that reuses Generous Ledger conventions: state-in-vault, provenance marking, `obsidian-cli` I/O. No dependency on a Generous Ledger existing.
- **Default folder `Library/`, configurable.** Setup records the book-notes folder and `.bib` path in a vault config file.
- **Confirm before writing** enrichment data and before any bulk operation; show a diff first.
- **Cite mode always asks** which citation style; it has no default.
- **Provenance on every AI write:** `fullAI`/`mixedAI` frontmatter booleans (never both true) + line-level `⚡ ` prefix on AI lines in Mixed notes; a `> [!ai] …` banner (no per-line prefix) in Full-AI notes.
- **Obsidian CLI:** always pass `vault=<vault-name>` as the first argument.

## File Structure

```
librarian-skill/
├── SKILL.md                       # router → modes (Task 13)
├── README.md                      # install + overview (Task 15)
├── references/
│   ├── conventions.md             # folder layout, YAML schema, citekey rules, I/O (Task 8)
│   ├── provenance.md              # AI-authorship marking (Task 8)
│   ├── enrichment.md              # ISBN/title lookup via Open Library → Google Books (Task 9)
│   ├── mode-setup.md              # (Task 10)
│   ├── mode-new-book.md           # (Task 10)
│   ├── mode-sync.md               # vault → .bib reconcile (Task 11)
│   ├── mode-import.md             # .bib → vault + bulk Goodreads/Zotero (Task 11)
│   ├── mode-audit.md              # validation/lint + dedup + orphan report (Task 12)
│   └── mode-cite.md               # formatted citation export (Task 12)
├── scripts/
│   ├── bibtools.py                # deterministic core + CLI (Tasks 1–5)
│   └── tests/
│       ├── test_bibtools.py       # pytest unit tests (Tasks 1–5)
│       └── fixtures/
│           ├── sample.bib         # (Task 2)
│           └── goodreads.csv      # (Task 4)
├── templates/
│   ├── BookNote.md                # book-note template (Task 6)
│   ├── Books.base                 # Obsidian Base (Task 7)
│   ├── config.md                  # records folder + .bib path, written into vault (Task 6)
│   └── CLAUDE.md                  # per-vault operating contract (Task 6)
└── agents/
    └── librarian.md               # subagent definition (Task 14)
```

`bibtools.py` is the only file with executable logic and the only unit-tested unit. Reference/template files are content, validated by parsing (YAML/frontmatter) and manual review.

---

## Task 1: Project scaffold + ISBN validation

**Files:**
- Create: `librarian-skill/scripts/bibtools.py`
- Create: `librarian-skill/scripts/tests/test_bibtools.py`
- Create: `librarian-skill/.gitignore`

**Interfaces:**
- Consumes: nothing (first task).
- Produces:
  - `normalize_isbn(raw: str) -> str | None` — strips hyphens/spaces/`="..."` wrappers; returns the bare digit string (with trailing `X` allowed for ISBN-10), or `None` if it isn't 10/13 chars of the right shape.
  - `valid_isbn(raw: str) -> bool` — `True` iff `normalize_isbn` yields a string whose ISBN-10 or ISBN-13 checksum is valid.

- [ ] **Step 1: Create the git repo and ignore file**

```bash
mkdir -p librarian-skill/scripts/tests/fixtures
cd librarian-skill
git init
printf '__pycache__/\n*.pyc\n.pytest_cache/\n' > .gitignore
```

- [ ] **Step 2: Write the failing test**

Create `librarian-skill/scripts/tests/test_bibtools.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import bibtools


def test_normalize_isbn_strips_formatting():
    assert bibtools.normalize_isbn("978-0-268-03504-4") == "9780268035044"
    assert bibtools.normalize_isbn('="9780268035044"') == "9780268035044"
    assert bibtools.normalize_isbn("0-268-00594-X") == "026800594X"
    assert bibtools.normalize_isbn("nonsense") is None


def test_valid_isbn13():
    assert bibtools.valid_isbn("978-0-268-03504-4") is True
    assert bibtools.valid_isbn("978-0-268-03504-5") is False  # bad check digit


def test_valid_isbn10():
    assert bibtools.valid_isbn("0-268-00594-X") is True
    assert bibtools.valid_isbn("0-268-00594-1") is False
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd librarian-skill && python -m pytest scripts/tests/test_bibtools.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bibtools'` (or `AttributeError`).

- [ ] **Step 4: Write minimal implementation**

Create `librarian-skill/scripts/bibtools.py`:

```python
"""Deterministic helpers for the Obsidian librarian skill.

Standard library only. Exposes a CLI (see main()) that the skill's mode
playbooks shell out to, plus importable functions used by the tests.
"""
import re


def normalize_isbn(raw):
    """Return the bare ISBN digits (trailing X allowed) or None."""
    if raw is None:
        return None
    # Strip Goodreads-style ="..." wrappers and any non-isbn characters.
    s = raw.strip()
    s = re.sub(r'^="?|"?$', "", s)            # leading =" and trailing "
    s = re.sub(r"[\s-]", "", s)               # spaces and hyphens
    s = s.upper()
    if re.fullmatch(r"\d{13}", s):
        return s
    if re.fullmatch(r"\d{9}[\dX]", s):
        return s
    return None


def valid_isbn(raw):
    s = normalize_isbn(raw)
    if s is None:
        return False
    if len(s) == 13:
        total = sum((1 if i % 2 == 0 else 3) * int(d) for i, d in enumerate(s))
        return total % 10 == 0
    # ISBN-10
    total = 0
    for i, ch in enumerate(s):
        val = 10 if ch == "X" else int(ch)
        total += (10 - i) * val
    return total % 11 == 0
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd librarian-skill && python -m pytest scripts/tests/test_bibtools.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
cd librarian-skill
git add .gitignore scripts/bibtools.py scripts/tests/test_bibtools.py
git commit -m "feat: bibtools ISBN normalization and checksum validation"
```

---

## Task 2: BibTeX parse / format / write round-trip

**Files:**
- Modify: `librarian-skill/scripts/bibtools.py`
- Modify: `librarian-skill/scripts/tests/test_bibtools.py`
- Create: `librarian-skill/scripts/tests/fixtures/sample.bib`

**Interfaces:**
- Consumes: nothing new.
- Produces:
  - `parse_bib(text: str) -> list[dict]` — each entry is `{"type": str, "citekey": str, "fields": dict[str, str]}` with lowercased field names and braces/quotes stripped from values.
  - `format_entry(entry: dict) -> str` — one BibTeX entry; field order: `author, title, year, publisher, isbn`, then remaining fields alphabetically.
  - `write_bib(entries: list[dict]) -> str` — all entries joined by blank lines, trailing newline.

- [ ] **Step 1: Create the fixture**

Create `librarian-skill/scripts/tests/fixtures/sample.bib`:

```bibtex
@book{MacIntyre1981,
  author = {MacIntyre, Alasdair},
  title = {After Virtue},
  year = {1981},
  publisher = {University of Notre Dame Press}
}

@book{Taylor1989,
  author = {Taylor, Charles},
  title = {Sources of the Self},
  year = {1989}
}
```

- [ ] **Step 2: Write the failing test**

Append to `test_bibtools.py`:

```python
import os

FIX = os.path.join(os.path.dirname(__file__), "fixtures")


def test_parse_bib_reads_entries():
    with open(os.path.join(FIX, "sample.bib")) as f:
        entries = bibtools.parse_bib(f.read())
    assert len(entries) == 2
    e = entries[0]
    assert e["type"] == "book"
    assert e["citekey"] == "MacIntyre1981"
    assert e["fields"]["author"] == "MacIntyre, Alasdair"
    assert e["fields"]["title"] == "After Virtue"
    assert e["fields"]["year"] == "1981"


def test_format_entry_orders_fields():
    entry = {"type": "book", "citekey": "X2000",
             "fields": {"isbn": "123", "title": "T", "author": "A", "year": "2000"}}
    out = bibtools.format_entry(entry)
    assert out.startswith("@book{X2000,")
    # author before title before year before isbn
    assert out.index("author") < out.index("title") < out.index("year") < out.index("isbn")


def test_round_trip():
    with open(os.path.join(FIX, "sample.bib")) as f:
        text = f.read()
    entries = bibtools.parse_bib(text)
    reparsed = bibtools.parse_bib(bibtools.write_bib(entries))
    assert reparsed == entries
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd librarian-skill && python -m pytest scripts/tests/test_bibtools.py -k "parse_bib or format_entry or round_trip" -v`
Expected: FAIL — `AttributeError: module 'bibtools' has no attribute 'parse_bib'`.

- [ ] **Step 4: Write minimal implementation**

Append to `bibtools.py`:

```python
_FIELD_ORDER = ["author", "title", "year", "publisher", "isbn"]


def parse_bib(text):
    """Tolerant BibTeX parser. Returns a list of entry dicts."""
    entries = []
    i = 0
    n = len(text)
    while True:
        at = text.find("@", i)
        if at == -1:
            break
        brace = text.find("{", at)
        if brace == -1:
            break
        etype = text[at + 1:brace].strip().lower()
        # Walk to the matching closing brace, tracking depth.
        depth = 1
        j = brace + 1
        while j < n and depth > 0:
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
            j += 1
        body = text[brace + 1:j - 1]
        comma = body.find(",")
        citekey = body[:comma].strip() if comma != -1 else body.strip()
        fields = _parse_fields(body[comma + 1:]) if comma != -1 else {}
        entries.append({"type": etype, "citekey": citekey, "fields": fields})
        i = j
    return entries


def _parse_fields(body):
    fields = {}
    i, n = 0, len(body)
    while i < n:
        eq = body.find("=", i)
        if eq == -1:
            break
        name = body[i:eq].strip().strip(",").lower()
        # Find the value: either {..}, "..", or a bareword up to comma.
        k = eq + 1
        while k < n and body[k] in " \t\r\n":
            k += 1
        if k < n and body[k] in "{\"":
            opener = body[k]
            closer = "}" if opener == "{" else "\""
            depth = 1
            m = k + 1
            while m < n and depth > 0:
                if opener == "{" and body[m] == "{":
                    depth += 1
                elif body[m] == closer:
                    depth -= 1
                m += 1
            value = body[k + 1:m - 1]
            i = body.find(",", m)
        else:
            comma = body.find(",", k)
            end = comma if comma != -1 else n
            value = body[k:end].strip()
            i = comma
        if name:
            fields[name] = " ".join(value.split())
        if i == -1:
            break
        i += 1
    return fields


def format_entry(entry):
    fields = entry.get("fields", {})
    ordered = [k for k in _FIELD_ORDER if k in fields]
    ordered += sorted(k for k in fields if k not in _FIELD_ORDER)
    lines = ["@{}{{{},".format(entry.get("type", "book"), entry["citekey"])]
    for idx, k in enumerate(ordered):
        comma = "," if idx < len(ordered) - 1 else ""
        lines.append("  {} = {{{}}}{}".format(k, fields[k], comma))
    lines.append("}")
    return "\n".join(lines)


def write_bib(entries):
    return "\n\n".join(format_entry(e) for e in entries) + "\n"
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd librarian-skill && python -m pytest scripts/tests/test_bibtools.py -v`
Expected: PASS (all tests so far).

- [ ] **Step 6: Commit**

```bash
cd librarian-skill
git add scripts/bibtools.py scripts/tests/test_bibtools.py scripts/tests/fixtures/sample.bib
git commit -m "feat: bibtools BibTeX parse/format/write round-trip"
```

---

## Task 3: Citekey minting (AuthorYear + collision)

**Files:**
- Modify: `librarian-skill/scripts/bibtools.py`
- Modify: `librarian-skill/scripts/tests/test_bibtools.py`

**Interfaces:**
- Consumes: nothing new.
- Produces:
  - `surname_of(author_field: str) -> str` — first author's surname, letters only. Handles `"Last, First"`, `"First Last"`, and multiple authors joined by `" and "`.
  - `base_citekey(author_field: str, year) -> str` — `Surname + str(year)` (e.g. `MacIntyre1981`); year coerced to its 4-digit form.
  - `mint_citekey(author_field: str, year, existing) -> str` — returns `base_citekey` if free; otherwise appends `a`, `b`, `c`, … until unused. `existing` is any iterable of taken keys.

- [ ] **Step 1: Write the failing test**

Append to `test_bibtools.py`:

```python
def test_surname_of_handles_formats():
    assert bibtools.surname_of("MacIntyre, Alasdair") == "MacIntyre"
    assert bibtools.surname_of("Alasdair MacIntyre") == "MacIntyre"
    assert bibtools.surname_of("Charles Taylor and Hubert Dreyfus") == "Taylor"
    assert bibtools.surname_of("{Anonymous}") == "Anonymous"


def test_base_citekey():
    assert bibtools.base_citekey("MacIntyre, Alasdair", "1981") == "MacIntyre1981"
    assert bibtools.base_citekey("Alasdair MacIntyre", 1981) == "MacIntyre1981"


def test_mint_citekey_collisions():
    existing = {"MacIntyre1981"}
    assert bibtools.mint_citekey("MacIntyre, Alasdair", 1981, existing) == "MacIntyre1981a"
    existing.add("MacIntyre1981a")
    assert bibtools.mint_citekey("MacIntyre, Alasdair", 1981, existing) == "MacIntyre1981b"
    assert bibtools.mint_citekey("Charles Taylor", 1989, existing) == "Taylor1989"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd librarian-skill && python -m pytest scripts/tests/test_bibtools.py -k "surname or citekey" -v`
Expected: FAIL — `AttributeError: module 'bibtools' has no attribute 'surname_of'`.

- [ ] **Step 3: Write minimal implementation**

Append to `bibtools.py`:

```python
import string as _string


def surname_of(author_field):
    first = author_field.split(" and ")[0].strip().strip("{}")
    if "," in first:
        last = first.split(",")[0]
    else:
        parts = first.split()
        last = parts[-1] if parts else first
    return "".join(c for c in last if c.isalnum())


def base_citekey(author_field, year):
    y = "".join(c for c in str(year) if c.isdigit())[:4]
    return surname_of(author_field) + y


def mint_citekey(author_field, year, existing):
    existing = set(existing)
    base = base_citekey(author_field, year)
    if base not in existing:
        return base
    for letter in _string.ascii_lowercase:
        cand = base + letter
        if cand not in existing:
            return cand
    # Exhausted a–z: fall back to numeric suffixes.
    i = 1
    while base + str(i) in existing:
        i += 1
    return base + str(i)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd librarian-skill && python -m pytest scripts/tests/test_bibtools.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd librarian-skill
git add scripts/bibtools.py scripts/tests/test_bibtools.py
git commit -m "feat: bibtools AuthorYear citekey minting with collision suffixes"
```

---

## Task 4: Upsert entry + Goodreads CSV import

**Files:**
- Modify: `librarian-skill/scripts/bibtools.py`
- Modify: `librarian-skill/scripts/tests/test_bibtools.py`
- Create: `librarian-skill/scripts/tests/fixtures/goodreads.csv`

**Interfaces:**
- Consumes: `mint_citekey`, `normalize_isbn`.
- Produces:
  - `upsert_entry(entries: list[dict], entry: dict) -> list[dict]` — if an entry with the same `citekey` exists, merge its `fields` (new values win) in place; otherwise append. Returns the same list.
  - `parse_goodreads_csv(text: str) -> list[dict]` — maps each row to `{"title", "authors": list[str], "year": str, "isbn": str, "rating": str, "status": str, "pages": str, "publisher": str, "date_finished": str}`. `status` maps Goodreads `Exclusive Shelf`: `read`→`read`, `currently-reading`→`reading`, anything else→`to-read`.

- [ ] **Step 1: Create the fixture**

Create `librarian-skill/scripts/tests/fixtures/goodreads.csv`:

```csv
Book Id,Title,Author,Additional Authors,ISBN,ISBN13,My Rating,Publisher,Number of Pages,Year Published,Original Publication Year,Date Read,Exclusive Shelf
1,After Virtue,Alasdair MacIntyre,,"=""0268006113""","=""9780268006112""",5,University of Notre Dame Press,286,1984,1981,2023/04/01,read
2,Sources of the Self,Charles Taylor,,"="""""","=""9780674824263""",0,Harvard University Press,624,1992,1989,,to-read
```

- [ ] **Step 2: Write the failing test**

Append to `test_bibtools.py`:

```python
def test_upsert_entry_adds_and_merges():
    entries = [{"type": "book", "citekey": "A2000", "fields": {"title": "Old", "year": "2000"}}]
    bibtools.upsert_entry(entries, {"type": "book", "citekey": "A2000",
                                    "fields": {"title": "New", "isbn": "123"}})
    assert len(entries) == 1
    assert entries[0]["fields"]["title"] == "New"      # overwritten
    assert entries[0]["fields"]["year"] == "2000"      # preserved
    assert entries[0]["fields"]["isbn"] == "123"       # added
    bibtools.upsert_entry(entries, {"type": "book", "citekey": "B2001", "fields": {}})
    assert len(entries) == 2


def test_parse_goodreads_csv():
    with open(os.path.join(FIX, "goodreads.csv")) as f:
        books = bibtools.parse_goodreads_csv(f.read())
    assert len(books) == 2
    b = books[0]
    assert b["title"] == "After Virtue"
    assert b["authors"] == ["Alasdair MacIntyre"]
    assert b["year"] == "1981"                  # Original Publication Year preferred
    assert b["isbn"] == "9780268006112"         # ISBN13 preferred, unwrapped
    assert b["rating"] == "5"
    assert b["status"] == "read"
    assert books[1]["status"] == "to-read"
    assert books[1]["rating"] == ""             # 0 rating becomes empty
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd librarian-skill && python -m pytest scripts/tests/test_bibtools.py -k "upsert or goodreads" -v`
Expected: FAIL — `AttributeError`.

- [ ] **Step 4: Write minimal implementation**

Append to `bibtools.py`:

```python
import csv as _csv
import io as _io


def upsert_entry(entries, entry):
    for existing in entries:
        if existing["citekey"] == entry["citekey"]:
            existing.setdefault("fields", {}).update(entry.get("fields", {}))
            if entry.get("type"):
                existing["type"] = entry["type"]
            return entries
    entries.append(entry)
    return entries


_SHELF = {"read": "read", "currently-reading": "reading"}


def parse_goodreads_csv(text):
    books = []
    reader = _csv.DictReader(_io.StringIO(text))
    for row in reader:
        authors = [row.get("Author", "").strip()]
        extra = row.get("Additional Authors", "").strip()
        if extra:
            authors += [a.strip() for a in extra.split(",") if a.strip()]
        authors = [a for a in authors if a]
        year = (row.get("Original Publication Year") or row.get("Year Published") or "").strip()
        isbn = normalize_isbn(row.get("ISBN13") or "") or normalize_isbn(row.get("ISBN") or "") or ""
        rating = row.get("My Rating", "0").strip()
        rating = "" if rating in ("", "0") else rating
        shelf = row.get("Exclusive Shelf", "").strip()
        books.append({
            "title": row.get("Title", "").strip(),
            "authors": authors,
            "year": year,
            "isbn": isbn,
            "rating": rating,
            "status": _SHELF.get(shelf, "to-read"),
            "pages": row.get("Number of Pages", "").strip(),
            "publisher": row.get("Publisher", "").strip(),
            "date_finished": row.get("Date Read", "").strip().replace("/", "-"),
        })
    return books
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd librarian-skill && python -m pytest scripts/tests/test_bibtools.py -v`
Expected: PASS (all tests).

- [ ] **Step 6: Commit**

```bash
cd librarian-skill
git add scripts/bibtools.py scripts/tests/test_bibtools.py scripts/tests/fixtures/goodreads.csv
git commit -m "feat: bibtools upsert and Goodreads CSV import"
```

---

## Task 5: bibtools CLI dispatcher

**Files:**
- Modify: `librarian-skill/scripts/bibtools.py`
- Modify: `librarian-skill/scripts/tests/test_bibtools.py`

**Interfaces:**
- Consumes: all functions from Tasks 1–4.
- Produces — the command surface the mode playbooks shell out to:
  - `python scripts/bibtools.py check-isbn <isbn>` → prints normalized ISBN, exit 0 if valid; prints `invalid` to stderr, exit 1 otherwise.
  - `python scripts/bibtools.py parse <file.bib>` → prints a JSON array of entry dicts.
  - `python scripts/bibtools.py mint-key --bib <file.bib> --author "<author>" --year <year>` → prints the citekey (reads existing keys from the `.bib` if it exists).
  - `python scripts/bibtools.py upsert --bib <file.bib> --json '<entry-json>'` → upserts and writes the file; mints a citekey when the JSON omits one; prints the citekey. Entry JSON shape: `{"type":"book","citekey":"<optional>","author":"<for minting>","fields":{...}}`.
  - `python scripts/bibtools.py import-goodreads <file.csv>` → prints a JSON array of book dicts.

- [ ] **Step 1: Write the failing test**

Append to `test_bibtools.py`:

```python
import subprocess, json

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "bibtools.py")


def _run(*args):
    return subprocess.run([sys.executable, SCRIPT, *args],
                          capture_output=True, text=True)


def test_cli_check_isbn():
    ok = _run("check-isbn", "978-0-268-03504-4")
    assert ok.returncode == 0
    assert ok.stdout.strip() == "9780268035044"
    bad = _run("check-isbn", "978-0-268-03504-5")
    assert bad.returncode == 1


def test_cli_parse(tmp_path):
    bib = tmp_path / "x.bib"
    bib.write_text("@book{A2000,\n  author = {Doe, Jane},\n  title = {T},\n  year = {2000}\n}\n")
    out = _run("parse", str(bib))
    assert out.returncode == 0
    data = json.loads(out.stdout)
    assert data[0]["citekey"] == "A2000"


def test_cli_upsert_mints_key(tmp_path):
    bib = tmp_path / "x.bib"
    bib.write_text("")
    payload = json.dumps({"type": "book", "author": "Alasdair MacIntyre",
                          "fields": {"author": "MacIntyre, Alasdair",
                                     "title": "After Virtue", "year": "1981"}})
    out = _run("upsert", "--bib", str(bib), "--json", payload)
    assert out.returncode == 0
    assert out.stdout.strip() == "MacIntyre1981"
    assert "MacIntyre1981" in bib.read_text()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd librarian-skill && python -m pytest scripts/tests/test_bibtools.py -k "cli" -v`
Expected: FAIL — the script has no CLI yet (no output / nonzero on unknown args).

- [ ] **Step 3: Write minimal implementation**

Append to `bibtools.py`:

```python
import argparse as _argparse
import json as _json
import sys as _sys
import os as _os


def _read_bib(path):
    if path and _os.path.exists(path):
        with open(path) as f:
            return parse_bib(f.read())
    return []


def main(argv=None):
    parser = _argparse.ArgumentParser(prog="bibtools")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("check-isbn"); p.add_argument("isbn")
    p = sub.add_parser("parse"); p.add_argument("bibfile")
    p = sub.add_parser("mint-key")
    p.add_argument("--bib", required=True); p.add_argument("--author", required=True)
    p.add_argument("--year", required=True)
    p = sub.add_parser("upsert")
    p.add_argument("--bib", required=True); p.add_argument("--json", required=True)
    p = sub.add_parser("import-goodreads"); p.add_argument("csvfile")

    args = parser.parse_args(argv)

    if args.cmd == "check-isbn":
        if valid_isbn(args.isbn):
            print(normalize_isbn(args.isbn)); return 0
        print("invalid", file=_sys.stderr); return 1

    if args.cmd == "parse":
        with open(args.bibfile) as f:
            print(_json.dumps(parse_bib(f.read()), indent=2)); return 0

    if args.cmd == "mint-key":
        existing = {e["citekey"] for e in _read_bib(args.bib)}
        print(mint_citekey(args.author, args.year, existing)); return 0

    if args.cmd == "upsert":
        entries = _read_bib(args.bib)
        payload = _json.loads(args.json)
        citekey = payload.get("citekey")
        if not citekey:
            existing = {e["citekey"] for e in entries}
            author = payload.get("author") or payload.get("fields", {}).get("author", "")
            year = payload.get("fields", {}).get("year", "")
            citekey = mint_citekey(author, year, existing)
        entry = {"type": payload.get("type", "book"), "citekey": citekey,
                 "fields": payload.get("fields", {})}
        upsert_entry(entries, entry)
        with open(args.bib, "w") as f:
            f.write(write_bib(entries))
        print(citekey); return 0

    if args.cmd == "import-goodreads":
        with open(args.csvfile) as f:
            print(_json.dumps(parse_goodreads_csv(f.read()), indent=2)); return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the full suite**

Run: `cd librarian-skill && python -m pytest scripts/tests/test_bibtools.py -v`
Expected: PASS (all tests across Tasks 1–5).

- [ ] **Step 5: Commit**

```bash
cd librarian-skill
git add scripts/bibtools.py scripts/tests/test_bibtools.py
git commit -m "feat: bibtools CLI dispatcher (check-isbn, parse, mint-key, upsert, import-goodreads)"
```

---

## Task 6: Book-note, config, and CLAUDE templates

**Files:**
- Create: `librarian-skill/templates/BookNote.md`
- Create: `librarian-skill/templates/config.md`
- Create: `librarian-skill/templates/CLAUDE.md`

**Interfaces:**
- Consumes: nothing executable.
- Produces: the `{{token}}` contract the mode playbooks fill. BookNote tokens: `{{title}} {{authors}} {{year}} {{isbn}} {{citekey}} {{status}} {{rating}} {{date_started}} {{date_finished}} {{publisher}} {{pages}}`. config tokens: `{{books_folder}} {{bib_path}} {{vault_name}}`. CLAUDE tokens: `{{books_folder}} {{bib_path}} {{vault_name}}`.

- [ ] **Step 1: Write the BookNote template**

Create `librarian-skill/templates/BookNote.md`:

```markdown
---
type: book-note
title: "{{title}}"
authors: [{{authors}}]
year: {{year}}
isbn: "{{isbn}}"
citekey: {{citekey}}
status: {{status}}
rating: {{rating}}
date_started: {{date_started}}
date_finished: {{date_finished}}
publisher: "{{publisher}}"
pages: {{pages}}
fullAI: false
mixedAI: true
---

# {{title}}

⚡ *Stub created by the librarian. Replace this line with your own notes.*

## Summary

## Notes

## Quotes
```

- [ ] **Step 2: Write the config template**

Create `librarian-skill/templates/config.md`:

```markdown
---
type: librarian-config
books_folder: "{{books_folder}}"
bib_path: "{{bib_path}}"
vault_name: "{{vault_name}}"
fullAI: true
mixedAI: false
---

> [!ai] This file is maintained by the librarian skill. It records where book notes live and where the .bib file is.

- **Book notes folder:** `{{books_folder}}`
- **BibTeX file:** `{{bib_path}}`
- **Vault name:** `{{vault_name}}`
```

- [ ] **Step 3: Write the CLAUDE template**

Create `librarian-skill/templates/CLAUDE.md`:

```markdown
<!-- Authored by the librarian skill. Hand-curated operating contract; not an /init dump. -->

# Librarian operating contract

This vault uses the **librarian** skill to keep book notes and a BibTeX file in sync.

- **Source of truth:** the vault. Book notes drive `{{bib_path}}`. The .bib is never the authority.
- **Never auto-delete** a .bib entry or a note. Report orphans; let the human decide.
- **Citekeys:** AuthorYear (e.g. `MacIntyre1981`), `a`/`b`/`c` on collision. Minted by `scripts/bibtools.py`.
- **Book notes** live in `{{books_folder}}/` and carry `type: book-note` frontmatter.
- **Provenance:** mark AI authorship — `fullAI`/`mixedAI` frontmatter, `⚡ ` on AI lines in mixed notes.
- **Obsidian CLI:** always pass `vault={{vault_name}}`.
- The collating Base is `{{books_folder}}/Books.base`.
```

- [ ] **Step 4: Validate the template frontmatter parses**

Run:
```bash
cd librarian-skill && python - <<'PY'
import re
for p in ["templates/BookNote.md", "templates/config.md"]:
    t = open(p).read()
    assert t.startswith("---"), p
    fm = t.split("---", 2)[1]
    assert "type:" in fm, p
    print("ok", p)
PY
```
Expected: `ok templates/BookNote.md` and `ok templates/config.md`.

- [ ] **Step 5: Commit**

```bash
cd librarian-skill
git add templates/BookNote.md templates/config.md templates/CLAUDE.md
git commit -m "feat: book-note, config, and CLAUDE templates"
```

---

## Task 7: Books.base template

**Files:**
- Create: `librarian-skill/templates/Books.base`

**Interfaces:**
- Consumes: the book-note YAML fields from Task 6 (`status`, `rating`, `year`, `authors`).
- Produces: a valid `.base` with views: All Books (table), shelves grouped by `status`, by `rating`, and by `year`.

- [ ] **Step 1: Write the Base**

Create `librarian-skill/templates/Books.base`:

```yaml
filters:
  and:
    - 'type == "book-note"'

formulas:
  status_icon: 'if(status == "reading", "📖", if(status == "read", "✅", if(status == "abandoned", "🚫", "📚")))'

properties:
  authors:
    displayName: Authors
  year:
    displayName: Year
  status:
    displayName: Status
  rating:
    displayName: Rating
  formula.status_icon:
    displayName: ""

views:
  - type: table
    name: "All Books"
    order:
      - formula.status_icon
      - file.name
      - authors
      - year
      - status
      - rating

  - type: table
    name: "By Shelf"
    groupBy:
      property: status
      direction: ASC
    order:
      - file.name
      - authors
      - year
      - rating

  - type: table
    name: "By Rating"
    filters:
      and:
        - 'rating'
    groupBy:
      property: rating
      direction: DESC
    order:
      - file.name
      - authors
      - year

  - type: table
    name: "By Year"
    groupBy:
      property: year
      direction: DESC
    order:
      - file.name
      - authors
      - status
```

- [ ] **Step 2: Validate the Base is well-formed YAML**

Run:
```bash
cd librarian-skill && python - <<'PY'
import yaml
d = yaml.safe_load(open("templates/Books.base"))
names = [v["name"] for v in d["views"]]
assert names == ["All Books", "By Shelf", "By Rating", "By Year"], names
# every formula. reference in views/properties must be defined
defined = {"formula." + k for k in d.get("formulas", {})}
for v in d["views"]:
    for o in v.get("order", []):
        if o.startswith("formula."):
            assert o in defined, o
print("ok Books.base", names)
PY
```
Expected: `ok Books.base ['All Books', 'By Shelf', 'By Rating', 'By Year']`. (If `yaml` is unavailable, `pip install pyyaml` in the dev env — it is not a runtime dependency of the skill.)

- [ ] **Step 3: Commit**

```bash
cd librarian-skill
git add templates/Books.base
git commit -m "feat: Books.base collating template with shelf views"
```

---

## Task 8: Conventions and provenance references

**Files:**
- Create: `librarian-skill/references/conventions.md`
- Create: `librarian-skill/references/provenance.md`

**Interfaces:**
- Consumes: the templates (Task 6–7) and `bibtools.py` CLI surface (Task 5).
- Produces: the shared rules every mode reads first. No executable output.

- [ ] **Step 1: Write provenance.md**

Create `librarian-skill/references/provenance.md` with this exact content structure (adapt from the Generous Ledger pattern):

- Frontmatter schema: two booleans `fullAI` / `mixedAI`; the 3-category table (Full AI / Mixed AI / Full human); the rule that both-true is invalid → treat as Full AI.
- How to set them via the obsidian CLI `property:set` (show the exact command with `vault=<vault-name>`).
- Inline marking: Mixed notes prefix every AI line with `⚡ `; Full-AI notes use a single `> [!ai] …` banner and NO per-line prefix; Full-human notes get no markers and the body is never edited.
- Which category to use: book notes created by **New book**/**Import** start **Mixed AI** (human will add their own notes); generated reports (audit `_Health.md`) and `config.md` are **Full AI**.
- A "self-check before finishing any write" list (4 items).

- [ ] **Step 2: Write conventions.md**

Create `librarian-skill/references/conventions.md` covering, in order:

1. **The Library folder** — default `Library/`, configurable; recorded in `Library/config.md` (`books_folder`, `bib_path`, `vault_name`). Every mode reads `config.md` first to learn the paths; if it is missing, route to Setup.
2. **Book-note schema** — reproduce the YAML field list from the spec (`type: book-note`, `title`, `authors` list, `year`, `isbn`, `citekey`, `status` enum `to-read|reading|read|abandoned`, `rating` 1–5 optional, `date_started`, `date_finished`, `publisher`, `pages`). State that **`citekey` is the join key** between a note and its `.bib` entry.
3. **Citekey rules** — AuthorYear + `a`/`b`/`c` collision; always minted by `bibtools.py`, never by hand.
4. **The bibtools CLI** — list the five commands verbatim from Task 5's Produces block, each with one example invocation. State that all `.bib` reads/writes go through this script.
5. **Vault I/O** — use the `obsidian-cli` skill; always pass `vault=<vault-name>` (read it from `config.md`); reproduce the create/read/append/property:set/search cheat-sheet lines. Note that `.bib` and CSV files are read/written directly on disk (they are not vault notes), and that long note bodies may be written directly to `<vault root>/<path>`.
6. **Safety rules** — never auto-delete a `.bib` entry or note; confirm + show a diff before enrichment writes and bulk operations.
7. **Detecting the vault root / vault name** — the vault root is the directory containing `.obsidian/`; the vault name can be read from `~/Library/Application Support/obsidian/obsidian.json`.

- [ ] **Step 3: Verify both files exist and are non-trivial**

Run:
```bash
cd librarian-skill && wc -l references/conventions.md references/provenance.md
```
Expected: both files present with substantive line counts (> 30 each).

- [ ] **Step 4: Commit**

```bash
cd librarian-skill
git add references/conventions.md references/provenance.md
git commit -m "docs: conventions and provenance references"
```

---

## Task 9: Enrichment reference

**Files:**
- Create: `librarian-skill/references/enrichment.md`

**Interfaces:**
- Consumes: `bibtools.py check-isbn` (Task 5).
- Produces: the metadata-lookup playbook used by New book and Import.

- [ ] **Step 1: Write enrichment.md**

Create `librarian-skill/references/enrichment.md` covering:

- **Goal:** given an ISBN or a title (+ optional author), fill missing book-note fields (authors, year, publisher, pages) before writing.
- **Sources, in order:** Open Library first (no API key), Google Books as fallback. Provide the exact WebFetch URLs:
  - Open Library by ISBN: `https://openlibrary.org/api/books?bibkeys=ISBN:<isbn>&format=json&jscmd=data`
  - Open Library search by title: `https://openlibrary.org/search.json?title=<url-encoded-title>&author=<author>&limit=5`
  - Google Books: `https://www.googleapis.com/books/v1/volumes?q=isbn:<isbn>` or `q=intitle:<title>+inauthor:<author>`
- **Field mapping** from each source's JSON to the book-note fields (authors → `authors` list, publish year → `year`, publishers → `publisher`, number_of_pages → `pages`).
- **Validation:** run `python scripts/bibtools.py check-isbn <isbn>` before trusting an ISBN; if invalid, ask the user.
- **Confirmation rule (Global Constraint):** present the fetched fields as a diff against what the user gave and **confirm before writing**. On lookup failure or ambiguous matches, fall back to manual entry — never block note creation.

- [ ] **Step 2: Verify**

Run: `cd librarian-skill && grep -c "openlibrary.org" references/enrichment.md`
Expected: ≥ 2.

- [ ] **Step 3: Commit**

```bash
cd librarian-skill
git add references/enrichment.md
git commit -m "docs: metadata enrichment reference"
```

---

## Task 10: Setup and New-book mode references

**Files:**
- Create: `librarian-skill/references/mode-setup.md`
- Create: `librarian-skill/references/mode-new-book.md`

**Interfaces:**
- Consumes: templates (Tasks 6–7), conventions/provenance (Task 8), enrichment (Task 9), bibtools CLI (Task 5).
- Produces: two mode playbooks the router dispatches to.

- [ ] **Step 1: Write mode-setup.md**

Create `librarian-skill/references/mode-setup.md`. Goal: establish the library in a vault. Steps:

1. Determine the vault name (ask, or read `obsidian.json`) and confirm the books folder (default `Library/`) and `.bib` path (default `<books_folder>/library.bib`).
2. Write `Library/config.md` from `templates/config.md` (Full AI; set `fullAI: true`, `mixedAI: false`).
3. Create `Library/Books.base` from `templates/Books.base`.
4. Create the `.bib` file if absent (empty file on disk at `bib_path`).
5. Offer to write/merge the vault-root `CLAUDE.md` from `templates/CLAUDE.md`.
6. Idempotency: if `config.md` already exists, read it and **augment** rather than overwrite.
7. Finish: summarize what was created and how to add the first book (point to New book).

Include the exact obsidian CLI commands (with `vault=<vault-name>`) for each create, and provenance `property:set` calls.

- [ ] **Step 2: Write mode-new-book.md**

Create `librarian-skill/references/mode-new-book.md`. Goal: create one book note and log it in the `.bib`. Steps:

1. Read `Library/config.md` for paths; if missing → Setup.
2. Gather the book: accept an ISBN, a title, or a title+author. Run enrichment (`references/enrichment.md`) to fill fields; validate ISBN with `bibtools.py check-isbn`; **confirm the fields** with the user.
3. Mint/insert the `.bib` entry: run
   `python scripts/bibtools.py upsert --bib "<bib_path>" --json '{"type":"book","author":"<author>","fields":{"author":"<author>","title":"<title>","year":"<year>","isbn":"<isbn>","publisher":"<publisher>"}}'`
   and capture the printed citekey.
4. Create the note from `templates/BookNote.md` at `<books_folder>/<sanitized title>.md`, filling tokens including the captured `citekey`; `authors` as a YAML inline list. Apply provenance (Mixed AI).
5. Confirm to the user, linking the new note and noting the citekey.

Show the exact CLI and obsidian commands.

- [ ] **Step 3: Verify**

Run: `cd librarian-skill && grep -l "bibtools.py upsert" references/mode-new-book.md`
Expected: the file path prints (the upsert command is present).

- [ ] **Step 4: Commit**

```bash
cd librarian-skill
git add references/mode-setup.md references/mode-new-book.md
git commit -m "docs: setup and new-book mode references"
```

---

## Task 11: Sync and Import mode references

**Files:**
- Create: `librarian-skill/references/mode-sync.md`
- Create: `librarian-skill/references/mode-import.md`

**Interfaces:**
- Consumes: conventions (Task 8), bibtools CLI (Task 5), templates (Task 6).
- Produces: the two sync-direction playbooks.

- [ ] **Step 1: Write mode-sync.md (vault → .bib)**

Create `librarian-skill/references/mode-sync.md`. Goal: ensure every book note is represented in the `.bib`. Steps:

1. Read `config.md`; list all notes with `type: book-note` (obsidian search / read the folder).
2. For each note: if it has a `citekey`, ensure a matching `.bib` entry exists and its fields match; if it has no `citekey`, mint one via `bibtools.py upsert` (which mints when none is supplied) and **write the returned citekey back into the note's frontmatter** with `property:set`.
3. Build each `upsert --json` payload from the note's frontmatter (author from `authors[0]`, title, year, isbn, publisher).
4. **Never delete** `.bib` entries here. Entries with no note are out of scope for Sync — they are reported by Audit.
5. Produce a change summary (added / updated / unchanged counts) and show it to the user.

- [ ] **Step 2: Write mode-import.md (.bib → vault, + bulk)**

Create `librarian-skill/references/mode-import.md`. Goal: create notes from external sources on command. Two paths:

- **From a `.bib`:** run `python scripts/bibtools.py parse "<bib_path>"`; for each entry, check whether a note with that `citekey` exists (search frontmatter); for entries lacking a note, create one from `templates/BookNote.md` (Mixed AI), mapping `fields.author/title/year/...` and copying the existing `citekey` (do not re-mint). Confirm the batch before writing.
- **From Goodreads/Zotero:** Goodreads CSV → `python scripts/bibtools.py import-goodreads <csv>` yields book dicts; Zotero exports to BibTeX → treat as the `.bib` path above. For each imported book, optionally enrich, then `upsert` into the `.bib` (to mint a citekey) and create the note. This is a **bulk operation**: show a diff/summary and confirm before writing anything.

State the safety rule: confirm-before-write, and a final change summary.

- [ ] **Step 3: Verify**

Run: `cd librarian-skill && grep -l "bibtools.py parse" references/mode-import.md && grep -l "Never delete" references/mode-sync.md`
Expected: both file paths print.

- [ ] **Step 4: Commit**

```bash
cd librarian-skill
git add references/mode-sync.md references/mode-import.md
git commit -m "docs: sync and import mode references"
```

---

## Task 12: Audit and Cite mode references

**Files:**
- Create: `librarian-skill/references/mode-audit.md`
- Create: `librarian-skill/references/mode-cite.md`

**Interfaces:**
- Consumes: conventions (Task 8), bibtools CLI (Task 5).
- Produces: the audit and citation playbooks.

- [ ] **Step 1: Write mode-audit.md**

Create `librarian-skill/references/mode-audit.md`. Goal: report integrity problems; write `<books_folder>/_Health.md` (Full AI). Checks:

1. **Validation/lint:** every `book-note` has required fields (`title`, `authors`, `year`, `citekey`); ISBNs pass `bibtools.py check-isbn`; `status` is one of the allowed enum values; `year` is a plausible 3–4 digit number.
2. **Duplicate detection:** same `isbn` or same normalized title+author across multiple notes; duplicate `citekey`s.
3. **Orphan reconciliation:** parse the `.bib` (`bibtools.py parse`); list `.bib` entries with no note and notes with no `.bib` entry. **Report only — never delete.**
4. Write `_Health.md` with one section per check, each listing offending notes as wikilinks, plus a summary count line. Apply Full-AI provenance (banner, no per-line `⚡`).

- [ ] **Step 2: Write mode-cite.md**

Create `librarian-skill/references/mode-cite.md`. Goal: emit a formatted citation for a book or a selection. Steps:

1. **Always ask which style** (APA / MLA / Chicago / other) — there is no default (Global Constraint).
2. Resolve the target: a single note (by title/citekey) or a set (e.g., all `read` books).
3. Read the fields from the note frontmatter (or the `.bib` entry), and format the citation(s) in the chosen style.
4. Output the formatted citation(s) to the user; offer to append them to a note if asked (Mixed AI if so).

- [ ] **Step 3: Verify**

Run: `cd librarian-skill && grep -l "_Health.md" references/mode-audit.md && grep -li "always ask" references/mode-cite.md`
Expected: both file paths print.

- [ ] **Step 4: Commit**

```bash
cd librarian-skill
git add references/mode-audit.md references/mode-cite.md
git commit -m "docs: audit and cite mode references"
```

---

## Task 13: SKILL.md router

**Files:**
- Create: `librarian-skill/SKILL.md`

**Interfaces:**
- Consumes: all references (Tasks 8–12) and templates (Tasks 6–7).
- Produces: the entrypoint with YAML frontmatter (`name`, `description`) and the mode-routing table.

- [ ] **Step 1: Write SKILL.md**

Create `librarian-skill/SKILL.md`:

```markdown
---
name: librarian
description: Connect an Obsidian vault of book notes to a BibTeX .bib file. Use when the user wants to set up a book library in a vault, add or import books, keep notes and a .bib in sync, audit the library, build a collating Base, or export citations. Standalone; vault is the source of truth.
---

# Librarian

A standalone skill that bridges an Obsidian vault and a BibTeX `.bib` file. **The vault is
canonical** — book notes drive the `.bib`. State lives visibly in the vault under a
configurable folder (default `Library/`), never in this skill.

Deterministic work (`.bib` parse/write, citekey minting, ISBN checks, CSV import) is done by
`scripts/bibtools.py` (Python stdlib only). Vault I/O goes through the **obsidian-cli** skill.

## Always read first

- `references/conventions.md` — folder layout, book-note schema, citekey rules, the bibtools
  CLI, and vault I/O. Every mode starts by reading `Library/config.md` for paths; if it is
  missing, route to Setup.
- `references/provenance.md` — how to mark AI authorship; applies to every write.

## Design principles

1. **Vault canonical** — notes drive the `.bib`; `.bib`→vault is explicit, on command.
2. **Never auto-delete** a `.bib` entry or a note — report orphans instead.
3. **Transparency** — everything Markdown; mark AI authorship.
4. **Determinism where it matters** — citekeys, parsing, ISBNs go through `bibtools.py`.

## Routing — pick the mode, then read its playbook

- **Setup** — "set up / start a library", record paths, install template + Base.
  → `references/mode-setup.md`
- **New book** — add one book (from ISBN/title), enrich, log in `.bib`.
  → `references/mode-new-book.md`
- **Sync** — reconcile notes into the `.bib` (vault → .bib).
  → `references/mode-sync.md`
- **Import** — create notes from a `.bib`, or bulk-import Goodreads/Zotero.
  → `references/mode-import.md`
- **Audit** — validation/lint, duplicates, orphans; write `_Health.md`.
  → `references/mode-audit.md`
- **Cite** — export a formatted citation (always asks the style).
  → `references/mode-cite.md`

If intent is ambiguous, ask which mode before acting.

## Templates

`templates/` holds `BookNote.md`, `Books.base`, `config.md`, and `CLAUDE.md`. Modes load
these, fill `{{tokens}}`, and write them into the vault with provenance applied.

## Enrichment

`references/enrichment.md` covers ISBN/title lookup (Open Library → Google Books) used by
New book and Import. Always confirm fetched fields before writing.
```

- [ ] **Step 2: Validate frontmatter**

Run:
```bash
cd librarian-skill && python - <<'PY'
t = open("SKILL.md").read()
fm = t.split("---", 2)[1]
assert "name: librarian" in fm
assert "description:" in fm
print("ok SKILL.md")
PY
```
Expected: `ok SKILL.md`.

- [ ] **Step 3: Commit**

```bash
cd librarian-skill
git add SKILL.md
git commit -m "feat: librarian SKILL.md router"
```

---

## Task 14: Librarian agent definition

**Files:**
- Create: `librarian-skill/agents/librarian.md`

**Interfaces:**
- Consumes: the `librarian` skill (Task 13).
- Produces: a subagent definition installable to `.claude/agents/` or a plugin's `agents/`.

- [ ] **Step 1: Write the agent**

Create `librarian-skill/agents/librarian.md`:

```markdown
---
name: librarian
description: Use to run librarian jobs against an Obsidian vault + .bib — set up a library, add or import books, sync notes into the .bib, audit the library, build the Base, or export citations. Invoke for delegated or scheduled library maintenance.
tools: Read, Write, Edit, Bash, WebFetch
---

You are the librarian agent. You operate the **librarian** skill to keep an Obsidian vault
of book notes in sync with a BibTeX `.bib` file.

On every task:

1. Invoke the `librarian` skill and follow its router. Read `references/conventions.md` and
   `references/provenance.md` first, then the matching mode playbook.
2. Read `Library/config.md` for the books folder, `.bib` path, and vault name. If it is
   missing, run Setup (confirm paths with whoever dispatched you first).
3. The **vault is canonical**. Never auto-delete a `.bib` entry or a note — report orphans.
4. Use `scripts/bibtools.py` for all `.bib` parsing/writing, citekey minting, and ISBN
   checks. Use the obsidian CLI (always `vault=<vault-name>`) for vault I/O.
5. Confirm before enrichment writes and bulk operations; show a diff. Apply provenance to
   every write.
6. Finish with a concise change summary (added / updated / reported).
```

- [ ] **Step 2: Validate frontmatter**

Run:
```bash
cd librarian-skill && python - <<'PY'
t = open("agents/librarian.md").read()
fm = t.split("---", 2)[1]
for key in ("name:", "description:", "tools:"):
    assert key in fm, key
print("ok agents/librarian.md")
PY
```
Expected: `ok agents/librarian.md`.

- [ ] **Step 3: Commit**

```bash
cd librarian-skill
git add agents/librarian.md
git commit -m "feat: librarian agent definition"
```

---

## Task 15: README, end-to-end smoke test, and manual verification checklist

**Files:**
- Create: `librarian-skill/README.md`
- Create: `librarian-skill/scripts/tests/test_end_to_end.py`

**Interfaces:**
- Consumes: everything.
- Produces: install docs and an integration test exercising the full CLI flow on a temp `.bib`.

- [ ] **Step 1: Write the end-to-end test**

Create `librarian-skill/scripts/tests/test_end_to_end.py`:

```python
import sys, os, subprocess, json

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "bibtools.py")


def _run(*args):
    return subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True)


def test_full_flow(tmp_path):
    bib = tmp_path / "library.bib"
    bib.write_text("")
    # Add two books by the same author+year -> collision suffix.
    for title in ["After Virtue", "Whose Justice"]:
        payload = json.dumps({"type": "book", "author": "Alasdair MacIntyre",
                              "fields": {"author": "MacIntyre, Alasdair",
                                         "title": title, "year": "1981"}})
        out = _run("upsert", "--bib", str(bib), "--json", payload)
        assert out.returncode == 0
    keys = [e["citekey"] for e in json.loads(_run("parse", str(bib)).stdout)]
    assert "MacIntyre1981" in keys and "MacIntyre1981a" in keys
```

- [ ] **Step 2: Run the full suite**

Run: `cd librarian-skill && python -m pytest scripts/tests/ -v`
Expected: PASS (all unit tests + the end-to-end test).

- [ ] **Step 3: Write README.md**

Create `librarian-skill/README.md` covering: what the skill does (one paragraph); the vault-canonical model; install (copy `librarian-skill/` into your skills directory; copy `agents/librarian.md` into `.claude/agents/` to enable the agent); how to start (`/librarian` → Setup); the `bibtools.py` CLI command list; how to run the dev tests (`python -m pytest scripts/tests/ -v`); and a **manual verification checklist** for each mode:

- Setup creates `Library/config.md`, `Library/Books.base`, and the `.bib`.
- New book creates a note with a citekey and a matching `.bib` entry.
- Sync writes a missing `.bib` entry for a hand-made note and back-fills its citekey.
- Import creates notes for `.bib` entries that lack them; Goodreads CSV import works.
- Audit writes `_Health.md` listing orphans/duplicates without deleting anything.
- Cite asks for a style and prints a formatted citation.
- Open `Books.base` in Obsidian and confirm the four views render.

- [ ] **Step 4: Commit**

```bash
cd librarian-skill
git add README.md scripts/tests/test_end_to_end.py
git commit -m "docs: README, manual verification checklist, end-to-end test"
```

---

## Self-Review (completed by plan author)

**Spec coverage:**
- Book-notes template w/ YAML (title, author, year, ISBN, citekey) → Task 6 ✓
- Vault → .bib reconcile (vault canonical) → Task 11 (Sync) ✓
- .bib → vault note creation on command → Task 11 (Import) ✓
- Obsidian Base collating notes → Task 7 ✓
- ISBN/title auto-enrichment → Task 9 ✓
- Validation/lint report → Task 12 (Audit) ✓
- Duplicate detection → Task 12 (Audit) ✓
- Reading status + rating → Task 6 (schema) + Task 7 (shelf views) ✓
- Formatted citation export (always asks style) → Task 12 (Cite) ✓
- Health/orphan report → Task 12 (Audit) ✓
- Bulk import (Goodreads/Zotero) → Task 4 + Task 11 (Import) ✓
- AuthorYear citekeys + collision → Task 3 ✓
- Hybrid scripts vs LLM → Tasks 1–5 (scripts) + Tasks 8–13 (LLM playbooks) ✓
- Standalone + Ledger conventions (provenance, state-in-vault, obsidian-cli) → Tasks 8, 13 ✓
- Configurable folder, default Library/ → Task 6 (config) + Task 10 (Setup) ✓
- The librarian agent → Task 14 ✓

**Placeholder scan:** Script/template/Base/SKILL/agent tasks contain complete content. Reference-prose tasks (8–12) carry detailed content specifications with all hard facts (exact CLI commands, URLs, schemas, enum values) — no vague TODOs.

**Type consistency:** CLI command names, function signatures, and JSON payload shapes are consistent across Tasks 1–5 and referenced identically in Tasks 10–14 (`upsert --bib --json`, `parse`, `check-isbn`, `mint-key`, `import-goodreads`). Book-note field names match across Tasks 6, 7, 11, 12.

No gaps found.
