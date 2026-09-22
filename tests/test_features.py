import tiktoken

from depgraphs.features import blob_features, split_ident

ENC = tiktoken.get_encoding("o200k_base")


def test_split_ident():
    assert split_ident("parse_HTTPHeader") == ["parse", "http", "header"]
    assert split_ident("getX") == ["get"]          # 1-letter tokens dropped
    assert split_ident("camelCaseName") == ["camel", "case", "name"]


def test_blob_features():
    src = ("import os\nX = 1\nclass Foo:\n    def bar(self):\n        return baz(os.path)\n"
           "def qux():\n    pass\n")
    f = blob_features(src, ENC)
    assert f["lines"] == 7 and f["parse_ok"]
    assert f["defs"] == ["Foo", "X", "bar", "qux"]
    assert "baz" in f["calls"] and "path" in f["refs"] and "os" in f["refs"]
    assert f["bag"]["foo"] == 1 and f["tokens"] > 0


def test_unparseable_still_has_bag():
    f = blob_features("def (:\n  parse_header = 1\n", ENC)
    assert not f["parse_ok"] and f["bag"]["header"] == 1 and f["defs"] == []
