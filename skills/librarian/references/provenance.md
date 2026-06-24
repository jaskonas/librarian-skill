# Provenance & Transparency Rules

Every book note and generated file the librarian creates or substantially edits MUST
declare its authorship in YAML frontmatter and mark AI-authored content inline. This is
the "machine-intelligence transparency" principle: a reader can always tell what the
agent wrote versus what the human reader wrote about their own books.

## Frontmatter schema

Two booleans define three authorship categories:

```yaml
---
fullAI: false
mixedAI: true
---
```

| `fullAI` | `mixedAI` | Category   | Meaning                                       |
|----------|-----------|------------|------------------------------------------------|
| `true`   | `false`   | Full AI    | Entire file authored by the librarian agent    |
| `false`  | `true`    | Mixed AI   | Human reader + agent collaboration             |
| `false`  | `false`   | Full human | Agent must not modify the body                 |

`fullAI: true` together with `mixedAI: true` is invalid. If you encounter it, treat the
note as Full AI and correct the frontmatter (`mixedAI: false`).

Set frontmatter with the obsidian CLI:

```bash
obsidian vault=<vault-name> property:set name="fullAI" value="false" path="Library/Antifragile.md"
obsidian vault=<vault-name> property:set name="mixedAI" value="true"  path="Library/Antifragile.md"
```

## Inline marking rules

- **Mixed notes (`mixedAI: true`):** Prefix every AI-authored line with `⚡ ` (the
  lightning emoji followed by a space). Leave human-authored lines bare. This gives
  line-level, greppable provenance. When the librarian creates a book-note stub or
  appends metadata, prefix each line it writes:

  ```bash
  obsidian vault=<vault-name> append path="Library/Antifragile.md" content="⚡ *Stub created by the librarian. Replace this line with your own notes.*"
  ```

- **Full-AI notes (`fullAI: true`):** Do NOT prefix every line. Instead place a single
  banner as the first body line, immediately after the frontmatter:

  ```
  > [!ai] This file is maintained by the librarian skill.
  ```

- **Full-human notes:** No markers. Never edit the body. You may read them (e.g. to
  scrape an ISBN or rating out of a note a human wrote from scratch) and copy
  information out into the .bib or a generated report, with appropriate marking there.

## Which category to use

- **Book notes created by New book or Import:** start **Mixed AI** — the librarian
  writes the frontmatter and a stub body (prefixed `⚡ `), and the human is expected to
  add their own summary, notes, and quotes underneath.
- **Generated reports** (e.g. an audit `_Health.md` file) and **`Library/config.md`**:
  **Full AI** — the librarian writes these wholesale and the human is not expected to
  hand-edit them; use the `> [!ai]` banner, no per-line prefixes.
- **Pre-existing book notes the human wrote unassisted:** treat as Full human unless the
  human explicitly opts the note into librarian management (at which point set
  `mixedAI: true` going forward, but do not retroactively mark prior lines).

## Self-check before finishing any write

1. Does the file have `fullAI` and `mixedAI` frontmatter? If not, add it.
2. If Mixed AI: is every AI-authored line prefixed with `⚡ `? Are human lines left bare?
3. If Full AI: is the `> [!ai]` banner present, and are you NOT prefixing individual lines?
4. Never both booleans true — if you see it, fix it to Full AI (`mixedAI: false`).
