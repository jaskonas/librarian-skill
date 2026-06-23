"""Deterministic helpers for the Obsidian librarian skill.

Standard library only. Exposes a CLI (see main()) that the skill's mode
playbooks shell out to, plus importable functions used by the tests.
"""
import re


def normalize_isbn(raw):
    """Return the bare ISBN digits (trailing X allowed) or None."""
    if raw is None:
        return None
    # Strip Goodreads-style ="..." wrappers and any non-isbn characters.
    s = raw.strip()
    s = re.sub(r'^="?|"?$', "", s)            # leading =" and trailing "
    s = re.sub(r"[\s-]", "", s)               # spaces and hyphens
    s = s.upper()
    if re.fullmatch(r"\d{13}", s):
        return s
    if re.fullmatch(r"\d{9}[\dX]", s):
        return s
    return None


def valid_isbn(raw):
    s = normalize_isbn(raw)
    if s is None:
        return False
    if len(s) == 13:
        total = sum((1 if i % 2 == 0 else 3) * int(d) for i, d in enumerate(s))
        return total % 10 == 0
    # ISBN-10
    total = 0
    for i, ch in enumerate(s):
        val = 10 if ch == "X" else int(ch)
        total += (10 - i) * val
    return total % 11 == 0


_FIELD_ORDER = ["author", "title", "year", "publisher", "isbn"]


def parse_bib(text):
    """Tolerant BibTeX parser. Returns a list of entry dicts."""
    entries = []
    i = 0
    n = len(text)
    while True:
        at = text.find("@", i)
        if at == -1:
            break
        brace = text.find("{", at)
        if brace == -1:
            break
        etype = text[at + 1:brace].strip().lower()
        # Walk to the matching closing brace, tracking depth.
        depth = 1
        j = brace + 1
        while j < n and depth > 0:
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
            j += 1
        body = text[brace + 1:j - 1]
        comma = body.find(",")
        citekey = body[:comma].strip() if comma != -1 else body.strip()
        fields = _parse_fields(body[comma + 1:]) if comma != -1 else {}
        entries.append({"type": etype, "citekey": citekey, "fields": fields})
        i = j
    return entries


def _parse_fields(body):
    fields = {}
    i, n = 0, len(body)
    while i < n:
        eq = body.find("=", i)
        if eq == -1:
            break
        name = body[i:eq].strip().strip(",").lower()
        # Find the value: either {..}, "..", or a bareword up to comma.
        k = eq + 1
        while k < n and body[k] in " \t\r\n":
            k += 1
        if k < n and body[k] in "{\"":
            opener = body[k]
            closer = "}" if opener == "{" else "\""
            depth = 1
            m = k + 1
            while m < n and depth > 0:
                if opener == "{" and body[m] == "{":
                    depth += 1
                elif body[m] == closer:
                    depth -= 1
                m += 1
            value = body[k + 1:m - 1]
            i = body.find(",", m)
        else:
            comma = body.find(",", k)
            end = comma if comma != -1 else n
            value = body[k:end].strip()
            i = comma
        if name:
            fields[name] = " ".join(value.split())
        if i == -1:
            break
        i += 1
    return fields


def format_entry(entry):
    fields = entry.get("fields", {})
    ordered = [k for k in _FIELD_ORDER if k in fields]
    ordered += sorted(k for k in fields if k not in _FIELD_ORDER)
    lines = ["@{}{{{},".format(entry.get("type", "book"), entry["citekey"])]
    for idx, k in enumerate(ordered):
        comma = "," if idx < len(ordered) - 1 else ""
        lines.append("  {} = {{{}}}{}".format(k, fields[k], comma))
    lines.append("}")
    return "\n".join(lines)


def write_bib(entries):
    return "\n\n".join(format_entry(e) for e in entries) + "\n"


import string as _string


def surname_of(author_field):
    first = author_field.split(" and ")[0].strip().strip("{}")
    if "," in first:
        last = first.split(",")[0]
    else:
        parts = first.split()
        last = parts[-1] if parts else first
    return "".join(c for c in last if c.isalnum())


def base_citekey(author_field, year):
    y = "".join(c for c in str(year) if c.isdigit())[:4]
    return surname_of(author_field) + y


def mint_citekey(author_field, year, existing):
    existing = set(existing)
    base = base_citekey(author_field, year)
    if base not in existing:
        return base
    for letter in _string.ascii_lowercase:
        cand = base + letter
        if cand not in existing:
            return cand
    # Exhausted a–z: fall back to numeric suffixes.
    i = 1
    while base + str(i) in existing:
        i += 1
    return base + str(i)
