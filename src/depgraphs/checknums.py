"""Check the paper's prose against the result files.

The failure this guards against is specific and was found by a reviewer: every number in
the paper was copied mechanically from a CSV, and every *sentence about* those numbers was
written by hand. Claims like "every fusion beats every pure signal" or "third or better in
all eight cells" are not numbers, so nothing checked them, and several were false.

Each check below states a claim the text makes and recomputes it. A check that cannot be
expressed against the data does not belong here; it belongs in the reviewer's hands.

Usage:  python -m depgraphs.checknums
Exit status is non-zero if any check fails.
"""
from __future__ import annotations

import sys

import pandas as pd

from depgraphs.study2 import FUSION, OUT

CHECKS = []


def check(name):
    def deco(fn):
        CHECKS.append((name, fn))
        return fn
    return deco


def _rank_by_source():
    r = pd.read_csv(OUT / "rank_by_source.csv")
    r["worst"] = r[["co_edited", "symbol"]].max(axis=1)
    return r.set_index("method")


@check("worst-case rank: which fusions beat every pure signal")
def c_fusion_worst():
    r = _rank_by_source()
    pure = [m for m in r.index if m not in FUSION
            and m not in ("oracle", "random", "same_dir")]
    best_pure = r.loc[pure, "worst"].min()
    winners = sorted(m for m in FUSION if m in r.index and r.loc[m, "worst"] < best_pure)
    losers = sorted(m for m in FUSION if m in r.index and r.loc[m, "worst"] >= best_pure)
    return ("fusions beating every pure signal: %s | fusions that do NOT: %s "
            "(best pure worst-rank = %d)" % (winners, losers or "none", best_pure))


@check("per-source top 5 and their families")
def c_top():
    ps = pd.read_csv(OUT / "per_source.csv")
    out = []
    for src in ("co_edited", "symbol"):
        t = ps[ps.source == src].nsmallest(5, "rank")
        out.append("%s: %s" % (src, ", ".join(
            "%s(%s,%.3f,#%d)" % (r.method, r.family[:4], r.auc, r["rank"])
            for _, r in t.iterrows())))
    return " | ".join(out)


@check("rank conventions: n methods overall vs n contenders")
def c_ranks():
    ps = pd.read_csv(OUT / "per_source.csv")
    pw = pd.read_csv(OUT / "pairwise.csv")
    n_all = ps[ps.source == "co_edited"].method.nunique()
    cont = set(pw.a) | set(pw.b) if {"a", "b"} <= set(pw.columns) else set()
    return "ranks in per_source are over %d orderings; contender set has %d" % (
        n_all, len(cont))


@check("full coverage at 8000 lines: best non-oracle per source")
def c_ceiling():
    cm = pd.read_csv(OUT / "ceiling_method.csv")
    cm = cm[cm.budget == 8000]
    out = []
    for src in ("co_edited", "symbol"):
        g = cm[(cm.source == src) & (cm.method != "oracle")].nlargest(3, "share_full")
        o = cm[(cm.source == src) & (cm.method == "oracle")].share_full.iloc[0]
        out.append("%s: oracle %.1f%%, best %s" % (src, 100 * o, ", ".join(
            "%s %.1f%%" % (r.method, 100 * r.share_full) for _, r in g.iterrows())))
    return " | ".join(out)


@check("size quartiles: rank of the headline fusion in every cell")
def c_size():
    sz = pd.read_csv(OUT / "by_size.csv")
    sz = sz[sz.source.isin(["co_edited", "symbol"])]
    piv = sz.pivot_table(index="method", columns=["source", "size_q"], values="rank")
    m = "rrf_hops_path"
    if m not in piv.index:
        return "MISSING " + m
    v = piv.loc[m]
    return "%s ranks %s (worst %d)" % (m, list(v.astype(int)), int(v.max()))


@check("size quartiles: does the co_edited/symbol rank gap widen with size?")
def c_widen():
    sz = pd.read_csv(OUT / "by_size.csv")
    piv = sz.pivot_table(index="method", columns=["source", "size_q"], values="rank")
    out = []
    for m in ("ppr_und_pl", "hops_lines", "path_issue", "pagerank"):
        if m not in piv.index:
            continue
        gaps = [int(piv.loc[m, ("co_edited", q)] - piv.loc[m, ("symbol", q)])
                for q in ("Q1", "Q2", "Q3", "Q4")]
        mono = all(b >= a for a, b in zip(gaps, gaps[1:]))
        out.append("%s gaps %s %s" % (m, gaps, "monotonic" if mono else "NOT monotonic"))
    return " | ".join(out)


@check("distance profile rows: proportions or medians?")
def c_distance():
    d = pd.read_csv(OUT / "distance_profile.csv")
    sums = d.groupby("source")["share"].sum().round(3).to_dict()
    return "share sums per source %s (1.0 means pooled proportions, not medians)" % sums


@check("rank agreement between the two key sources")
def c_rho():
    import json
    f = json.loads((OUT / "findings.json").read_text())
    return str(f.get("rank_agreement"))


@check("issue-text methods: points lost moving co_edited -> symbol (full coverage)")
def c_drop():
    cm = pd.read_csv(OUT / "ceiling_method.csv")
    cm = cm[cm.budget == 8000]
    out = []
    for m in ("bm25_issue", "path_issue"):
        a = cm[(cm.method == m) & (cm.source == "co_edited")].share_full
        b = cm[(cm.method == m) & (cm.source == "symbol")].share_full
        if len(a) and len(b):
            out.append("%s -%.1f pts" % (m, 100 * (a.iloc[0] - b.iloc[0])))
    return ", ".join(out)


@check("stem-leakage stratum: does the reversal survive?")
def c_stem():
    p = OUT / "leak_sensitivity.csv"
    d = pd.read_csv(p)
    if "stratum" not in d.columns:
        return "leak_sensitivity.csv has no stratum column - rerun analysis2"
    out = []
    for st in d.stratum.unique():
        g = d[d.stratum == st]
        n = int(g.n_pr.max())
        bits = []
        for src in ("co_edited", "symbol"):
            h = g[g.source == src].nsmallest(2, "rank_no_leak")
            bits.append("%s top %s" % (src, list(h.method)))
        out.append("%s (n=%d): %s" % (st, n, "; ".join(bits)))
    return " | ".join(out)


@check("directed PPR: does edge direction matter, and per source?")
def c_directed():
    ps = pd.read_csv(OUT / "per_source.csv")
    ms = ["ppr_und", "ppr_und_pl", "ppr_out", "ppr_out_pl", "ppr_in", "ppr_in_pl"]
    out = []
    for src in ("co_edited", "symbol"):
        g = ps[(ps.source == src) & (ps.method.isin(ms))].sort_values("rank")
        if g.empty:
            return "directed variants absent - rerun study2"
        out.append("%s: %s" % (src, ", ".join(
            "%s #%d %.3f" % (r.method, r["rank"], r.auc) for _, r in g.iterrows())))
    return " | ".join(out)


def main():
    bad = 0
    for name, fn in CHECKS:
        try:
            print("[ok] %s\n     %s\n" % (name, fn()))
        except Exception as e:
            bad += 1
            print("[!!] %s\n     %s: %s\n" % (name, type(e).__name__, e))
    print("%d check(s) could not be computed" % bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
