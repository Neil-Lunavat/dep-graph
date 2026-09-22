"""Scoring formulas on hand-worked examples (paper/metrics.md)."""
import math

import networkx as nx

from depgraphs.scoring import coverage_auc, rank_metrics, topo_check


def test_auc_hand_worked():
    # list: a(300 lines, key) b(800, not key) c(1000, key); key = {a, c}
    # cum costs 300, 1100, 2100. grid 250..32000:
    # b=250 -> 0 ; 500 -> 1/2 ; 1000 -> 1/2 ; 2000 -> 1/2 ; 4000.. -> 1 (4 points)
    auc = coverage_auc([300, 800, 1000], [True, False, True], 2,
                       [250, 500, 1000, 2000, 4000, 8000, 16000, 32000])
    assert math.isclose(auc, (0 + 0.5 * 3 + 1 * 4) / 8)


def test_auc_empty_list_and_key_outside():
    assert coverage_auc([], [], 3, [1, 2]) == 0
    assert math.isnan(coverage_auc([], [], 0, [1, 2]))


def test_rank_metrics():
    m = rank_metrics(["x", "a", "y", "b"], {"a", "b"}, n_candidates=10)
    assert m["top1"] == 0 and m["top5"] == 1 and m["acc3"] == 0 and m["acc5"] == 1
    assert m["mrr"] == 0.5 and m["first_key_rank"] == 2
    assert math.isclose(m["ap"], (1 / 2 + 2 / 4) / 2)
    ideal = 1 + 1 / math.log2(3)
    assert math.isclose(m["ndcg10"], (1 / math.log2(3) + 1 / math.log2(5)) / ideal)
    # m=4 top files, h=2, E = 4*2/10 = 0.8
    assert math.isclose(m["odds_ratio"], (2.5 / 2.5) / (1.3 / 3.7))


def test_topo_check():
    g = nx.DiGraph([("a", "b"), ("b", "c")])        # a imports b imports c
    member = {"a": 0, "b": 1, "c": 2}
    assert topo_check(["c", "b", "a"], g, member) == (1.0, 0.0)
    assert topo_check(["a", "b", "c"], g, member) == (0.0, 1.0)
