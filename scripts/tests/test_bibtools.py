import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import bibtools


def test_normalize_isbn_strips_formatting():
    assert bibtools.normalize_isbn("978-0-268-03504-4") == "9780268035044"
    assert bibtools.normalize_isbn('="9780268035044"') == "9780268035044"
    assert bibtools.normalize_isbn("0-268-00594-X") == "026800594X"
    assert bibtools.normalize_isbn("nonsense") is None


def test_valid_isbn13():
    assert bibtools.valid_isbn("978-0-268-03504-4") is True
    assert bibtools.valid_isbn("978-0-268-03504-5") is False  # bad check digit


def test_valid_isbn10():
    assert bibtools.valid_isbn("0-268-00594-X") is True
    assert bibtools.valid_isbn("0-268-00594-1") is False


import os

FIX = os.path.join(os.path.dirname(__file__), "fixtures")


def test_parse_bib_reads_entries():
    with open(os.path.join(FIX, "sample.bib")) as f:
        entries = bibtools.parse_bib(f.read())
    assert len(entries) == 2
    e = entries[0]
    assert e["type"] == "book"
    assert e["citekey"] == "MacIntyre1981"
    assert e["fields"]["author"] == "MacIntyre, Alasdair"
    assert e["fields"]["title"] == "After Virtue"
    assert e["fields"]["year"] == "1981"


def test_format_entry_orders_fields():
    entry = {"type": "book", "citekey": "X2000",
             "fields": {"isbn": "123", "title": "T", "author": "A", "year": "2000"}}
    out = bibtools.format_entry(entry)
    assert out.startswith("@book{X2000,")
    # author before title before year before isbn
    assert out.index("author") < out.index("title") < out.index("year") < out.index("isbn")


def test_round_trip():
    with open(os.path.join(FIX, "sample.bib")) as f:
        text = f.read()
    entries = bibtools.parse_bib(text)
    reparsed = bibtools.parse_bib(bibtools.write_bib(entries))
    assert reparsed == entries
