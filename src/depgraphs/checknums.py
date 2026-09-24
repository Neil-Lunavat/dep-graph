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


@check("redaction: what deleting the key files' names from the same issue costs")
def c_redaction():
    d = pd.read_csv(OUT / "redaction.csv")
    if "arm" in d:
        d = d[d.arm == "names"]
    out = []
    for grp in ("names removed", "nothing removed"):
        g = d[d.group == grp]
        bits = ["%s/%s %+.3f [%.3f,%.3f]%s" % (r.method, r.source[:3], r.delta,
                                               r.ci_lo, r.ci_hi,
                                               "*" if r.p_holm < 0.05 else "")
                for r in g.itertuples() if r.method in
                ("path_issue", "rrf_pprpl_issue_path")]
        out.append("%s (n=%d): %s" % (grp, int(g.n.iloc[0]), "; ".join(bits)))
    ctl = d[d.group == "nothing removed"].delta.abs().max()
    out.append("control arm max |delta| = %.4f (must be ~0)" % ctl)
    return " | ".join(out)


@check("decomposition: does whole issue = names + rest, on one population?")
def c_decompose():
    pw = pd.read_csv(OUT / "pairwise.csv")

    def d(a, b, src, st):
        g = pw[(pw.unit == "repo") & (pw.stratum == st) & (pw.population == "shared")
               & (pw.source == src)
               & (((pw.a == a) & (pw.b == b)) | ((pw.a == b) & (pw.b == a)))]
        r = g.iloc[0]
        return (1 if r.a == a else -1) * r.delta

    F, T, R = "rrf_pprpl_issue_path", "rrf_pprpl_seedpath", "rrf_pprpl_issue_path_rd"
    out = []
    for src in ("co_edited", "symbol"):
        whole, names, rest = (d(F, T, src, "explicit"), d(F, R, src, "explicit"),
                              d(R, T, src, "explicit"))
        non = d(F, T, src, "no_explicit")
        out.append("%s: whole %+.3f = names %+.3f + rest %+.3f (residual %+.4f); "
                   "names nothing %+.3f"
                   % (src, whole, names, rest, whole - names - rest, non))
    return " | ".join(out)


@check("repeated held-out splits: how often is the same fusion selected and confirmed?")
def c_splits():
    h = pd.read_csv(OUT / "heldout.csv")
    top = h.chosen.value_counts()
    best = top.idxmax()
    g = h[h.chosen == best]
    return ("%d splits; %s selected %d; best on held-out %d (co_edited) / %d (symbol); "
            "mean gap %.4f / %.4f"
            % (len(h), best, len(g), int((g.rank_co_edited == 2).sum()),
               int((g.rank_symbol == 2).sum()),
               (g.best_co_edited - g.auc_co_edited).mean(),
               (g.best_symbol - g.auc_symbol).mean()))


@check("RRF k: does the headline fusion depend on the fusion constant?")
def c_rrf_k():
    ps = pd.read_csv(OUT / "per_source.csv").set_index(["source", "method"])
    out = []
    for src in ("co_edited", "symbol"):
        v = [float(ps.loc[(src, m), "auc"]) for m in
             ("rrf_pprpl_issue_path_k10", "rrf_pprpl_issue_path",
              "rrf_pprpl_issue_path_k200")]
        out.append("%s k=10/60/200 %.3f/%.3f/%.3f spread %.4f"
                   % (src, v[0], v[1], v[2], max(v) - min(v)))
    return " | ".join(out)


@check("worst-case shortfall in AUC, which does not depend on the competitor set")
def c_worst_gap():
    r = pd.read_csv(OUT / "rank_by_source.csv")
    r = r[r.method != "oracle"].sort_values("worst_gap").head(4)
    return "; ".join("%s gap %.3f (worst rank %d)" % (x.method, x.worst_gap, int(x.worst_case))
                     for x in r.itertuples())


@check("smallest p-value by unit, and whether the repository-level test is saturated")
def c_p_floor():
    import numpy as np
    from scipy import stats
    pw = pd.read_csv(OUT / "pairwise.csv")
    pw = pw[pw.source.isin(["co_edited", "symbol"])]
    out = []
    for u in ("pr", "repo"):
        r = pw.loc[pw[pw.unit == u].p.idxmin()]
        out.append("%s: p=%.2g (%s>%s, %s, n=%d)" % (u, r.p, r.a, r.b, r.source, r.n_pr))
    # normal-approximation signed-rank floor: every unit favours the same method
    n = 112
    z = (n * (n + 1) / 4) / np.sqrt(n * (n + 1) * (2 * n + 1) / 24)
    out.append("floor at n=%d: %.2g" % (n, 2 * stats.norm.sf(z)))
    return " | ".join(out)


@check("two-hop ball: median share of repository and median precision")
def c_ball():
    b = pd.read_csv(OUT / "ball.csv")
    prec = b.ball_recall * b.key_files / b.ball_files.where(b.ball_files > 0)
    return ("share median %.1f%% mean %.1f%% | precision median %.1f%% mean %.1f%% | "
            "recall mean %.1f%% | lift %.2f" % (
                100 * b.ball_share_of_repo.median(), 100 * b.ball_share_of_repo.mean(),
                100 * prec.median(), 100 * prec.mean(), 100 * b.ball_recall.mean(),
                b.ball_recall.mean() / b.ball_share_of_repo.mean()))


