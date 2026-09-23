"""Generate the paper's data tables from the result files.

Hand-transcribing twenty-odd rows per table is how a number ends up disagreeing with the
CSV it came from. Everything numeric in the results section is written here instead, into
paper/tab_*.tex, and the paper \\input's them. Captions, labels and prose stay in the
paper; only the rows are generated.

Usage:  python -m depgraphs.maketables
"""
from __future__ import annotations

import pandas as pd

from depgraphs.lexfeat import ROOT
from depgraphs.study2 import FUSION, OUT

PAPER = ROOT / "paper"
BS = chr(92)
NL = BS + BS

FAM = {"structure": "str", "lexical": "lex", "fusion": "fus", "global": "glo",
       "reference": "ref"}


def m(name: str) -> str:
    return BS + "m{" + name.replace("_", BS + "_") + "}"


def ci(lo: float, hi: float) -> str:
    return "[%s,%s]" % (("%.3f" % lo).lstrip("0"), ("%.3f" % hi).lstrip("0"))


def write(stem: str, body: str):
    # newline="" keeps LF, matching paper.tex. The trailing "%" matters: \input leaves a
    # space token after the file's last row terminator, which opens a fresh row, and the
    # \bottomrule that follows then lands inside it as a misplaced \noalign.
    p = PAPER / ("tab_%s.tex" % stem)
    with open(p, "w", encoding="utf-8", newline="") as f:
        f.write(body.rstrip() + "%\n")
    print("wrote", p.name, "(%d rows)" % body.count(NL))


def main_table():
    ps = pd.read_csv(OUT / "per_source.csv")
    left = ps[ps.source == "co_edited"].sort_values("rank").reset_index(drop=True)
    right = ps[ps.source == "symbol"].sort_values("rank").reset_index(drop=True)
    rows = []
    for i in range(max(len(left), len(right))):
        cells = []
        for df in (left, right):
            if i < len(df):
                r = df.loc[i]
                cells += ["%d" % r["rank"], m(r.method), FAM.get(r.family, r.family),
                          "%.3f %s" % (r.auc, ci(r.ci_lo, r.ci_hi))]
            else:
                cells += ["", "", "", ""]
        rows.append(" & ".join(cells) + " " + NL)
    write("main", "\n".join(rows))


def worst_table():
    r = pd.read_csv(OUT / "rank_by_source.csv")
    r["worst"] = r[["co_edited", "symbol"]].max(axis=1)
    ps = pd.read_csv(OUT / "per_source.csv")
    fam = dict(zip(ps.method, ps.family))
    r = r[r.method != "oracle"].sort_values(["worst", "method"])
    rows = ["%s & %s & %d & %d & %d %s" % (
        m(x.method), FAM.get(fam.get(x.method, ""), "?"),
        x.co_edited, x.symbol, x.worst, NL) for x in r.itertuples()]
    write("worst", "\n".join(rows))


def full_table():
    cm = pd.read_csv(OUT / "ceiling_method.csv")
    cm = cm[cm.budget == 8000]
    piv = cm.pivot(index="method", columns="source", values="share_full")
    piv = piv.sort_values("co_edited", ascending=False)
    rows = []
    for name, r in piv.iterrows():
        rows.append("%s & %.1f & %.1f %s" % (
            m(name), 100 * r.co_edited, 100 * r.symbol, NL))
        if name == "oracle":
            rows.append(BS + "midrule")
    write("full", "\n".join(rows))


def ceiling_table():
    ck = pd.read_csv(OUT / "ceiling_key.csv")
    t = ck[ck.unit == "tokens"].pivot(index="budget", columns="source",
                                      values="share_fits")
    rows = ["%s & %.1f & %.1f %s" % (
        "{:,}".format(int(b)).replace(",", "{,}"),
        100 * r.co_edited, 100 * r.symbol, NL) for b, r in t.iterrows()]
    write("ceiling", "\n".join(rows))


