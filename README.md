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

This repo is a **Claude Code plugin**. The skill (`skills/librarian/`) and the agent
(`agents/librarian.md`) are auto-discovered on install — no manual copying.

- **As a local plugin** (this repo as its own marketplace-less plugin): add it via a
  marketplace that points at this repo, or place the repo under a skills directory; the
  `.claude-plugin/plugin.json` manifest makes it a plugin named `librarian`. Then `/librarian`
  is available and the `librarian` agent is invokable.
- **Nested inside a larger plugin:** drop `skills/librarian/` into the parent plugin's
  `skills/` and `agents/librarian.md` into its `agents/`. No path edits are needed — the
  helper is referenced as `${CLAUDE_PLUGIN_ROOT}/skills/librarian/scripts/bibtools.py`, which
  resolves correctly under either plugin root.

No runtime dependencies beyond Python 3 — the bundled `bibtools.py` uses only the standard
library. Vault I/O uses the `obsidian-cli` skill (Obsidian must be running).

## Getting started

Invoke `/librarian` and ask to **set up** a library. Setup records your books folder
(default `Library/`), your `.bib` path, and your vault name into `Library/config.md`,
installs the `Books.base` collating view, and creates the `.bib` file. After that, "add a
book", "sync", "import my .bib", "audit", and "cite" all work.

## `bibtools.py` CLI

The deterministic core (`skills/librarian/scripts/bibtools.py`). Modes shell out to it via
`${CLAUDE_PLUGIN_ROOT}/skills/librarian/scripts/bibtools.py`; the short form below is for
running it directly from the repo:

```bash
python bibtools.py check-isbn <isbn>                                   # validate + normalize an ISBN
python bibtools.py parse <file.bib>                                    # .bib → JSON array of entries
python bibtools.py mint-key --bib <file.bib> --author "<author>" --year <year>   # next free AuthorYear citekey
python bibtools.py upsert --bib <file.bib> --json '<entry-json>'       # insert/update by citekey (mints if omitted)
python bibtools.py match --bib <file.bib> [--isbn X] [--title T] [--author A]     # best-matching entries (JSON array)
python bibtools.py import-goodreads <file.csv>                         # Goodreads CSV → JSON book dicts
```

`upsert` payload shape: `{"type":"book","citekey":"<optional>","author":"<for minting>","fields":{...}}`.

## Modes

| Mode | What it does |
|------|--------------|
| Setup | Record paths, install the Base, create the `.bib`, write `CLAUDE.md`. |
| New book | Create one note from an ISBN/title, enrich, log it in the `.bib`. |
| Sync | Reconcile vault notes into the `.bib` (vault → `.bib`). |
| Import | Create notes from a `.bib`, or bulk-import a Goodreads CSV / Zotero export. |
| Adopt | Bring existing notes under management: match the .bib, interview, stamp `type`. |
| Audit | Validation/lint, duplicate detection, orphan reconciliation → `_Health.md`. |
| Cite | Export a formatted citation (always asks the style). |

## Running the dev tests

```bash
python -m pytest skills/librarian/scripts/tests/ -v
```

## Manual verification checklist

Run these against a real vault after install:

- [ ] **Setup** creates `Library/config.md`, `Library/Books.base`, and the `.bib` file.
- [ ] **New book** creates a note with a `citekey` and a matching `.bib` entry.
- [ ] **Sync** writes a missing `.bib` entry for a hand-made note and back-fills its
      `citekey` into the note's frontmatter.
- [ ] **Import** creates notes for `.bib` entries that lack them; Goodreads CSV import
      produces notes.
- [ ] **Adopt** finds a hand-made note, matches it to the `.bib` or mints a key, and
      stamps `type: book-note` in place.
- [ ] **Audit** writes `_Health.md` listing orphans/duplicates **without deleting** anything.
- [ ] **Cite** asks which style, then prints a formatted citation.
- [ ] Open `Books.base` in Obsidian and confirm the four views (All Books, By Shelf, By
      Rating, By Year) render.