@check("introduction: repository size and key share, per pull request")
def c_intro_sizes():
    k = pd.read_csv(OUT / "key_size.csv")
    t = k.drop_duplicates("task_id").groupby("instance_id").repo_tokens.mean()
    share = (k.key_tokens / k.repo_tokens).groupby([k.source, k.instance_id]).mean()
    return ("median repo %d tokens (per PR) | PRs >128k %.1f%%, >200k %.1f%% | "
            "key share median %.2f%%" % (t.median(), 100 * (t > 128000).mean(),
                                         100 * (t > 200000).mean(), 100 * share.median()))


@check("single-file pull requests on the symbol key: which orderings lead")
def c_single():
    r = pd.read_parquet(OUT / "rows.parquet", columns=["instance_id", "method", "source",
                                                      "auc"])
    co = set(r[r.source == "co_edited"].instance_id)
    s = r[(r.source == "symbol") & ~r.instance_id.isin(co)]
    ps = pd.read_csv(OUT / "per_source.csv")
    fam = dict(zip(ps.method, ps.family))
    m = (s.groupby(["method", "instance_id"]).auc.mean().groupby("method").mean()
         .drop("oracle").sort_values(ascending=False).head(6))
    return "n=%d: %s" % (s.instance_id.nunique(), ", ".join(
        "%s(%s,%.3f)" % (k, fam.get(k, "?")[:4], v) for k, v in m.items()))


@check("direction: do the largest structural gaps all have an inward walk losing?")
def c_inward():
    pw = pd.read_csv(OUT / "pairwise.csv")
    st = {"bfs_und", "hops_lines", "ppr_und", "ppr_und_pl", "ppr_out", "ppr_out_pl",
          "ppr_in", "ppr_in_pl"}
    out = []
    for pop in ("all", "shared"):
        d = pw[(pw.unit == "repo") & (pw.stratum == "all") & (pw.source == "symbol")
               & (pw.population == pop) & pw.a.isin(st) & pw.b.isin(st)]
        d = d.assign(ad=d.delta.abs()).sort_values("ad", ascending=False)
        losers = [r.b if r.delta > 0 else r.a for r in d.itertuples()]
        n = next(i for i, x in enumerate(losers) if x not in ("ppr_in", "ppr_in_pl"))
        out.append("symbol/%s: first %d gaps have an inward loser" % (pop, n))
    return " | ".join(out)


@check("unit: which Holm verdicts change between pull request and repository as the unit")
def c_unit_flips():
    pw = pd.read_csv(OUT / "pairwise.csv")
    pw = pw[(pw.stratum == "all") & pw.source.isin(["co_edited", "symbol"])]
    k = ["source", "population", "a", "b"]
    m = pw[pw.unit == "pr"].merge(pw[pw.unit == "repo"], on=k, suffixes=("_pr", "_repo"))
    sig_pr, sig_repo = m.p_holm_pr < 0.05, m.p_holm_repo < 0.05
    return "%d comparisons; significant by PR %d; lost at repo %d; gained at repo %d" % (
        len(m), sig_pr.sum(), (sig_pr & ~sig_repo).sum(), (~sig_pr & sig_repo).sum())


@check("mixed model: same verdict as the repository-level Wilcoxon test?")
def c_mixed():
    mx = pd.read_csv(OUT / "mixed.csv")
    pw = pd.read_csv(OUT / "pairwise.csv")
    pw = pw[pw.unit == "repo"]
    rd = pd.read_csv(OUT / "redaction.csv")
    rd = rd[rd.arm == "names"] if "arm" in rd else rd
    grp = {"explicit": "names removed", "no_explicit": "nothing removed"}
    agree, differ = 0, []
    for r in mx.itertuples():
        if r.b.endswith("_rd"):
            w = rd[(rd.group == grp[r.stratum]) & (rd.source == r.source)
                   & (rd.method == r.a)].iloc[0]
        else:
            w = pw[(pw.source == r.source) & (pw.stratum == r.stratum)
                   & (pw.population == r.population)
                   & (((pw.a == r.a) & (pw.b == r.b)) | ((pw.a == r.b) & (pw.b == r.a)))].iloc[0]
        if (r.p_holm < 0.05) == (w.p_holm < 0.05):
            agree += 1
        else:
            differ.append("%s-%s %s/%s/%s mixed %+.3f p=%.2g, wilcoxon p=%.2g" % (
                r.a, r.b, r.source, r.stratum, r.population, r.estimate, r.p_holm, w.p_holm))
    return "agree %d of %d | differ: %s" % (agree, len(mx), "; ".join(differ) or "none")


