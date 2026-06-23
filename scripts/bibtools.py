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
