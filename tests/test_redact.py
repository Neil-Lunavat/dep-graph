"""The three redaction arms on a hand-written issue (redact.py)."""
from depgraphs.redact import defined_names, redact

ISSUE = (
    "Traceback:\n"
    "```\n"
    '  File "astroquery/simbad/core.py", line 3, in query_object\n'
    "```\n"
    "calling Simbad.query_object( fails; see astroquery.simbad.core and the simbad docs"
)
KEY = ["astroquery/simbad/core.py"]


def test_names_arm_leaves_directories_and_symbols():
    text, n = redact(ISSUE, KEY, "names")
    assert "core" not in text
    assert "astroquery/simbad/" in text and "astroquery.simbad." in text
    assert "query_object" in text
    assert n == 2


def test_paths_arm_removes_directories_written_as_code_only():
    text, _ = redact(ISSUE, KEY, "paths")
    assert "astroquery" not in text
    # the prose mention is vocabulary, not a path, and stays
    assert "the simbad docs" in text
    assert "query_object" in text


def test_symbols_arm_removes_defined_names_written_as_code():
    text, _ = redact(ISSUE, KEY, "symbols", {"query_object"})
    assert "query_object" not in text
    assert "the simbad docs" in text


def test_nothing_to_remove_is_a_no_op():
    text = "the widget crashes when resized"
    for mode in ("names", "paths", "symbols"):
        assert redact(text, KEY, mode, {"query_object"}) == (text, 0)


def test_defined_names_skips_dunders_and_short_names():
    src = "class Simbad:\n    def __init__(self): pass\n    def query_object(self): pass\n" \
          "def f(): pass\n"
    assert defined_names(src) == {"Simbad", "query_object"}
    assert defined_names("def (:") == set()
