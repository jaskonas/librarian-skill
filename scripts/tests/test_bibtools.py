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
