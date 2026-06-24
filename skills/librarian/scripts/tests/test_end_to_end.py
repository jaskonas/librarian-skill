import sys, os, subprocess, json

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "bibtools.py")


def _run(*args):
    return subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True)


def test_full_flow(tmp_path):
    bib = tmp_path / "library.bib"
    bib.write_text("")
    # Add two books by the same author+year -> collision suffix.
    for title in ["After Virtue", "Whose Justice"]:
        payload = json.dumps({"type": "book", "author": "Alasdair MacIntyre",
                              "fields": {"author": "MacIntyre, Alasdair",
                                         "title": title, "year": "1981"}})
        out = _run("upsert", "--bib", str(bib), "--json", payload)
        assert out.returncode == 0
    keys = [e["citekey"] for e in json.loads(_run("parse", str(bib)).stdout)]
    assert "MacIntyre1981" in keys and "MacIntyre1981a" in keys