def size_table():
    sz = pd.read_csv(OUT / "by_size.csv")
    sz = sz[sz.source.isin(["co_edited", "symbol"])]
    piv = sz.pivot_table(index="method", columns=["source", "size_q"],
                         values=["auc", "rank"])
    rows = []
    for name in KEEP:
        if name not in piv.index:
            continue
        cells = [m(name)]
        for src in ("co_edited", "symbol"):
            for q in ("Q1", "Q2", "Q3", "Q4"):
                a = piv.loc[name, ("auc", src, q)]
                k = int(piv.loc[name, ("rank", src, q)])
                cells.append("%s (%d)" % (("%.3f" % a).lstrip("0"), k))
        rows.append(" & ".join(cells) + " " + NL)
    write("size", "\n".join(rows))


KEEP = ["rrf_pprpl_issue_path", "rrf_hops_path", "ppr_out_pl", "ppr_und_pl",
        "hops_lines", "path_issue", "bm25_issue", "pagerank"]


def leak_table():
    d = pd.read_csv(OUT / "leak_sensitivity.csv")
    rows = []
    for name in KEEP:
        cells = [m(name)]
        for st in ("no_full_path", "no_explicit", "no_stem"):
            for src in ("co_edited", "symbol"):
                g = d[(d.stratum == st) & (d.source == src) & (d.method == name)]
                cells.append("%s (%d)" % (("%.3f" % g.auc_no_leak.iloc[0]).lstrip("0"),
                                          int(g.rank_no_leak.iloc[0]))
                             if len(g) else "--")
        rows.append(" & ".join(cells) + " " + NL)
    write("leak", "\n".join(rows))


def shared_table():
    """The two keys re-scored on the pull requests that carry both of them."""
    sh = pd.read_csv(OUT / "per_source_shared.csv")
    full = pd.read_csv(OUT / "per_source.csv")
    rows = []
    for src in ("co_edited", "symbol"):
        s = sh[sh.source == src].set_index("method")
        f = full[full.source == src].set_index("method")
        if src == "symbol":
            rows.append(BS + "midrule")
        for name in s.sort_values("rank").index[:10]:
            d = int(s.loc[name, "rank"]) - int(f.loc[name, "rank"])
            rows.append("%s & %s & %s & %d & %s %s" % (
                m(name), FAM.get(s.loc[name, "family"], "?"),
                ("%.3f" % s.loc[name, "auc"]).lstrip("0"), int(s.loc[name, "rank"]),
                "$+%d$" % d if d > 0 else ("$%d$" % d if d < 0 else "--"), NL))
    write("shared", "\n".join(rows))


def lines_table():
    """Median lines read before half, then all, of the key is covered."""
    d = pd.read_csv(OUT / "lines_to_reach.csv")
    piv = d[d.source.isin(["co_edited", "symbol"])].pivot(
        index="method", columns="source",
        values=["lines_half_median", "lines_all_median"])
    order = ["oracle"] + [k for k in KEEP if k != "pagerank"] + ["random"]
    rows = []
    for name in order:
        if name not in piv.index:
            continue
        cells = [m(name)]
        for col in ("lines_half_median", "lines_all_median"):
            for src in ("co_edited", "symbol"):
                cells.append("{:,}".format(round(piv.loc[name, (col, src)]))
                             .replace(",", "{,}"))
        rows.append(" & ".join(cells) + " " + NL)
        if name == "oracle":
            rows.append(BS + "midrule")
    write("lines", "\n".join(rows))


def figure_data():
    """Coverage curves for the two-panel figure, one file per key source."""
    cur = pd.read_csv(OUT / "curves_mean.csv")
    cols = ["oracle", "rrf_hops_path", "ppr_und_pl", "ppr_out_pl", "path_issue",
            "pagerank", "random"]
    for src in ("co_edited", "symbol"):
        g = cur[cur.source == src].pivot(index="budget", columns="method",
                                         values="coverage")
        have = [c for c in cols if c in g.columns]
        out = ["budget " + " ".join(have)]
        for b, r in g.iterrows():
            out.append("%d %s" % (b, " ".join("%.4f" % r[c] for c in have)))
        p = PAPER / ("fig_%s.dat" % src)
        with open(p, "w", encoding="utf-8", newline="") as f:
            f.write("\n".join(out) + "\n")
        print("wrote", p.name, "columns:", have)


def main():
    main_table()
    shared_table()
    worst_table()
    lines_table()
    full_table()
    ceiling_table()
    size_table()
    leak_table()
    figure_data()


if __name__ == "__main__":
    main()
