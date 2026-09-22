"""Table 1 metrics on a hand-worked graph.

    a -> b -> c -> b   (loop {b, c})
    a -> d
    e                  (isolated)
"""
import math

from depgraphs.table1 import gini, metrics

NODES = ["a", "b", "c", "d", "pkg/e"]
EDGES = [("a", "b"), ("b", "c"), ("c", "b"), ("a", "d")]


def test_hand_worked():
    m = metrics(NODES, EDGES, lines={"a": 10, "b": 20, "c": 30, "d": 40, "pkg/e": 50},
                unresolved=1, internal=4)
    assert m["files"] == 5 and m["import_edges"] == 4
    assert math.isclose(m["density"], 4 / 20)
    # in-degrees a0 b2 c1 d1 e0 ; out-degrees a2 b1 c1 d0 e0
    assert m["indeg_max"] == 2 and math.isclose(m["indeg_mean"], 0.8)
    assert m["outdeg_max"] == 2
    # top ceil(0.25)=1 file by in-degree = b, which receives 2 of 4 edges
    assert math.isclose(m["hub_share_top5pct"], 0.5)
    assert m["n_loops"] == 1 and m["largest_loop"] == 2
    assert math.isclose(m["share_in_loops"], 0.4)
    # condensation: a -> {b,c}, a -> d : longest path 1 edge
    assert m["depth_condensed"] == 1
    # reachable pairs: a->b1 a->c2 a->d1 b->c1 c->b1 : mean 6/5, max 2
    assert math.isclose(m["spl_mean"], 1.2) and m["spl_max"] == 2
    assert m["n_wcc"] == 2 and math.isclose(m["largest_wcc_share"], 0.8)
    assert m["isolated"] == 1
    assert math.isclose(m["single_importer_share"], 0.4)   # c and d
    assert m["nesting_max"] == 1 and math.isclose(m["nesting_mean"], 0.2)
    assert math.isclose(m["unresolved_share"], 0.25)
    assert m["loc_total"] == 150 and m["loc_median"] == 30


def test_gini():
    assert gini([1, 1, 1, 1]) == 0
    assert math.isclose(gini([0, 0, 0, 4]), 0.75)
