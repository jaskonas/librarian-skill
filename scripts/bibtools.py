"""Deterministic helpers for the Obsidian librarian skill.

Standard library only. Exposes a CLI (see main()) that the skill's mode
playbooks shell out to, plus importable functions used by the tests.
"""
import argparse as _argparse
import csv as _csv
import io as _io
import json as _json
import os as _os
import re
import string as _string
import sys as _sys


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


def upsert_entry(entries, entry):
    for existing in entries:
        if existing["citekey"] == entry["citekey"]:
            existing.setdefault("fields", {}).update(entry.get("fields", {}))
            if entry.get("type"):
                existing["type"] = entry["type"]
            return entries
    entries.append(entry)
    return entries


_SHELF = {"read": "read", "currently-reading": "reading"}


def parse_goodreads_csv(text):
    books = []
    reader = _csv.DictReader(_io.StringIO(text))
    for row in reader:
        authors = [row.get("Author", "") or ""]
        authors = [a.strip() for a in authors if a]
        extra = (row.get("Additional Authors", "") or "").strip()
        if extra:
            authors += [a.strip() for a in extra.split(",") if a.strip()]
        year = ((row.get("Original Publication Year", "") or "") or (row.get("Year Published", "") or "")).strip()
        isbn = normalize_isbn(row.get("ISBN13", "") or "") or normalize_isbn(row.get("ISBN", "") or "") or ""
        rating = (row.get("My Rating", "") or "0").strip()
        rating = "" if rating in ("", "0") else rating
        shelf = (row.get("Exclusive Shelf", "") or "").strip()
        books.append({
            "title": (row.get("Title", "") or "").strip(),
            "authors": authors,
            "year": year,
            "isbn": isbn,
            "rating": rating,
            "status": _SHELF.get(shelf, "to-read"),
            "pages": (row.get("Number of Pages", "") or "").strip(),
            "publisher": (row.get("Publisher", "") or "").strip(),
            "date_finished": ((row.get("Date Read", "") or "") or "").strip().replace("/", "-"),
        })
    return books


def normalize_title(s):
    if not s:
        return ""
    s = s.lower()
    s = re.sub(r"^(the|a|an)\s+", "", s)
    s = re.sub(r"[^a-z0-9 ]", "", s)
    return " ".join(s.split())


def match_entries(entries, isbn=None, title=None, author=None):
    norm_isbn = normalize_isbn(isbn) if isbn else None
    norm_title = normalize_title(title) if title else None
    want_surname = surname_of(author).lower() if author else None
    results = []
    for e in entries:
        f = e.get("fields", {})
        score = 0
        e_isbn = normalize_isbn(f.get("isbn", "")) if f.get("isbn") else None
        if norm_isbn and e_isbn and e_isbn == norm_isbn:
            score = 100
        elif norm_title:
            e_title = normalize_title(f.get("title", ""))
            if e_title and e_title == norm_title:
                score = 60
            elif e_title and (norm_title in e_title or e_title in norm_title):
                score = 40
            if score and want_surname and surname_of(f.get("author", "")).lower() == want_surname:
                score += 30
        if score >= 40:
            results.append({"citekey": e["citekey"], "score": score, "fields": f})
    results.sort(key=lambda r: r["score"], reverse=True)
    return results


def _read_bib(path):
    if path and _os.path.exists(path):
        with open(path) as f:
            return parse_bib(f.read())
    return []


def main(argv=None):
    parser = _argparse.ArgumentParser(prog="bibtools")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("check-isbn"); p.add_argument("isbn")
    p = sub.add_parser("parse"); p.add_argument("bibfile")
    p = sub.add_parser("mint-key")
    p.add_argument("--bib", required=True); p.add_argument("--author", required=True)
    p.add_argument("--year", required=True)
    p = sub.add_parser("upsert")
    p.add_argument("--bib", required=True); p.add_argument("--json", required=True)
    p = sub.add_parser("import-goodreads"); p.add_argument("csvfile")

    args = parser.parse_args(argv)

    if args.cmd == "check-isbn":
        if valid_isbn(args.isbn):
            print(normalize_isbn(args.isbn)); return 0
        print("invalid", file=_sys.stderr); return 1

    if args.cmd == "parse":
        with open(args.bibfile) as f:
            print(_json.dumps(parse_bib(f.read()), indent=2)); return 0

    if args.cmd == "mint-key":
        existing = {e["citekey"] for e in _read_bib(args.bib)}
        print(mint_citekey(args.author, args.year, existing)); return 0

    if args.cmd == "upsert":
        entries = _read_bib(args.bib)
        payload = _json.loads(args.json)
        citekey = payload.get("citekey")
        if not citekey:
            existing = {e["citekey"] for e in entries}
            author = payload.get("author") or payload.get("fields", {}).get("author", "")
            year = payload.get("fields", {}).get("year", "")
            citekey = mint_citekey(author, year, existing)
        entry = {"type": payload.get("type", "book"), "citekey": citekey,
                 "fields": payload.get("fields", {})}
        upsert_entry(entries, entry)
        with open(args.bib, "w") as f:
            f.write(write_bib(entries))
        print(citekey); return 0

    if args.cmd == "import-goodreads":
        with open(args.csvfile) as f:
            print(_json.dumps(parse_goodreads_csv(f.read()), indent=2)); return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
