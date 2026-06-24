<!-- Authored by the librarian skill. Hand-curated operating contract; not an /init dump. -->

# Librarian operating contract

This vault uses the **librarian** skill to keep book notes and a BibTeX file in sync.

- **Source of truth:** the vault. Book notes drive `{{bib_path}}`. The .bib is never the authority.
- **Never auto-delete** a .bib entry or a note. Report orphans; let the human decide.
- **Citekeys:** AuthorYear (e.g. `MacIntyre1981`), `a`/`b`/`c` on collision. Minted by `scripts/bibtools.py`.
- **Book notes** live in `{{books_folder}}/` and carry `type: book-note` frontmatter.
- **Provenance:** mark AI authorship — `fullAI`/`mixedAI` frontmatter, `⚡ ` on AI lines in mixed notes.
- **Obsidian CLI:** always pass `vault={{vault_name}}`.
- The collating Base is `Library/Books.base` (at the librarian home root, alongside `config.md`).
