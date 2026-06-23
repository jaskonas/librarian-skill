# Obsidian Librarian — Skill & Agent Design

**Date:** 2026-06-22
**Status:** Approved design, pending implementation plan

## Summary

A **librarian** skill (plus a companion **librarian agent**) that bridges an Obsidian
vault and a BibTeX `.bib` file. The vault is the canonical source of truth: book notes
written from a standard template drive the `.bib`. The librarian keeps the two in sync,
can create notes from `.bib` entries on command, enriches metadata from the web, audits
the library for integrity problems, exports citations, and maintains an Obsidian Base that
collates all book notes.

The skill is **standalone** (works in any vault, no dependency on a Generous Ledger) but
**reuses the Generous Ledger conventions**: instance state lives visibly in the vault (not
the skill), AI authorship is marked with provenance, and vault I/O goes through the
`obsidian-cli` skill.

## Core decisions

| Decision | Choice |
|----------|--------|
| Source of truth | **Vault is canonical.** Book notes drive the `.bib`. `.bib`→vault is an explicit on-command operation, never automatic. |
| Citekey scheme | **AuthorYear** (e.g. `MacIntyre1981`), with `a`/`b`/`c` suffix on collision. |
| Coupling | Standalone skill; reuses Ledger conventions (provenance, state-in-vault, obsidian-cli). Not coupled to a Generous Ledger. |
| Vault layout | **Configurable**, default `Library/`. Setup records the book-notes folder and `.bib` path in a vault config file. |
| Implementation style | **Hybrid** — small Python helper(s) for the deterministic, fiddly work (`.bib` parse/write, citekey minting + collision, ISBN checksum). LLM handles judgment, prose, enrichment, conversation. |
| Citation style | **No default** — Cite mode always asks which style (APA / MLA / Chicago / other). |

## v1 feature scope

Included:

- Book-notes template with YAML header.
- Vault → `.bib` reconcile (Sync).
- `.bib` → vault note creation on command (Import).
- Obsidian Base collating all book notes.
- **ISBN/title auto-enrichment** (Open Library → Google Books).
- **Validation / lint report.**
- **Duplicate detection.**
- **Reading status + rating** (drives Base shelf views).
- **Formatted citation export** (style chosen per request).
- **Health / orphan report.**
- **Bulk import** from Goodreads CSV / Zotero export.

Explicitly deferred (not v1): cover-image fetch, auto author pages, topic/theme linking,
series tracking, quote/highlight commonplace book, Generous Ledger Resource integration,
backlink digest.

## Architecture

### Deliverable 1 — the `librarian` skill

Structure mirrors `generous-ledger-skill`:

```
librarian-skill/
  SKILL.md                 # router → modes
  references/
    conventions.md         # folder layout, YAML schema, citekey rules, .bib + obsidian-cli I/O
    provenance.md          # AI-authorship marking (shared pattern)
    enrichment.md          # ISBN/title lookup via Open Library → Google Books
    mode-setup.md
    mode-new-book.md
    mode-sync.md           # vault → .bib reconcile
    mode-import.md         # .bib → vault + bulk Goodreads/Zotero import
    mode-audit.md          # validation/lint + dedup + orphan health report
    mode-cite.md           # formatted citation export
  scripts/
    bibtools.py            # .bib parse/write, citekey mint+collision, ISBN checksum, CSV import parse
  templates/
    BookNote.md            # the book-notes template
    Books.base             # the Obsidian Base
    config.md              # records book-notes folder + .bib path (written into vault)
    CLAUDE.md              # per-vault operating contract written at setup
```

### Deliverable 2 — the `librarian` agent

A subagent definition (markdown with `name` / `description` / `tools` frontmatter) that
loads the skill so whole jobs can be delegated ("librarian, import my .bib and run an
audit") or scheduled. Tools: file Read/Write/Edit, Bash (obsidian-cli + `bibtools.py`),
WebFetch (enrichment).

## Modes (the router)

1. **Setup** — record book-notes folder (default `Library/`) and `.bib` path into a vault
   `config.md`; install the book-note template; create `Books.base`; write a per-vault
   `CLAUDE.md`. Idempotent.
2. **New book** — create a note from an ISBN / title / citekey; enrich the YAML; add the
   `@book` entry to the `.bib`.
3. **Sync (vault → .bib)** — for every book note, ensure a matching `@book` entry exists
   and matches; mint missing citekeys (AuthorYear + collision suffix); report changes.
   *Never deletes `.bib` entries.*
4. **Import (.bib → vault)** — scan a `.bib` and create notes for entries lacking one;
   also bulk-import a Goodreads CSV / Zotero export into notes (+ `.bib`).
5. **Audit** — validation/lint + duplicate detection + orphan reconciliation; write a
   `Library/_Health.md` report.
6. **Cite** — emit a formatted citation (asks style each time) for a book or selection.

If intent is ambiguous, the router asks which mode before acting.

## Data model — book-note YAML

The `citekey` is the join key between a note and its `.bib` entry.

```yaml
---
type: book-note
title:
authors: []          # list
year:
isbn:
citekey:             # AuthorYear, e.g. MacIntyre1981 (a/b/c on collision)
status: to-read      # to-read | reading | read | abandoned
rating:              # 1–5, optional
date_started:
date_finished:
publisher:
pages:
generated_by:        # provenance marker
---
```

## Behavior rules

- **Vault canonical.** Sync only writes `.bib` from notes. Orphan `.bib` entries (no note)
  are *reported* in Audit, never auto-deleted.
- **Matching** is by `citekey`. Audit flags notes/entries whose other fields disagree.
- **Confirm before writing** enrichment data and before any bulk operation — both
  network metadata and CSV exports are error-prone. Show a diff first.
- **ISBN checksum validation**; lookups that fail degrade gracefully to manual fields.
- **Provenance** is applied to every AI-authored write (YAML `generated_by` + line-level
  marks for AI-written prose), per the shared provenance reference.
- **I/O:** vault reads/writes via the `obsidian-cli` skill; `.bib` and CSV via direct file
  I/O through `bibtools.py`.

## The Base (`Books.base`)

Ships with views: all books (table), shelves by `status`, by `rating`, and by
`year` / `author`.

## Error handling

- Never auto-delete `.bib` entries or notes — report instead.
- Validate ISBN checksums; warn on failure.
- Network/enrichment failures fall back to manual entry.
- Bulk operations are confirm-gated and produce a change summary.

## Testing

- `bibtools.py` (the deterministic core) is unit-testable: `.bib` round-trip parse/write,
  citekey minting + collision suffixing, ISBN-13/10 checksum validation, Goodreads/Zotero
  parse.
- A small sample fixture vault + sample `.bib` supports manual verification of each mode,
  with a per-mode checklist.

## Open questions

None blocking. (Helper-script language fixed to Python; cover art / author pages / Ledger
integration consciously deferred.)
