import sys, os, subprocess, json
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


def test_surname_of_handles_formats():
    assert bibtools.surname_of("MacIntyre, Alasdair") == "MacIntyre"
    assert bibtools.surname_of("Alasdair MacIntyre") == "MacIntyre"
    assert bibtools.surname_of("Charles Taylor and Hubert Dreyfus") == "Taylor"
    assert bibtools.surname_of("{Anonymous}") == "Anonymous"


def test_base_citekey():
    assert bibtools.base_citekey("MacIntyre, Alasdair", "1981") == "MacIntyre1981"
    assert bibtools.base_citekey("Alasdair MacIntyre", 1981) == "MacIntyre1981"


def test_mint_citekey_collisions():
    existing = {"MacIntyre1981"}
    assert bibtools.mint_citekey("MacIntyre, Alasdair", 1981, existing) == "MacIntyre1981a"
    existing.add("MacIntyre1981a")
    assert bibtools.mint_citekey("MacIntyre, Alasdair", 1981, existing) == "MacIntyre1981b"
    assert bibtools.mint_citekey("Charles Taylor", 1989, existing) == "Taylor1989"


def test_upsert_entry_adds_and_merges():
    entries = [{"type": "book", "citekey": "A2000", "fields": {"title": "Old", "year": "2000"}}]
    bibtools.upsert_entry(entries, {"type": "book", "citekey": "A2000",
                                    "fields": {"title": "New", "isbn": "123"}})
    assert len(entries) == 1
    assert entries[0]["fields"]["title"] == "New"      # overwritten
    assert entries[0]["fields"]["year"] == "2000"      # preserved
    assert entries[0]["fields"]["isbn"] == "123"       # added
    bibtools.upsert_entry(entries, {"type": "book", "citekey": "B2001", "fields": {}})
    assert len(entries) == 2


def test_parse_goodreads_csv():
    with open(os.path.join(FIX, "goodreads.csv")) as f:
        books = bibtools.parse_goodreads_csv(f.read())
    assert len(books) == 2
    b = books[0]
    assert b["title"] == "After Virtue"
    assert b["authors"] == ["Alasdair MacIntyre"]
    assert b["year"] == "1981"                  # Original Publication Year preferred
    assert b["isbn"] == "9780268006112"         # ISBN13 preferred, unwrapped
    assert b["rating"] == "5"
    assert b["status"] == "read"
    assert books[1]["status"] == "to-read"
    assert books[1]["rating"] == ""             # 0 rating becomes empty


SCRIPT = os.path.join(os.path.dirname(__file__), "..", "bibtools.py")


def _run(*args):
    return subprocess.run([sys.executable, SCRIPT, *args],
                          capture_output=True, text=True)


def test_cli_check_isbn():
    ok = _run("check-isbn", "978-0-268-03504-4")
    assert ok.returncode == 0
    assert ok.stdout.strip() == "9780268035044"
    bad = _run("check-isbn", "978-0-268-03504-5")
    assert bad.returncode == 1


def test_cli_parse(tmp_path):
    bib = tmp_path / "x.bib"
    bib.write_text("@book{A2000,\n  author = {Doe, Jane},\n  title = {T},\n  year = {2000}\n}\n")
    out = _run("parse", str(bib))
    assert out.returncode == 0
    data = json.loads(out.stdout)
    assert data[0]["citekey"] == "A2000"


def test_cli_upsert_mints_key(tmp_path):
    bib = tmp_path / "x.bib"
    bib.write_text("")
    payload = json.dumps({"type": "book", "author": "Alasdair MacIntyre",
                          "fields": {"author": "MacIntyre, Alasdair",
                                     "title": "After Virtue", "year": "1981"}})
    out = _run("upsert", "--bib", str(bib), "--json", payload)
    assert out.returncode == 0
    assert out.stdout.strip() == "MacIntyre1981"
    assert "MacIntyre1981" in bib.read_text()


def test_surname_of_degenerate_input():
    # Empty / punctuation-only authors degrade to "" rather than raising.
    assert bibtools.surname_of("") == ""
    assert bibtools.surname_of("Plato") == "Plato"          # single name
    assert bibtools.surname_of("Hannah Arendt") == "Arendt"


def test_format_entry_sorts_extra_fields_after_defaults():
    # Non-default fields follow the five ordered ones, alphabetically.
    entry = {"type": "book", "citekey": "X2000",
             "fields": {"note": "n", "abstract": "a", "year": "2000", "author": "A"}}
    out = bibtools.format_entry(entry)
    assert out.index("author") < out.index("year") < out.index("abstract") < out.index("note")


def test_normalize_title():
    assert bibtools.normalize_title("The Great Gatsby!") == "great gatsby"
    assert bibtools.normalize_title("A Theory of Justice") == "theory of justice"
    assert bibtools.normalize_title("") == ""


def _entries():
    return [
        {"type": "book", "citekey": "MacIntyre1981",
         "fields": {"author": "MacIntyre, Alasdair", "title": "After Virtue",
                    "year": "1981", "isbn": "9780268006112"}},
        {"type": "book", "citekey": "Taylor1989",
         "fields": {"author": "Taylor, Charles", "title": "Sources of the Self", "year": "1989"}},
    ]


def test_match_by_isbn_is_definitive():
    res = bibtools.match_entries(_entries(), isbn="978-0-268-00611-2")
    assert res[0]["citekey"] == "MacIntyre1981"
    assert res[0]["score"] == 100


def test_match_by_title_and_author():
    res = bibtools.match_entries(_entries(), title="The Sources of the Self", author="Charles Taylor")
    assert res[0]["citekey"] == "Taylor1989"
    assert res[0]["score"] == 90  # exact title after article-strip (60) + surname (30)


def test_match_exact_title_no_author():
    res = bibtools.match_entries(_entries(), title="After Virtue")
    assert res[0]["citekey"] == "MacIntyre1981"
    assert res[0]["score"] == 60


def test_match_none():
    assert bibtools.match_entries(_entries(), title="Being and Time", author="Heidegger") == []


def test_cli_match(tmp_path):
    bib = tmp_path / "x.bib"
    bib.write_text("@book{Taylor1989,\n  author = {Taylor, Charles},\n  title = {Sources of the Self},\n  year = {1989}\n}\n")
    out = _run("match", "--bib", str(bib), "--title", "Sources of the Self", "--author", "Charles Taylor")
    assert out.returncode == 0
    res = json.loads(out.stdout)
    assert res[0]["citekey"] == "Taylor1989"
    # no-match prints empty array
    out2 = _run("match", "--bib", str(bib), "--title", "Being and Time")
    assert json.loads(out2.stdout) == []
