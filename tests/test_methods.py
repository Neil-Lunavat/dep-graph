"""Methods on a hand-built toy graph (G13).

    s -> a -> b        (s imports a, a imports b)
    c -> s             (c imports s)
    b -> d -> b        (loop {b, d})
    pkg/e              (isolated)
"""
import random

import pytest

from depgraphs.methods import METHODS, Ctx, by_score, oracle, topo_fwd

NODES = ["s", "a", "b", "c", "d", "pkg/e"]
EDGES = [("s", "a"), ("a", "b"), ("c", "s"), ("b", "d"), ("d", "b")]
FEATS = {
    "s": {"lines": 10, "defs": ["run"], "refs": ["helper", "Engine"], "calls": ["helper"],
          "bag": {"parse": 3, "header": 2}},
    "a": {"lines": 20, "defs": ["helper"], "refs": ["util"], "calls": ["util"], "bag": {"helper": 1}},
    "b": {"lines": 30, "defs": ["util"], "refs": [], "calls": [], "bag": {"parse": 1}},
    "c": {"lines": 40, "defs": ["Engine"], "refs": ["run"], "calls": ["run"], "bag": {"header": 5}},
    "d": {"lines": 50, "defs": [], "refs": ["util"], "calls": [], "bag": {}},
    "pkg/e": {"lines": 60, "defs": [], "refs": [], "calls": [], "bag": {"zzz": 1}},
}


@pytest.fixture
def ctx():
    return Ctx(NODES, EDGES, FEATS, cochange={"s": {"c": 2.0, "b": 0.5}})


@pytest.mark.parametrize("name", sorted(METHODS))
def test_invariants(ctx, name):
    out1 = METHODS[name](ctx, "s", random.Random(1))
    out2 = METHODS[name](ctx, "s", random.Random(1))
    assert out1 == out2, "same rng seed must give the same list"
    assert "s" not in out1
    assert len(out1) == len(set(out1))
    assert set(out1) <= set(NODES)


def test_bfs(ctx):
    r = random.Random(0)
    assert METHODS["bfs_fwd"](ctx, "s", r)[:2] == ["a", "b"]
    assert set(METHODS["bfs_fwd"](ctx, "s", r)) == {"a", "b", "d"}
    assert METHODS["bfs_rev"](ctx, "s", r) == ["c"]
    assert set(METHODS["khop1_und"](ctx, "s", r)) == {"a", "c"}
    assert set(METHODS["closure_comb"](ctx, "s", r)) == {"a", "b", "c", "d"}


def test_topo_dependencies_first(ctx):
    out = topo_fwd(ctx, "s", random.Random(0))
    assert set(out[:2]) == {"b", "d"} and out[2] == "a"


def test_directory_and_same_dir(ctx):
    out = METHODS["directory"](ctx, "s", random.Random(0))
    assert out[-1] == "pkg/e"
    assert set(METHODS["same_dir"](ctx, "s", random.Random(0))) == {"a", "b", "c", "d"}


def test_bm25_and_cochange(ctx):
    out = METHODS["bm25"](ctx, "s", random.Random(0))
    assert set(out) == {"b", "c"} and out[0] == "c"   # c shares 'header' x5
    assert METHODS["cochange"](ctx, "s", random.Random(0)) == ["c", "b"]


def test_ref_and_call_graphs(ctx):
    assert set(ctx.R.edges) == {("s", "a"), ("s", "c"), ("a", "b"), ("c", "s"), ("d", "b")}
    assert set(ctx.C.edges) == {("s", "a"), ("a", "b"), ("c", "s")}
    assert set(METHODS["repograph_k1"](ctx, "s", random.Random(0))) == {"a", "c"}


def test_robillard_starts_with_most_specific(ctx):
    out = METHODS["robillard"](ctx, "s", random.Random(0))
    # a and c both have 2 neighbours, one in S -> tie; both come first
    assert set(out[:2]) == {"a", "c"}


def test_oracle_cheapest_first(ctx):
    assert oracle(ctx, "s", random.Random(0), key={"c", "a", "b"}) == ["a", "b", "c"]


def test_by_score_ties_random_but_seeded():
    s = {"x": 1, "y": 1, "z": 2}
    a = by_score(s, random.Random(3))
    assert a[0] == "z" and a == by_score(s, random.Random(3))


def test_cochange_score_rule():
    from depgraphs.cochange import score
    fs = [("c1", 1, ["s.py", "a.py", "tests/test_s.py"]),     # 2 source files -> w=1
          ("c2", 2, ["s.py", "a.py", "b.py"]),                  # 3 files -> w=0.5
          ("c3", 3, ["a.py", "b.py"]),                          # no seed
          ("c4", 4, ["s.py"])]                                  # single file: ignored
    sc, used = score(fs, ["s.py"])
    assert used == 3 and sc["s.py"] == {"a.py": 1.5, "b.py": 0.5}
