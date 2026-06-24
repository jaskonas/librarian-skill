---
name: librarian
description: Connect an Obsidian vault of book notes to a BibTeX .bib file. Use when the user wants to set up a book library in a vault, add or import books, keep notes and a .bib in sync, audit the library, build a collating Base, or export citations. Standalone; vault is the source of truth.
---

# Librarian

A standalone skill that bridges an Obsidian vault and a BibTeX `.bib` file. **The vault is
canonical** — book notes drive the `.bib`. State lives visibly in the vault under a
configurable folder (default `Library/`), never in this skill.

Deterministic work (`.bib` parse/write, citekey minting, ISBN checks, CSV import) is done by
`scripts/bibtools.py` (Python stdlib only). Vault I/O goes through the **obsidian-cli** skill.

**Scope (v1): books only.** The librarian manages `@book` entries and their book notes. A
`.bib` may also contain non-book material (`@article`, `@techreport`, `@misc`, archival
entries, …); the librarian **leaves those untouched** — it never creates notes for them,
never edits them, and never reports them as orphans.

## Always read first

- `references/conventions.md` — folder layout, book-note schema, citekey rules, the bibtools
  CLI, and vault I/O. Every mode starts by reading `Library/config.md` for paths; if it is
  missing, route to Setup.
- `references/provenance.md` — how to mark AI authorship; applies to every write.

## Design principles

1. **Vault canonical** — notes drive the `.bib`; `.bib`→vault is explicit, on command.
2. **Never auto-delete** a `.bib` entry or a note — report orphans instead.
3. **Transparency** — everything Markdown; mark AI authorship.
4. **Determinism where it matters** — citekeys, parsing, ISBNs go through `bibtools.py`.

## Routing — pick the mode, then read its playbook

- **Setup** — "set up / start a library", record paths, install template + Base.
  → `references/mode-setup.md`
- **New book** — add one book (from ISBN/title), enrich, log in `.bib`.
  → `references/mode-new-book.md`
- **Sync** — reconcile notes into the `.bib` (vault → .bib).
  → `references/mode-sync.md`
- **Import** — create notes from a `.bib`, or bulk-import Goodreads/Zotero.
  → `references/mode-import.md`
- **Adopt** — bring existing vault notes under management (stamp `type: book-note`, match
  the `.bib`, interview). → `references/mode-adopt.md`
- **Audit** — validation/lint, duplicates, orphans; write `_Health.md`.
  → `references/mode-audit.md`
- **Cite** — export a formatted citation (always asks the style).
  → `references/mode-cite.md`

If intent is ambiguous, ask which mode before acting.

## Templates

`templates/` holds `BookNote.md`, `Books.base`, `config.md`, and `CLAUDE.md`. Modes load
these, fill `{{tokens}}`, and write them into the vault with provenance applied.

## Enrichment

`references/enrichment.md` covers ISBN/title lookup (Open Library → Google Books) used by
New book and Import. Always confirm fetched fields before writing.
