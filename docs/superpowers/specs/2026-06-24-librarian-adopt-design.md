# Librarian — Adopt Mode & Match-Before-Mint (Design Addendum)

**Date:** 2026-06-24
**Status:** Approved design, pending implementation
**Extends:** `2026-06-22-obsidian-librarian-design.md`

## Problem

Setup is greenfield: the librarian only ever sees notes that *it* stamped with
`type: book-note` (via New book or Import). A vault that already contains book notes written
by hand — in the user's own format, without that frontmatter — is invisible to the librarian.
There is no path to bring existing notes under management.

Separately, **New book** and **Sync** mint citekeys from author+year without first checking
whether the book is already in the `.bib` under a different key — so they can create
duplicate entries.

## Solution overview

1. A new **Adopt** mode that finds existing notes, matches them against the current `.bib`,
   interviews the user per note, and stamps `type: book-note` + the confirmed fields in
   place.
2. A deterministic **`match`** capability in `bibtools.py` (match a candidate's
   ISBN/title/author against `.bib` entries), used by Adopt and by New book / Sync.
3. **Match-before-mint** everywhere: reuse an existing citekey when the book is already in
   the `.bib`; only mint when the book is genuinely new.

## Adopt flow

The user's mental model: **candidate notes → check `.bib` for plausible entries → confirm
with me per note → add `book-note` frontmatter.**

1. **Build the `.bib` index** — `bibtools.py parse <bib>`, then index entries by ISBN,
   normalized title+author, and citekey.
2. **Gather candidates** — the union of three signals, excluding notes already
   `type: book-note`:
   - notes in folder(s) the user names,
   - notes carrying telltale frontmatter (`author`/`authors`/`isbn`) or a book tag
     (`#book`/`#reading`),
   - notes whose title+author matches a `.bib` entry (via `match`).
   De-duplicate the union.
3. **Stage 1 — shortlist confirmation** — present candidates (flagging which already match a
   `.bib` entry); the user checks which are genuinely book notes. Cheap yes/no per note.
4. **Stage 2 — per-note interview** — for each confirmed note: show extracted fields (from
   frontmatter/title/body) and any `.bib` match (with its citekey); the user confirms/corrects
   title, authors, year, ISBN, approves/rejects the match, and optionally sets status/rating.
   Optional enrichment fills gaps.
5. **Resolve citekey (match-before-mint)** — reuse the note's own `citekey` if present →
   else the matched `.bib` entry's citekey → else mint a fresh `AuthorYear` key (only after
   the match check confirms the book is new).
6. **Write in place** — stamp `type: book-note` and the confirmed fields into the note where
   it already lives (notes are **not** moved; the Base collates by `type`, not folder).
   Provenance: set `mixedAI: true` going forward; do **not** retroactively `⚡`-prefix the
   user's existing lines (per `provenance.md`, prior human lines stay bare; only newly
   AI-added lines are marked). Then `upsert` the entry into the `.bib` if it is not already
   present.
7. **Summary** — adopted / matched-to-existing / newly-minted / skipped counts.

## `bibtools.py match`

A deterministic matcher (stdlib only):

- `normalize_title(s)` — lowercase, strip a leading article (`the`/`a`/`an`), drop
  punctuation, collapse whitespace.
- `match_entries(entries, isbn=None, title=None, author=None)` — score each entry and return
  ranked candidates above a threshold as `[{"citekey", "score", "fields"}, …]`:
  - ISBN equal (normalized) → definitive (score 100).
  - else normalized-title equal → 60, or one normalized title contained in the other → 40;
    plus author surname match → +30. Title must match at least partially to be a candidate.
- CLI: `python scripts/bibtools.py match --bib <f> [--isbn X] [--title T] [--author A]` →
  JSON array of best matches (empty array when none).

## Match-before-mint in New book and Sync

Before upsert-minting, both modes run `match` against the `.bib`. If a confident match
exists, reuse that entry's citekey (New book confirms with the user; Sync surfaces it in its
report) instead of minting a new one — preventing duplicate entries for the same book.

## Out of scope (unchanged)

- Still **book-only** (`@book`); Adopt never stamps or touches non-book material.
- Notes are not relocated; folder layout rules are unchanged.
- Fuzzy/full-text candidate detection beyond the three named signals is not included
  (interview is the false-positive filter).
