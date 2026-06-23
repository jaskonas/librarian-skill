# Librarian Conventions

Shared rules for how the librarian skill is laid out in a vault and how every mode
(Setup, New book, Sync, Import, Audit, Cite) operates on it. Read this file — and
`references/provenance.md` — before doing anything else.

## Scope: books only (v1)

The librarian manages **`@book` entries** and their book notes. A `.bib` may also hold
non-book material — `@article`, `@techreport`, `@misc`, archival entries, and so on. Treat
those as **out of scope**: Sync, Import, and Audit must filter to `type == "book"` and must
never create, edit, or report non-book entries. They are the human's to manage by hand.

## The Library folder

All librarian state lives in a top-level folder, by default `Library/` (configurable —
the human may rename it during Setup). Book notes live **directly inside** the books
folder (flat, no subfolder); `config.md` and `Books.base` sit at the `Library/` root
alongside them. Default layout:

```
Library/
├── config.md           Records books_folder, bib_path, vault_name (this file's own home)
├── Books.base          Collating Base view over all book notes
├── After Virtue.md     Individual book notes (one per book, type: book-note)
└── Sources of the Self.md
```

`Library/config.md` is the source of truth for paths: it records `books_folder` (where
book notes live, default `Library/`), `bib_path` (the BibTeX file on disk), and
`vault_name` (for the
obsidian CLI's `vault=` argument). **Every mode reads `config.md` first** to learn these
paths — deterministically, before doing anything else. If `config.md` is missing or
cannot be read, the vault has not been set up yet: route to **Setup** rather than
guessing paths or creating files ad hoc.

## Book-note schema

Each book note carries this YAML frontmatter (see `templates/BookNote.md`):

```yaml
---
type: book-note
title: "<title>"
authors: [<author1>, <author2>, ...]
year: <year>
isbn: "<isbn>"
citekey: <citekey>
status: <to-read|reading|read|abandoned>
rating: <1-5, optional>
date_started: <date, optional>
date_finished: <date, optional>
publisher: "<publisher>"
pages: <pages>
---
```

- `status` is one of exactly four values: `to-read`, `reading`, `read`, `abandoned`.
- `rating` is optional, an integer 1–5.
- `date_started` / `date_finished` are optional dates.
- **`citekey` is the join key** between a book note and its entry in the `.bib` file —
  the same string identifies "this note" and "this BibTeX entry." Never let a note's
  `citekey` drift out of sync with its `.bib` entry.

## Citekey rules

Citekeys follow the `AuthorYear` convention (e.g. `MacIntyre1981`), with a lowercase
`a`/`b`/`c` suffix appended on collision (`MacIntyre1981a`, `MacIntyre1981b`, …).
Citekeys are **always minted by `scripts/bibtools.py mint-key`**, never typed by hand —
this guarantees the collision suffixing stays consistent with whatever is already in the
`.bib` file.

## The bibtools CLI

All `.bib` file reads and writes go through `scripts/bibtools.py`. Never hand-edit a
`.bib` file or reimplement BibTeX parsing — shell out to the script. Its five commands:

```bash
# Validate and normalize an ISBN (exit 0 + prints normalized form if valid; exit 1 + stderr "invalid" otherwise)
python scripts/bibtools.py check-isbn 9780812979688

# Parse a .bib file into a JSON array of entries
python scripts/bibtools.py parse Library/library.bib

# Mint a new citekey (AuthorYear + collision suffix) against an existing .bib file
python scripts/bibtools.py mint-key --bib Library/library.bib --author "Taleb" --year 2012

# Insert or update an entry by citekey (mints one if omitted; prints the citekey used)
python scripts/bibtools.py upsert --bib Library/library.bib --json '{"type":"book","author":"Taleb","fields":{"title":"Antifragile","year":"2012"}}'

# Import a Goodreads export into a JSON array of book dicts
python scripts/bibtools.py import-goodreads export.csv
```

The `upsert` payload shape is `{"type": "book", "citekey": "<optional>", "author":
"<for minting if citekey omitted>", "fields": {...}}`. Omit `citekey` to let the script
mint one; it always prints the citekey actually used so the caller can write it into the
note's frontmatter.

## Vault I/O

Use the **obsidian-cli** skill for everything that lives inside the vault (book notes,
`config.md`, `Books.base`, generated reports). **Always pass `vault=<vault-name>`** as
the first argument — read `vault_name` from `Library/config.md`, or detect it per the
section below if config.md doesn't exist yet (i.e. during Setup).

```bash
# Create a note (silent = don't pop it open)
obsidian vault=<vault-name> create path="Library/Antifragile.md" content="..." silent

# Read a note
obsidian vault=<vault-name> read path="Library/Antifragile.md"

# Append a line
obsidian vault=<vault-name> append path="Library/Antifragile.md" content="⚡ ..."

# Set a frontmatter property
obsidian vault=<vault-name> property:set name="status" value="reading" path="Library/Antifragile.md"

# Search the wider vault
obsidian vault=<vault-name> search query="Taleb" limit=10
```

`.bib` files and Goodreads CSV exports are **not vault notes** — they are read and
written directly on disk via `scripts/bibtools.py`, never through the obsidian CLI.
For long note bodies with many embedded special characters that are awkward to pass as
a CLI argument, write the file directly to `<vault root>/<path>` on disk instead —
Obsidian picks up the change immediately.

## Safety rules

- **Never auto-delete** a `.bib` entry or a book note. If a note and its `.bib` entry
  fall out of sync (e.g. an orphaned citekey, or a note with no matching entry), report
  it and let the human decide — this is what Audit mode is for.
- **Confirm and show a diff** before any enrichment write (e.g. filling in metadata
  fetched from an ISBN lookup) or bulk operation (e.g. a multi-book Import). The vault is
  canonical; the agent proposes changes, the human approves them.

## Detecting the vault root / vault name

The vault root is the directory containing the `.obsidian/` folder. Book notes live on
disk at `<vault root>/<books_folder>/...`, so they can be read, grepped, or diffed
directly when needed. If the vault name is not yet known (no `config.md`, e.g. during
Setup), read it from `~/Library/Application Support/obsidian/obsidian.json` — the
vault-name token there usually equals the vault folder's basename.
