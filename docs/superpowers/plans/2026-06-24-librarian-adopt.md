# Librarian Adopt Mode — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Add an **Adopt** mode that brings existing vault notes under librarian management (stamp `type: book-note` after matching against the `.bib` and interviewing the user), plus a deterministic `match` capability in `bibtools.py`, and wire match-before-mint into New book and Sync.

**Architecture:** A new deterministic matcher in `scripts/bibtools.py` (a `match` CLI command over parsed `.bib` entries) backs a new prose playbook `references/mode-adopt.md`. New book and Sync gain a match-before-mint step. Router and supporting docs are updated.

**Tech Stack:** Python 3 stdlib only (existing `bibtools.py`); pytest for dev tests; Markdown playbooks; obsidian-cli for vault I/O.

## Global Constraints

- **Book-only (`@book`)**: Adopt never stamps or touches non-book material.
- **Vault canonical**; confirm before writing; never auto-delete a `.bib` entry or note.
- **Match-before-mint**: reuse an existing citekey (note's own, or a matched `.bib` entry's) before minting a new `AuthorYear` key.
- **`bibtools.py` is Python 3 stdlib only.** `pytest` is dev-only.
- **Notes are adopted in place** (not relocated); the Base collates by `type`, not folder.
- **Provenance on adoption**: set `mixedAI: true` going forward; do NOT retroactively `⚡`-prefix the user's pre-existing lines; only newly AI-added lines get `⚡`.
- Existing `match_entries` scoring: ISBN-equal → 100; normalized-title equal → 60, contained → 40; author-surname match → +30; threshold 40.

## File Structure

```
scripts/bibtools.py              # + normalize_title, match_entries, `match` CLI (Tasks 1-2)
scripts/tests/test_bibtools.py   # + matcher + CLI tests (Tasks 1-2)
references/mode-adopt.md         # new playbook (Task 3)
references/mode-new-book.md      # + match-before-mint step (Task 4)
references/mode-sync.md          # + match-before-mint step (Task 4)
SKILL.md                         # + Adopt route (Task 5)
references/mode-setup.md         # offer Adopt at the end (Task 5)
references/conventions.md        # mention Adopt + matcher (Task 5)
README.md                        # Adopt in mode table + checklist (Task 5)
```

---

## Task 1: `normalize_title` + `match_entries`

**Files:**
- Modify: `scripts/bibtools.py`
- Modify: `scripts/tests/test_bibtools.py`

**Interfaces:**
- Consumes: `normalize_isbn`, `surname_of` (existing).
- Produces:
  - `normalize_title(s: str) -> str` — lowercase, strip a leading `the`/`a`/`an`, drop non-alphanumerics, collapse whitespace.
  - `match_entries(entries, isbn=None, title=None, author=None) -> list[dict]` — ranked `[{"citekey","score","fields"}, …]` for entries scoring ≥ 40.

- [ ] **Step 1: Write the failing test** — append to `test_bibtools.py`:

```python
def test_normalize_title():
    assert bibtools.normalize_title("The Great Gatsby!") == "great gatsby"
    assert bibtools.normalize_title("A Theory of Justice") == "theory of justice"
    assert bibtools.normalize_title("") == ""


def _entries():
    return [
        {"type": "book", "citekey": "MacIntyre1981",
         "fields": {"author": "MacIntyre, Alasdair", "title": "After Virtue",
                    "year": "1981", "isbn": "9780268006112"}},
        {"type": "book", "citekey": "Taylor1989",
         "fields": {"author": "Taylor, Charles", "title": "Sources of the Self", "year": "1989"}},
    ]


def test_match_by_isbn_is_definitive():
    res = bibtools.match_entries(_entries(), isbn="978-0-268-00611-2")
    assert res[0]["citekey"] == "MacIntyre1981"
    assert res[0]["score"] == 100


def test_match_by_title_and_author():
    res = bibtools.match_entries(_entries(), title="The Sources of the Self", author="Charles Taylor")
    assert res[0]["citekey"] == "Taylor1989"
    assert res[0]["score"] == 90  # contained title (40) + surname (30)... see scoring


def test_match_exact_title_no_author():
    res = bibtools.match_entries(_entries(), title="After Virtue")
    assert res[0]["citekey"] == "MacIntyre1981"
    assert res[0]["score"] == 60


def test_match_none():
    assert bibtools.match_entries(_entries(), title="Being and Time", author="Heidegger") == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m pytest scripts/tests/test_bibtools.py -k "normalize_title or match" -v`
Expected: FAIL — `AttributeError: module 'bibtools' has no attribute 'normalize_title'`.

- [ ] **Step 3: Implement** — append to `bibtools.py`:

