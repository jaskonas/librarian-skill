# Mode: Import (.bib → vault, and bulk sources)

Goal: create book notes from external sources on command. This is the explicit, opt-in
`.bib`→vault direction (Sync never creates notes). Every Import path is **confirm before
write**.

Read `references/conventions.md` and `references/provenance.md` first. Load
`Library/config.md` for `books_folder`, `bib_path`, `vault_name`.

## Path A — from a `.bib` file

1. Parse the file:

   ```bash
   python scripts/bibtools.py parse "<bib_path>"
   ```

2. For each entry, check whether a note with that `citekey` already exists (search
   frontmatter):

   ```bash
   obsidian vault=<vault-name> search query="citekey: <citekey>" limit=1
   ```

3. For entries that **lack a note**, create one from `templates/BookNote.md` (Mixed AI),
   mapping `fields.author` → `authors`, `fields.title` → `title`, `fields.year` → `year`,
   etc., and **copying the existing `citekey` verbatim — do not re-mint it** (the `.bib` is
   the authority for these keys during Import).
4. **Confirm the batch** with the user (list which notes would be created) before writing
   anything.

## Path B — bulk from Goodreads / Zotero

- **Goodreads CSV:** convert the export to book dicts:

  ```bash
  python scripts/bibtools.py import-goodreads <export.csv>
  ```

  Each dict has `title`, `authors`, `year`, `isbn`, `rating`, `status`, `pages`,
  `publisher`, `date_finished`.

- **Zotero:** export from Zotero as **BibTeX**, then treat the resulting file as a `.bib`
  via **Path A**.

For each imported book: optionally enrich (`references/enrichment.md`), then `upsert` it
into the `.bib` (to mint/record a citekey) and create the note from the template, carrying
across `status`, `rating`, etc. where present.

## Safety and reporting

- This is a **bulk operation**: show a diff/summary of everything that would be created or
  changed, and **confirm before writing**. Never write notes or `.bib` entries
  unconfirmed.
- Never overwrite an existing note that already matches a citekey — skip it (or ask).
- Finish with a **change summary**: notes created, entries upserted, items skipped.
