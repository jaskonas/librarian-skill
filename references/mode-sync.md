# Mode: Sync (vault → .bib)

Goal: ensure every book note in the vault is represented in the `.bib` file. The vault is
canonical — Sync pushes notes *into* the `.bib`, never the other way. (To create notes from
a `.bib`, use **Import**.)

Read `references/conventions.md` and `references/provenance.md` first.

## 1. Load config and list notes

Read `Library/config.md` for `books_folder`, `bib_path`, `vault_name`. Then list every book
note:

```bash
obsidian vault=<vault-name> search query="type: book-note" limit=500
```

(Or read the `books_folder` directly on disk and select files whose frontmatter has
`type: book-note`.)

## 2. Reconcile each note into the `.bib`

For each book note, build an `upsert` payload from its frontmatter — `author` from
`authors[0]`, plus `title`, `year`, `isbn`, `publisher`:

```bash
python scripts/bibtools.py upsert --bib "<bib_path>" --json '{"type":"book","citekey":"<citekey-if-present>","author":"<authors[0]>","fields":{"author":"<authors[0]>","title":"<title>","year":"<year>","isbn":"<isbn>","publisher":"<publisher>"}}'
```

- **Note has a `citekey`:** include it in the payload. `upsert` matches by citekey and
  updates that entry's fields (new values win), or inserts it if absent.
- **Note has no `citekey`:** omit `citekey` from the payload. `upsert` mints an `AuthorYear`
  key (collision-suffixed) and prints it. **Write that key back into the note's
  frontmatter** so the join is permanent:

  ```bash
  obsidian vault=<vault-name> property:set name="citekey" value="<printed citekey>" path="<note path>"
  ```

Track whether each note was **added**, **updated**, or left **unchanged** in the `.bib`.

## 3. Safety

**Never delete** `.bib` entries in Sync. A `.bib` entry that has no corresponding note is
*out of scope here* — do not remove it. Such orphans are surfaced by **Audit**, which lets
the human decide.

## 4. Report

Show the user a change summary: counts of entries **added** / **updated** / **unchanged**,
and the list of notes that had a citekey minted and written back.