```python
def normalize_title(s):
    if not s:
        return ""
    s = s.lower()
    s = re.sub(r"^(the|a|an)\s+", "", s)
    s = re.sub(r"[^a-z0-9 ]", "", s)
    return " ".join(s.split())


def match_entries(entries, isbn=None, title=None, author=None):
    norm_isbn = normalize_isbn(isbn) if isbn else None
    norm_title = normalize_title(title) if title else None
    want_surname = surname_of(author).lower() if author else None
    results = []
    for e in entries:
        f = e.get("fields", {})
        score = 0
        e_isbn = normalize_isbn(f.get("isbn", "")) if f.get("isbn") else None
        if norm_isbn and e_isbn and e_isbn == norm_isbn:
            score = 100
        elif norm_title:
            e_title = normalize_title(f.get("title", ""))
            if e_title and e_title == norm_title:
                score = 60
            elif e_title and (norm_title in e_title or e_title in norm_title):
                score = 40
            if score and want_surname and surname_of(f.get("author", "")).lower() == want_surname:
                score += 30
        if score >= 40:
            results.append({"citekey": e["citekey"], "score": score, "fields": f})
    results.sort(key=lambda r: r["score"], reverse=True)
    return results
```

Note for the test author: with `title="The Sources of the Self"` → normalized `sources of the self`; entry title `Sources of the Self` → `sources of the self`; these are **equal** after article-strip, so score is 60 + 30 = 90. The `test_match_by_title_and_author` comment about "contained" is informational; the assertion `== 90` is what matters.

- [ ] **Step 4: Run to verify pass**

Run: `python3 -m pytest scripts/tests/test_bibtools.py -v`
Expected: PASS (all, including the new five).

- [ ] **Step 5: Commit**

```bash
git add scripts/bibtools.py scripts/tests/test_bibtools.py
git commit -m "feat: bibtools match_entries + normalize_title (match-before-mint core)"
```

---

## Task 2: `match` CLI command

**Files:**
- Modify: `scripts/bibtools.py`
- Modify: `scripts/tests/test_bibtools.py`

**Interfaces:**
- Consumes: `match_entries`, `_read_bib` (existing).
- Produces: `python scripts/bibtools.py match --bib <f> [--isbn X] [--title T] [--author A]` → prints a JSON array of best matches (empty `[]` when none).

- [ ] **Step 1: Write the failing test** — append to `test_bibtools.py`:

```python
def test_cli_match(tmp_path):
    bib = tmp_path / "x.bib"
    bib.write_text("@book{Taylor1989,\n  author = {Taylor, Charles},\n  title = {Sources of the Self},\n  year = {1989}\n}\n")
    out = _run("match", "--bib", str(bib), "--title", "Sources of the Self", "--author", "Charles Taylor")
    assert out.returncode == 0
    res = json.loads(out.stdout)
    assert res[0]["citekey"] == "Taylor1989"
    # no-match prints empty array
    out2 = _run("match", "--bib", str(bib), "--title", "Being and Time")
    assert json.loads(out2.stdout) == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m pytest scripts/tests/test_bibtools.py -k "cli_match" -v`
Expected: FAIL — argparse error / unknown command `match`.

- [ ] **Step 3: Implement** — in `bibtools.py`, register the subparser inside `main()` alongside the others, and handle it. Add the subparser registration:

```python
    p = sub.add_parser("match")
    p.add_argument("--bib", required=True)
    p.add_argument("--isbn"); p.add_argument("--title"); p.add_argument("--author")
```

and the handler (place it with the other `if args.cmd == …` blocks, before `return 2`):

```python
    if args.cmd == "match":
        entries = _read_bib(args.bib)
        res = match_entries(entries, isbn=args.isbn, title=args.title, author=args.author)
        print(_json.dumps(res, indent=2)); return 0
```

- [ ] **Step 4: Run the full suite**

