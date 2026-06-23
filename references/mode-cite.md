# Mode: Cite

Goal: emit a formatted citation for one book or a set of books.

Read `references/conventions.md` first. Load `Library/config.md` for paths.

## 1. Always ask the style

There is **no default citation style.** Always ask the user which style they want —
**APA**, **MLA**, **Chicago**, or another they name — before producing anything. Do not
assume.

## 2. Resolve the target

Figure out what to cite:

- A **single book** — identified by title or `citekey`.
- A **set** — e.g. "all `read` books", "everything by <author>", or a list the user gives.

Find the matching notes (`obsidian search`), or read the matching entries from the `.bib`
via `python scripts/bibtools.py parse "<bib_path>"`.

## 3. Format

Read the fields (`authors`, `title`, `year`, `publisher`, …) from each note's frontmatter
(or its `.bib` entry) and format the citation(s) in the chosen style. For a set, produce one
citation per book, ordered sensibly (typically alphabetical by first author surname).

## 4. Output

Show the formatted citation(s) to the user. If they ask to save them into a note, append
there as **Mixed AI** (prefix each written line with `⚡ `).

If the target note is **Full human** (`fullAI: false`, `mixedAI: false`), do **not** edit
its body — per `references/provenance.md` the agent never edits human-authored notes. Either
ask the human to opt the note into Mixed AI first, or offer to write the citation into a
separate note instead.
