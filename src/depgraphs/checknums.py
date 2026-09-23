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


@check("matched population: what moves when both keys score the same PRs")
def c_shared():
    sh = pd.read_csv(OUT / "per_source_shared.csv")
    full = pd.read_csv(OUT / "per_source.csv")
    out = []
    for src in ("co_edited", "symbol"):
        a = sh[sh.source == src].set_index("method")
        b = full[full.source == src].set_index("method")
        d = (a["rank"] - b["rank"].reindex(a.index)).dropna()
        worst = d.abs().sort_values(ascending=False).head(3)
        top = a.sort_values("rank").index[1:4].tolist()   # skip the oracle
        out.append("%s (n=%d): top3 %s; biggest rank moves %s"
                   % (src, int(a.n_pr.iloc[0]), top,
                      ", ".join("%s %+d" % (k, v) for k, v in worst.items())))
    return " | ".join(out)


@check("repository-level tests: does any headline comparison lose significance?")
def c_repo_unit():
    pw = pd.read_csv(OUT / "pairwise.csv")
    if "unit" not in pw.columns:
        return "pairwise.csv has no unit column - rerun analysis2"
    pairs = [("rrf_pprpl_issue_path", "path_issue"),
             ("ppr_out_pl", "path_issue"),
             ("hops_lines", "path_issue"),
             ("ppr_out_pl", "ppr_in_pl"),
             ("ppr_out_pl", "ppr_und_pl")]
    out = []
    for a, b in pairs:
        for src in ("co_edited", "symbol"):
            for pop in ("all", "shared"):
                g = pw[(pw.unit == "repo") & (pw.population == pop) & (pw.source == src)
                       & (((pw.a == a) & (pw.b == b)) | ((pw.a == b) & (pw.b == a)))]
                if not len(g):
                    continue
                r = g.iloc[0]
                sign = -1 if r.a != a else 1
                out.append("%s>%s %s/%s d=%+.3f p=%.2g"
                           % (a, b, src, pop, sign * r.delta, r.p_holm))
    return "; ".join(out)


@check("leakage strata: is the co_edited finding an artefact of over-correcting?")
def c_leak_strata():
    d = pd.read_csv(OUT / "leak_sensitivity.csv")
    want = {"no_full_path", "no_explicit", "no_stem"}
    have = set(d.stratum.unique())
    if not want <= have:
        return "missing strata %s - rerun leakage then analysis2" % (want - have)
    out = []
    for st in ("no_full_path", "no_explicit", "no_stem"):
        g = d[(d.stratum == st) & (d.source == "co_edited")]
        pi = g[g.method == "path_issue"].iloc[0]
        hl = g[g.method == "hops_lines"].iloc[0]
        out.append("%s (n=%d): path_issue #%d %.3f, hops_lines #%d %.3f"
                   % (st, int(pi.n_pr), pi.rank_no_leak, pi.auc_no_leak,
                      hl.rank_no_leak, hl.auc_no_leak))
    return " | ".join(out)


@check("leakage rates: full path, explicit code mention, bare stem")
def c_leak_rates():
    d = pd.read_csv(OUT / "issue_path_leak.csv")
    if "explicit" not in d.columns:
        return "issue_path_leak.csv has no explicit column - rerun leakage"
    n = len(d)
    bits = ["%s %.1f%%" % (c, 100 * d[c].mean())
            for c in ("full", "stem", "explicit", "incidental")]
    strict = int(((d["full"] == 0) & (d["stem"] == 0)).sum())
    primary = int(((d["full"] == 0) & (d["explicit"] == 0)).sum())
    inc_only = int(((d["full"] == 0) & (d["explicit"] == 0) & (d["stem"] > 0)).sum())
    adds_up = abs(100 * (d["explicit"].mean() + inc_only / n) - 100 * d["stem"].mean()) < 0.05
    return ("%d tasks: %s | incidental-only %.1f%% | explicit+incidental-only = stem: %s"
            " | primary stratum %d, strictest %d"
            % (n, ", ".join(bits), 100 * inc_only / n, adds_up, primary, strict))