@check("is the headline fusion ever significantly worse than a pure ordering?")
def c_fusion_never_worse():
    pw = pd.read_csv(OUT / "pairwise.csv")
    f = "rrf_pprpl_issue_path"
    pure = {"bfs_und", "hops_lines", "ppr_und", "ppr_und_pl", "ppr_out", "ppr_out_pl",
            "ppr_in", "ppr_in_pl", "pagerank", "bm25_seed", "path_seed", "bm25_issue",
            "bm25_issue_pl", "path_issue", "same_dir"}
    d = pw[(pw.unit == "repo") & pw.source.isin(["co_edited", "symbol"])
           & (((pw.a == f) & pw.b.isin(pure)) | ((pw.b == f) & pw.a.isin(pure)))].copy()
    d["other"] = [r.b if r.a == f else r.a for r in d.itertuples()]
    d["fmo"] = [r.delta if r.a == f else -r.delta for r in d.itertuples()]
    worse = d[(d.fmo < 0) & (d.p_holm < 0.05)]
    out = []
    for pop in ("shared", "all"):
        w = worse[worse.population == pop]
        out.append("%s: %s" % (pop, ", ".join(
            "%s/%s<%s %.3f" % (r.source, r.stratum, r.other, r.fmo) for r in w.itertuples())
            or "never"))
    return " | ".join(out)


@check("redaction arms: what each arm removes, and the decomposition under each")
def c_arms():
    rd = pd.read_csv(OUT / "redaction.csv")
    if "arm" not in rd:
        return "redaction.csv has no arm column - rerun analysis2"
    pw = pd.read_csv(OUT / "pairwise.csv")

    def twin(src, st):
        g = pw[(pw.unit == "repo") & (pw.population == "shared") & (pw.stratum == st)
               & (pw.source == src) & (pw.a == "rrf_pprpl_issue_path")
               & (pw.b == "rrf_pprpl_seedpath")]
        return float(g.delta.iloc[0])
    out = []
    for arm in rd.arm.unique():
        cells = []
        for src in ("co_edited", "symbol"):
            g = rd[(rd.arm == arm) & (rd.source == src)].set_index(["group", "method"])
            named = g.loc[("names removed", "rrf_pprpl_issue_path"), "delta"]
            unnamed = g.loc[("nothing removed", "rrf_pprpl_issue_path"), "delta"]
            gap = twin(src, "explicit") - twin(src, "no_explicit")
            cells.append("%s fusion named %.3f unnamed %.3f path_issue named %.3f "
                         "bm25_issue named %.3f | gap %.3f = leakage %.3f + rest %.3f" % (
                             src[:3], named, unnamed,
                             g.loc[("names removed", "path_issue"), "delta"],
                             g.loc[("names removed", "bm25_issue"), "delta"],
                             gap, named - unnamed, gap - (named - unnamed)))
        out.append("%s: %s" % (arm, " || ".join(cells)))
    return "\n     ".join(out)


@check("budget: do the leading orderings change if the AUC stops at 8,000 lines?")
def c_capped_budget():
    from depgraphs.analysis2 import shared_prs
    from depgraphs.study2 import FUSION_CTL, REDACTED_ALL, RRF_K_VARIANTS
    c = pd.read_parquet(OUT / "curves.parquet")
    c = c[c.source.isin(["co_edited", "symbol"]) & (c.budget <= 8000)]
    ctl = set(FUSION_CTL) | set(REDACTED_ALL) | set(RRF_K_VARIANTS)
    c = c[~c.method.isin(ctl)]
    pr = (c.groupby(["source", "method", "instance_id", "task_id"]).coverage.mean()
          .groupby(["source", "method", "instance_id"]).mean().reset_index())
    rows = pd.read_parquet(OUT / "rows.parquet", columns=["task_id", "instance_id", "method",
                                                          "source", "auc"])
    sh = shared_prs(rows)
    full = pd.read_csv(OUT / "per_source.csv")
    shd = pd.read_csv(OUT / "per_source_shared.csv")
    out = []
    for pop, g, ref in (("full", pr, full), ("matched", pr[pr.instance_id.isin(sh)], shd)):
        for src in ("co_edited", "symbol"):
            capped = (g[g.source == src].groupby("method").coverage.mean()
                      .drop("oracle").sort_values(ascending=False).index[:3].tolist())
            r = ref[(ref.source == src) & ref["rank"].notna() & (ref.method != "oracle")]
            orig = r.sort_values("rank").method.head(3).tolist()
            out.append("%s/%s top3 %s" % (pop, src, "same" if capped == orig
                                          else "capped %s vs %s" % (capped, orig)))
    return " | ".join(out)


@check("symbol key: share of its file references that are also co-edited files")
def c_symbol_overlap():
    import json
    from depgraphs.lexfeat import ROOT
    scored = set(pd.read_parquet(OUT / "rows.parquet", columns=["task_id"]).task_id)
    tot = both = 0
    for line in open(ROOT / "data" / "tasks.jsonl", encoding="utf-8"):
        t = json.loads(line)
        if t["task_id"] not in scored:
            continue
        s, c = set(t["keys"].get("symbol", [])), set(t["keys"].get("co_edited", []))
        tot += len(s)
        both += len(s & c)
    return "%d of %d symbol-key references also co-edited (%.1f%%)" % (both, tot,
                                                                        100 * both / tot)


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
