# Mode: Setup

Goal: establish the librarian in a vault — record the paths, install the book-note Base,
create the `.bib` file, and (optionally) write the vault operating contract. After Setup,
the other modes have everything they need.

Read `references/conventions.md` and `references/provenance.md` first.

## 1. Determine paths

Ask the user, or detect, three things:

- **Vault name** — ask, or read `~/Library/Application Support/obsidian/obsidian.json` (the
  vault-name token usually equals the vault folder's basename). Needed for every
  `obsidian vault=<vault-name> …` call.
- **Books folder** — where book notes live. Default `Library/`. The librarian's own files
  (`config.md`, `Books.base`) live at the `Library/` root; by default book notes live there
  too. Confirm or let the user choose another folder.
- **`.bib` path** — the BibTeX file on disk. Default `<books_folder>/library.bib`.

## 2. Idempotency check

```bash
obsidian vault=<vault-name> read path="Library/config.md"
```

If it returns content, the library already exists → **augment**: read the recorded paths
and only create what is missing. Never overwrite an existing `config.md`. If it errors /
not found, this is a fresh setup → proceed.

## 3. Write `Library/config.md`

Fill `templates/config.md` (`{{books_folder}}`, `{{bib_path}}`, `{{vault_name}}`) and create
it. This file is **Full AI**:

```bash
obsidian vault=<vault-name> create path="Library/config.md" content="<filled config template>" silent
obsidian vault=<vault-name> property:set name="fullAI"  value="true"  path="Library/config.md"
obsidian vault=<vault-name> property:set name="mixedAI" value="false" path="Library/config.md"
```

## 4. Create the Base

Copy `templates/Books.base` to `Library/Books.base`. Because a `.base` file is YAML with
many special characters, write it directly to disk at `<vault root>/Library/Books.base`
rather than passing it as a CLI argument. (`.base` files are not provenance-marked notes.)

## 5. Create the `.bib` file if absent

The `.bib` lives on disk, not in the vault. Create an empty file at `bib_path` if one does
not already exist (do not clobber an existing `.bib`):

```bash
[ -f "<bib_path>" ] || : > "<bib_path>"
```

## 6. Offer the vault operating contract

Offer to write `CLAUDE.md` at the **vault root** from `templates/CLAUDE.md` (fill
`{{books_folder}}`, `{{bib_path}}`, `{{vault_name}}`) so future Claude sessions inherit the
rules. If a `CLAUDE.md` already exists, propose **merging** these rules in rather than
overwriting. This is a plain root file, not a vault note, so provenance frontmatter does not
apply — but keep its "authored by the librarian skill" comment.

## 7. Finish

Summarize what was created (`config.md`, `Books.base`, the `.bib`, and `CLAUDE.md` if
accepted), and tell the user how to add their first book — point them to **New book** (e.g.
"give me an ISBN or a title and I'll create the note"). Remind them that any book note they
edit by hand is treated as human-authored (bare lines, no `⚡`).