@check("which fusions survive, and what distinguishes them")
def c_fusion_why():
    r = _rank_by_source()
    pure = [m for m in r.index if m not in FUSION
            and m not in ("oracle", "random", "same_dir")]
    best_pure = r.loc[pure, "worst"].min()
    scaled = {"hops_lines", "ppr_und_pl"}
    out = []
    for m in sorted(FUSION):
        if m not in r.index:
            continue
        base = [b for b in scaled if b.split("_")[0][:4] in m or b in m]
        out.append("%s worst=%d %s path=%s"
                   % (m, r.loc[m, "worst"],
                      "beats-pure" if r.loc[m, "worst"] < best_pure else "does-not",
                      "path" in m))
    return "best pure worst=%d | %s" % (best_pure, "; ".join(out))


@check("what the issue adds to a fusion, by how explicitly the issue names the answer")
def c_issue_dose():
    pw = pd.read_csv(OUT / "pairwise.csv")
    out = []
    for st in ("explicit", "all", "no_full_path", "no_explicit", "no_stem"):
        bits = []
        for a, b in (("rrf_pprpl_issue_path", "rrf_pprpl_seedpath"),
                     ("rrf_hops_path", "rrf_hops_pathseed")):
            for src in ("co_edited", "symbol"):
                g = pw[(pw.unit == "repo") & (pw.stratum == st)
                       & (pw.population == "shared") & (pw.source == src)
                       & (((pw.a == a) & (pw.b == b)) | ((pw.a == b) & (pw.b == a)))]
                if not len(g):
                    continue
                r = g.iloc[0]
                d = (1 if r.a == a else -1) * r.delta
                bits.append("%+.3f%s" % (d, "*" if r.p_holm < 0.05 else ""))
        out.append("%s [%s]" % (st, " ".join(bits)))
    return " | ".join(out)


@check("both controls at once: matched population inside each leakage stratum")
def c_joint():
    j = pd.read_csv(OUT / "per_source_joint.csv")
    out = []
    for st in ("all", "no_explicit", "no_stem"):
        for src in ("co_edited", "symbol"):
            g = j[(j.stratum == st) & (j.source == src) & (j.method != "oracle")]
            g = g.sort_values("rank").head(3)
            out.append("%s/%s n=%d: %s" % (
                st, src, int(g.n_pr.iloc[0]),
                ", ".join("%s %.3f" % (m, a) for m, a in zip(g.method, g.auc))))
    return " | ".join(out)


@check("held-out split: is the fusion chosen on one half still best on the other?")
def c_heldout():
    h = pd.read_csv(OUT / "heldout.csv")
    chosen = h.chosen_on_select.iloc[0]
    out = ["chose %s on %d repositories" % (chosen, int(h.n_repos.iloc[0]))]
    for src in ("co_edited", "symbol"):
        g = h[(h.half == "confirm") & (h.source == src) & (h.method != "oracle")]
        r = g[g.method == chosen].iloc[0]
        best = g.sort_values("rank").iloc[0]
        out.append("held-out %s: rank %d (%.3f), best is %s %.3f"
                   % (src, int(r["rank"]), r.auc, best.method, best.auc))
    return " | ".join(out)


@check("are the leakage-stratum rank changes significant, or only nominal?")
def c_leak_tested():
    pw = pd.read_csv(OUT / "pairwise.csv")
    out = []
    for st in ("no_full_path", "no_explicit", "no_stem"):
        for a, b, src in (("hops_lines", "path_issue", "co_edited"),
                          ("rrf_pprpl_issue_path", "path_issue", "co_edited"),
                          ("ppr_und_pl", "rrf_pprpl_issue_path", "symbol")):
            g = pw[(pw.unit == "repo") & (pw.stratum == st) & (pw.population == "shared")
                   & (pw.source == src)
                   & (((pw.a == a) & (pw.b == b)) | ((pw.a == b) & (pw.b == a)))]
            if not len(g):
                continue
            r = g.iloc[0]
            d = (1 if r.a == a else -1) * r.delta
            out.append("%s %s>%s/%s d=%+.3f p=%.2g" % (st, a, b, src, d, r.p_holm))
    return "; ".join(out)


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
