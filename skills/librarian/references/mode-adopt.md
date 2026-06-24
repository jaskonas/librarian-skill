# Mode: Adopt (pre-existing notes → managed book notes)

Goal: bring notes the human already wrote — before the librarian existed in this vault —
under management, by stamping `type: book-note` and the rest of the schema **in place**.
Adopt never moves a note to another folder; it only adds frontmatter (and, optionally, a
few new body lines) to a note that already exists. This is the opposite direction from
**New book** (which creates a note from nothing) and from **Import** (which creates notes
from `.bib`/CSV sources) — here the note is the starting point and is presumed
human-authored.

Read `references/conventions.md` and `references/provenance.md` first. Load
`Library/config.md` for `books_folder`, `bib_path`, `vault_name`. If `config.md` is
missing → run **Setup** first.

> **Book-only scope (v1).** Only adopt notes that are actually about a single book, and
> only match against **`@book`** entries in the `.bib`. Never stamp `type: book-note` on
> a note that isn't a book note (e.g. a reading-list index, a literature-review note
> spanning several books, a movie or article note) — when in doubt, ask the user rather
> than guess.

## 1. Build the `.bib` index

Parse the `.bib` once and keep the result in memory for the rest of this mode — every
candidate gets matched against it in Stage 2:

```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/librarian/scripts/bibtools.py" parse "<bib_path>"
```

## 2. Gather candidates

Assemble the candidate set as the **union** of:

- Notes in folder(s) the user names — ask which folder(s) hold pre-existing book notes if
  they haven't said (e.g. "Reading/", "Library/", the vault root).
- Notes with frontmatter `author` / `authors` / `isbn`, or a tag `#book` / `#reading`:

  ```bash
  obsidian vault=<vault-name> search query="author" limit=500
  obsidian vault=<vault-name> search query="isbn" limit=500
  obsidian vault=<vault-name> search query="#book" limit=500
  obsidian vault=<vault-name> search query="#reading" limit=500
  ```

- Notes whose title or author matches a `.bib` entry — found incidentally while running
  `match` in Stage 2, but a quick title sweep against the parsed `.bib` entries from step 1
  can also surface candidates before the interview starts.

**Exclude** any note that already has `type: book-note` — it's already managed; Adopt has
nothing to do there (use **Sync** or **Audit** instead). De-duplicate the union by path.

## 3. Stage 1 — shortlist confirmation

Present the de-duplicated candidate list to the user, flagging which ones already appear
to match a `.bib` entry (by title, from the sweep above) so they have a hint. Ask a quick
yes/no per note: *is this actually a book note?* Drop anything the user says no to —
don't interview notes that aren't in scope. Keep the confirmed list for Stage 2.

## 4. Stage 2 — interview each confirmed note

For each confirmed note, in turn:

1. **Extract probable fields** from the note's existing frontmatter, title, and body —
   `title` (often the note's filename), `authors`, `isbn`, `year`, `publisher`, `pages`,
   and any existing `citekey`.
2. **Run `match`** to find candidate `.bib` entries for this note:

   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/skills/librarian/scripts/bibtools.py" match --bib "<bib_path>" --title "<t>" --author "<a>" --isbn "<i>"
   ```

   This prints a JSON array of best matches (each with `citekey`, `score`, `fields`),
   or `[]` if nothing matches. Omit whichever of `--isbn` / `--title` / `--author` the
   note doesn't have.
3. **Show the user** the extracted fields plus any match — including its `citekey` — and
   let them confirm or correct `title` / `authors` / `year` / `isbn`, approve or reject the
   proposed match, and optionally set `status` / `rating`. If fields are still missing
   after this, offer enrichment (`references/enrichment.md`) before moving on.

## 5. Resolve the citekey (match-before-mint)

For each adopted note, resolve exactly one citekey, in this priority order:

1. The note's **own** `citekey`, if its frontmatter already has one.
2. Else, the **approved match's** citekey from Stage 2's `match` call.
3. Else, **mint** a fresh one by calling `upsert` with `citekey` omitted:

   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/skills/librarian/scripts/bibtools.py" upsert --bib "<bib_path>" --json '{"type":"book","author":"<author>","fields":{"author":"<author>","title":"<title>","year":"<year>","isbn":"<isbn>","publisher":"<publisher>"}}'
   ```

   Capture the printed citekey.

Never mint a new key when an existing one (the note's own, or a matched `.bib` entry's)
is available — minting is the last resort, not the default.

## 6. Write in place

The note is **not moved or recreated** — only its frontmatter (and, if needed, a short
appended note) changes, at its existing path.

Stamp the schema fields via `property:set`, one call per field:

```bash
obsidian vault=<vault-name> property:set name="type" value="book-note" path="<note path>"
obsidian vault=<vault-name> property:set name="title" value="<title>" path="<note path>"
obsidian vault=<vault-name> property:set name="authors" value="<authors>" path="<note path>"
obsidian vault=<vault-name> property:set name="year" value="<year>" path="<note path>"
obsidian vault=<vault-name> property:set name="isbn" value="<isbn>" path="<note path>"
obsidian vault=<vault-name> property:set name="citekey" value="<resolved citekey>" path="<note path>"
obsidian vault=<vault-name> property:set name="status" value="<status>" path="<note path>"
```

(Set `rating`, `date_started`, `date_finished`, `publisher`, `pages` the same way if the
user supplied them; leave any they didn't give empty rather than guessing.)

**Provenance — adoption is special.** The note's existing body is human-authored and
predates the librarian; Adopt does not retroactively claim it. Stamp the booleans
going forward as Mixed AI:

```bash
obsidian vault=<vault-name> property:set name="fullAI" value="false" path="<note path>"
obsidian vault=<vault-name> property:set name="mixedAI" value="true" path="<note path>"
```

Do **NOT** prefix the note's pre-existing body lines with `⚡ ` — per
`references/provenance.md`, prior human-authored lines stay bare. Only lines the
librarian adds *from this point forward* (e.g. an appended metadata note) get the `⚡ `
prefix:

```bash
obsidian vault=<vault-name> append path="<note path>" content="⚡ *Adopted into the librarian on <date>; frontmatter added.*"
```

Then ensure the `.bib` has the entry, reusing the resolved citekey so this write is an
update rather than an insert when the entry already existed:

```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/librarian/scripts/bibtools.py" upsert --bib "<bib_path>" --json '{"type":"book","citekey":"<resolved citekey>","author":"<author>","fields":{"author":"<author>","title":"<title>","year":"<year>","isbn":"<isbn>","publisher":"<publisher>"}}'
```

Adopted notes are identified purely by `type: book-note`, not by folder — the
`Books.base` collates on that property, so a note adopted in place (wherever it lives)
shows up alongside notes created by New book or Import without needing to move it.

## 7. Summary

Report counts: notes **adopted**, of those how many were **matched to an existing**
`.bib` entry vs. had a key **newly minted**, and how many candidates were **skipped**
(rejected at Stage 1, or abandoned mid-interview). List the adopted notes as wikilinks
(`[[<title>]]`) with the citekey each was filed under.
