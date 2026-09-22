import hashlib

import pandas as pd

from depgraphs.sampling import draw, draw_key, size_terciles


def test_draw_key_is_sha256_of_seed_plus_name():
    assert draw_key(42, "a/b") == hashlib.sha256(b"42a/b").hexdigest()


def test_draw_is_deterministic_and_per_stratum():
    c = pd.DataFrame({"repo": [f"o/r{i}" for i in range(10)],
                      "stratum": ["x"] * 5 + ["y"] * 5})
    a = draw(c, 7, 2)
    b = draw(c.sample(frac=1, random_state=1), 7, 2)
    assert sorted(a.repo) == sorted(b.repo)
    assert a.groupby("stratum").size().to_dict() == {"x": 2, "y": 2}
    # hand-check: the two smallest hashes in stratum x
    xs = sorted(c.repo[:5], key=lambda r: draw_key(7, r))[:2]
    assert set(a[a.stratum == "x"].repo) == set(xs)


def test_fixed_block_is_added_not_drawn():
    c = pd.DataFrame({"repo": ["o/a", "o/b", "o/c"], "stratum": ["x", "x", "x"]})
    out = draw(c, 1, 1, fixed_block=["o/a"])
    assert "o/a" in set(out.repo) and len(out) == 2
    assert out.set_index("repo").loc["o/a", "in_fixed_block"]


def test_terciles():
    s = pd.Series([1, 2, 3, 4, 5, 6])
    assert size_terciles(s).tolist() == ["small"] * 2 + ["medium"] * 2 + ["large"] * 2
