# Mode: New book

Goal: create one book note in the vault and log its entry in the `.bib`. The vault is
canonical — the note is the source of truth and the `.bib` entry is derived from it.

Read `references/conventions.md` and `references/provenance.md` first.

## 1. Load config

```bash
obsidian vault=<vault-name> read path="Library/config.md"
```

Read `books_folder`, `bib_path`, and `vault_name`. If `config.md` is missing → run
**Setup** first.

## 2. Gather the book

Accept whatever the user has: an **ISBN**, a **title**, or a **title + author**. Then run
metadata enrichment per `references/enrichment.md`:

- Validate any ISBN with `python scripts/bibtools.py check-isbn <isbn>` and use the
  normalized form it prints.
- Fetch missing fields (authors, year, publisher, pages) from Open Library → Google Books.
- **Confirm the fields with the user** (show them as a diff/proposal) before writing
  anything. On lookup failure, fall back to manual entry — never block note creation.

## 3. Insert the `.bib` entry

Upsert the entry; omit `citekey` so the script mints an `AuthorYear` key (with collision
suffix) and prints the key it used:

```bash
python scripts/bibtools.py upsert --bib "<bib_path>" --json '{"type":"book","author":"<author>","fields":{"author":"<author>","title":"<title>","year":"<year>","isbn":"<isbn>","publisher":"<publisher>"}}'
```

Capture the printed **citekey** — it is the join key that ties the note to this entry. The
top-level `"author"` is used only for minting; the `"fields"` object is what gets stored in
the `.bib`.

## 4. Create the note

Fill `templates/BookNote.md`, including the captured `citekey`, and write it to
`<books_folder>/<sanitized title>.md` (replace characters illegal in filenames). Render
`authors` as a YAML inline list (e.g. `authors: ["Alasdair MacIntyre"]`). The note is
**Mixed AI** — the librarian writes the frontmatter and a stub body (each AI line prefixed
`⚡ `), and the human fills in their own summary/notes/quotes.

Fill **every** `{{token}}` — leave none literal in the written YAML. Set `status` to
`to-read` for a new book unless the user says otherwise. Leave the optional fields the user
hasn't given — `rating`, `date_started`, `date_finished`, and any unknown `publisher`/
`pages` — **empty** (e.g. `rating:` with no value), never the literal `{{rating}}`.

```bash
obsidian vault=<vault-name> create path="<books_folder>/<sanitized title>.md" content="<filled BookNote template>" silent
obsidian vault=<vault-name> property:set name="fullAI"  value="false" path="<books_folder>/<sanitized title>.md"
obsidian vault=<vault-name> property:set name="mixedAI" value="true"  path="<books_folder>/<sanitized title>.md"
```

(If the filled body has many special characters, write it directly to
`<vault root>/<books_folder>/<sanitized title>.md` on disk instead.)

## 5. Confirm

Tell the user the note was created — link it (`[[<title>]]`) and state the citekey it was
filed under in the `.bib`.