Run: `python3 -m pytest scripts/tests/ -v`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add scripts/bibtools.py scripts/tests/test_bibtools.py
git commit -m "feat: bibtools match CLI command"
```

---

## Task 3: `mode-adopt.md` playbook

**Files:**
- Create: `references/mode-adopt.md`

**Interfaces:**
- Consumes: conventions, provenance, enrichment, bibtools `parse`/`match`/`upsert`.
- Produces: the Adopt mode playbook.

- [ ] **Step 1: Write `references/mode-adopt.md`** covering, in order:

1. **Goal & preconditions** — bring existing notes under management by stamping
   `type: book-note`. Read `conventions.md`/`provenance.md`; load `Library/config.md` (if
   missing → Setup). Book-only: never adopt/stamp non-book material.
2. **Build the `.bib` index** — `python scripts/bibtools.py parse "<bib_path>"`; keep it for
   matching.
3. **Gather candidates** — the union, excluding notes already `type: book-note`:
   - notes in folder(s) the user names (ask which),
   - notes with frontmatter `author`/`authors`/`isbn` or a tag `#book`/`#reading`
     (`obsidian search`),
   - notes whose title/author matches a `.bib` entry (per step 5's `match`).
   De-duplicate.
4. **Stage 1 — shortlist** — present the candidate list, flagging which already match a
   `.bib` entry; the user checks which are genuinely book notes (quick yes/no).
5. **Stage 2 — interview each confirmed note** — for each: extract probable fields from
   frontmatter/title/body; run
   `python scripts/bibtools.py match --bib "<bib_path>" --title "<t>" --author "<a>" --isbn "<i>"`
   to find existing entries; show the user the fields + any match (and its citekey); the user
   confirms/corrects title/authors/year/ISBN, approves/rejects the match, optionally sets
   status/rating. Offer enrichment (`references/enrichment.md`) for gaps.
6. **Resolve the citekey (match-before-mint)** — reuse the note's own `citekey` if present →
   else the approved match's citekey → else `upsert` with citekey omitted to mint a fresh one.
7. **Write in place** — set `type: book-note` and the confirmed fields on the note via
   `property:set` (note is **not moved**). Provenance: `obsidian property:set` `fullAI=false`,
   `mixedAI=true`; do NOT `⚡`-prefix the user's existing body lines; only mark new AI-added
   lines. Then ensure the `.bib` has the entry (`upsert`, reusing the resolved citekey).
8. **Summary** — adopted / matched-to-existing / newly-minted / skipped counts.

Show the exact `bibtools.py` and `obsidian` commands (with `vault=<vault-name>`).

- [ ] **Step 2: Verify**

Run: `grep -l "bibtools.py match" references/mode-adopt.md && grep -l "property:set name=\"type\"" references/mode-adopt.md`
Expected: both print the path. (If the second grep is empty, ensure the playbook shows stamping `type` via property:set.)

- [ ] **Step 3: Commit**

```bash
git add references/mode-adopt.md
git commit -m "docs: adopt mode playbook"
```

---

## Task 4: Match-before-mint in New book and Sync

**Files:**
- Modify: `references/mode-new-book.md`
- Modify: `references/mode-sync.md`

**Interfaces:**
- Consumes: bibtools `match`.
- Produces: a match step before each mint.

- [ ] **Step 1: Edit `mode-new-book.md`** — in the `.bib` step (before the `upsert` that
mints), insert: run
`python scripts/bibtools.py match --bib "<bib_path>" --isbn "<isbn>" --title "<title>" --author "<author>"`
first. If a confident match is returned, show it to the user and, on confirmation, reuse that
entry's citekey (pass it in the `upsert` payload as `"citekey"`) instead of minting a new key.
Only mint (omit `citekey`) when there is no match. State that this prevents a duplicate `.bib`
entry for a book already present.

- [ ] **Step 2: Edit `mode-sync.md`** — in the reconcile step, for a note **without** a
citekey, run `match` against the `.bib` first; if a confident match exists, reuse that entry's
citekey (and write it back into the note's frontmatter) instead of minting; surface
"matched to existing entry" in the change summary. Notes that already have a citekey are
unchanged.

- [ ] **Step 3: Verify**

Run: `grep -l "bibtools.py match" references/mode-new-book.md references/mode-sync.md`
Expected: both paths print.

- [ ] **Step 4: Commit**

```bash
git add references/mode-new-book.md references/mode-sync.md
git commit -m "docs: match-before-mint in new-book and sync"
```

---

## Task 5: Wire Adopt into the router and supporting docs

**Files:**
- Modify: `SKILL.md`
- Modify: `references/mode-setup.md`
- Modify: `references/conventions.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: `references/mode-adopt.md`.
- Produces: discoverability of Adopt.

- [ ] **Step 1: `SKILL.md`** — add an **Adopt** route to the routing list:
`- **Adopt** — bring existing vault notes under management (stamp type, match the .bib, interview). → references/mode-adopt.md`.

- [ ] **Step 2: `mode-setup.md`** — in the Finish section, offer to run **Adopt** if the
vault may already contain book notes ("I can scan existing notes and bring them under
management — want to run Adopt now?").

- [ ] **Step 3: `conventions.md`** — in the Scope or modes overview, note that book notes are
identified solely by `type: book-note`, and that **Adopt** is how pre-existing notes acquire
it. Mention `bibtools.py match` in the bibtools CLI list.

- [ ] **Step 4: `README.md`** — add **Adopt** to the modes table ("Bring existing notes under
management: match the .bib, interview, stamp type") and a checklist line ("Adopt finds a
hand-made note, matches it to the .bib or mints a key, and stamps `type: book-note` in
place").

- [ ] **Step 5: Verify**

Run: `grep -l "Adopt" SKILL.md references/mode-setup.md references/conventions.md README.md && grep -l "bibtools.py match" references/conventions.md`
Expected: paths print.

- [ ] **Step 6: Commit**

```bash
git add SKILL.md references/mode-setup.md references/conventions.md README.md
git commit -m "docs: wire Adopt into router, setup, conventions, README"
```

---

## Self-Review

- Adopt mode (candidate detection union, two-stage interview, match-before-mint, in-place stamping, provenance) → Tasks 3, 5 ✓
- Deterministic `.bib` matcher + CLI → Tasks 1, 2 ✓
- Match-before-mint in New book and Sync → Task 4 ✓
- Book-only preserved; notes not relocated; provenance opt-in without retroactive marking → Task 3 ✓
- No placeholders; matcher code complete; CLI surface consistent (`match --bib --isbn --title --author`) across Tasks 2-5.
