# Librarian

A standalone Claude skill (with a companion agent) that bridges an **Obsidian vault** of
book notes and a **BibTeX `.bib` file**. You keep book notes in your vault; the librarian
keeps the `.bib` in sync with them, creates notes from a `.bib` on command, enriches
metadata from the web, audits the library for integrity problems, exports citations, and
maintains a collating Obsidian Base over all your books.

## Vault-canonical model

**The vault is the source of truth.** Book notes drive the `.bib` — the `.bib` is a derived
export. The `.bib`→vault direction (Import) is always an explicit, opt-in command, never
automatic. The librarian **never auto-deletes** a `.bib` entry or a note; integrity problems
are *reported* (by Audit) for you to resolve. Citekeys follow `AuthorYear` (e.g.
`MacIntyre1981`, with `a`/`b`/`c` suffixes on collision) and are always minted by the helper
script, never by hand.

## Install

1. Copy the `librarian-skill/` directory into your Claude skills directory.
2. To enable the delegated/scheduled agent, copy `agents/librarian.md` into `.claude/agents/`
   (or a plugin's `agents/` directory).

No runtime dependencies beyond Python 3 — `scripts/bibtools.py` uses only the standard
library. Vault I/O uses the `obsidian-cli` skill (Obsidian must be running).

## Getting started

Invoke `/librarian` and ask to **set up** a library. Setup records your books folder
(default `Library/`), your `.bib` path, and your vault name into `Library/config.md`,
installs the `Books.base` collating view, and creates the `.bib` file. After that, "add a
book", "sync", "import my .bib", "audit", and "cite" all work.

## `bibtools.py` CLI

The deterministic core. Modes shell out to these; you can also run them directly:

```bash
python scripts/bibtools.py check-isbn <isbn>                                   # validate + normalize an ISBN
python scripts/bibtools.py parse <file.bib>                                    # .bib → JSON array of entries
python scripts/bibtools.py mint-key --bib <file.bib> --author "<author>" --year <year>   # next free AuthorYear citekey
python scripts/bibtools.py upsert --bib <file.bib> --json '<entry-json>'       # insert/update by citekey (mints if omitted)
python scripts/bibtools.py import-goodreads <file.csv>                         # Goodreads CSV → JSON book dicts
```

`upsert` payload shape: `{"type":"book","citekey":"<optional>","author":"<for minting>","fields":{...}}`.

## Modes

| Mode | What it does |
|------|--------------|
| Setup | Record paths, install the Base, create the `.bib`, write `CLAUDE.md`. |
| New book | Create one note from an ISBN/title, enrich, log it in the `.bib`. |
| Sync | Reconcile vault notes into the `.bib` (vault → `.bib`). |
| Import | Create notes from a `.bib`, or bulk-import a Goodreads CSV / Zotero export. |
| Audit | Validation/lint, duplicate detection, orphan reconciliation → `_Health.md`. |
| Cite | Export a formatted citation (always asks the style). |

## Running the dev tests

```bash
python -m pytest scripts/tests/ -v
```

## Manual verification checklist

Run these against a real vault after install:

- [ ] **Setup** creates `Library/config.md`, `Library/Books.base`, and the `.bib` file.
- [ ] **New book** creates a note with a `citekey` and a matching `.bib` entry.
- [ ] **Sync** writes a missing `.bib` entry for a hand-made note and back-fills its
      `citekey` into the note's frontmatter.
- [ ] **Import** creates notes for `.bib` entries that lack them; Goodreads CSV import
      produces notes.
- [ ] **Audit** writes `_Health.md` listing orphans/duplicates **without deleting** anything.
- [ ] **Cite** asks which style, then prints a formatted citation.
- [ ] Open `Books.base` in Obsidian and confirm the four views (All Books, By Shelf, By
      Rating, By Year) render.
