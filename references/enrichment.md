# Metadata Enrichment

How the librarian fills in book metadata it doesn't already have. Used by **New book**
(when the user gives only an ISBN or a title) and by **Import** (to enrich sparse entries
before writing notes).

## Goal

Given an **ISBN**, or a **title** (optionally with an author), look up the missing
book-note fields — `authors`, `year`, `publisher`, `pages` — so the agent can propose a
complete note instead of asking the human to type everything. Enrichment never writes on
its own; it produces a *proposal* the human confirms (see "Confirmation rule" below).

## Sources, in order

Try **Open Library first** (no API key, generous rate limits). Fall back to **Google
Books** only if Open Library returns nothing usable. Fetch these URLs with the **WebFetch**
tool — this is an LLM tool, *not* `bibtools.py`; the script is only for ISBN validation and
`.bib` I/O.

```
# 1a. Open Library — by ISBN (preferred when an ISBN is known)
https://openlibrary.org/api/books?bibkeys=ISBN:<isbn>&format=json&jscmd=data

# 1b. Open Library — search by title (+ optional author) when there is no ISBN
https://openlibrary.org/search.json?title=<url-encoded-title>&author=<url-encoded-author>&limit=5

# 2. Google Books — fallback
https://www.googleapis.com/books/v1/volumes?q=isbn:<isbn>
https://www.googleapis.com/books/v1/volumes?q=intitle:<url-encoded-title>+inauthor:<url-encoded-author>
```

URL-encode title and author values (spaces → `%20`, etc.); omit the `&author=` /
`+inauthor:` segment entirely when no author is known (don't send it empty). When searching
by title, prefer
the result whose title and author best match what the user gave; if several are plausible,
that is an *ambiguous match* — see the fallback rule.

## Field mapping

Map each source's JSON onto the book-note fields:

| Book-note field | Open Library (`jscmd=data`) | Open Library search (`docs[]`) | Google Books (`volumeInfo`) |
|-----------------|-----------------------------|--------------------------------|-----------------------------|
| `authors` (list) | `authors[].name` | `author_name[]` | `authors[]` |
| `year` | year from `publish_date` | `first_publish_year` | year from `publishedDate` |
| `publisher` | `publishers[].name` | `publisher[0]` | `publisher` |
| `pages` | `number_of_pages` | `number_of_pages_median` | `pageCount` |

Extract the 4-digit year from free-form date strings (e.g. `"April 1981"` → `1981`). Keep
`authors` as a list even when there is one author.

## ISBN validation

Before trusting any ISBN — whether the user typed it or a lookup returned it — validate it:

```bash
python scripts/bibtools.py check-isbn <isbn>
```

Exit 0 prints the normalized ISBN (use that normalized form); exit 1 means the ISBN is
invalid — do not store it. Ask the user to re-check the number, or proceed by title search
instead.

## Confirmation rule

The vault is canonical and enrichment data can be wrong (mismatched editions, bad scans).
So:

1. Present the fetched fields as a **diff** against what the user already provided — show
   what would be added or changed, field by field.
2. **Confirm before writing.** Only write the note (and `.bib` entry) after the human
   approves the proposed values.
3. On **lookup failure** (nothing found, network error) or an **ambiguous match** (several
   plausible results), **fall back to manual entry** — ask the user for the missing fields,
   or create the note with what is known. Enrichment must **never block note creation**.
