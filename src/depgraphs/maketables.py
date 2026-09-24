"""Generate the paper's data tables from the result files.

Hand-transcribing twenty-odd rows per table is how a number ends up disagreeing with the
CSV it came from. Everything numeric in the results section is written here instead, into
paper/tab_*.tex, and the paper \\input's them. Captions, labels and prose stay in the
paper; only the rows are generated.

Usage:  python -m depgraphs.maketables
"""
from __future__ import annotations

import math

import pandas as pd

from depgraphs.lexfeat import ROOT
from depgraphs.study2 import FUSION, OUT, REDACTED_ALL, SCORED_ONLY

PAPER = ROOT / "paper"
BS = chr(92)
LF = chr(10)
NL = BS + BS

FAM = {"structure": "str", "lexical": "lex", "fusion": "fus", "global": "glo",
       "fusion-control": "f--", "reference": "ref"}

STRATA = ["explicit", "all", "no_full_path", "no_explicit", "no_stem"]
STRATUM_LABEL = {"explicit": "names a key file as code",
                 "all": "every task",
                 "no_full_path": "no full path quoted",
                 "no_explicit": "no explicit mention",
                 "no_stem": "no stem at all"}


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
    ps = ps[ps["rank"].notna()]
    ps["rank"] = ps["rank"].astype(int)
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
    r = pd.read_csv(OUT / "rank_by_source.csv").dropna(subset=["co_edited", "symbol"])
    r["worst"] = r[["co_edited", "symbol"]].max(axis=1)
    ps = pd.read_csv(OUT / "per_source.csv")
    fam = dict(zip(ps.method, ps.family))
    r = r[r.method != "oracle"].sort_values(["worst_gap", "method"])
    rows = ["%s & %s & %d & %d & %d & %s %s" % (
        m(x.method), FAM.get(fam.get(x.method, ""), "?"),
        x.co_edited, x.symbol, x.worst,
        ("%.3f" % x.worst_gap).lstrip("0"), NL) for x in r.itertuples()]
    write("worst", LF.join(rows))


def full_table():
    cm = pd.read_csv(OUT / "ceiling_method.csv")
    cm = cm[cm.budget == 8000]
    # controls are scored but never compared as reading orders, here as everywhere else
    cm = cm[~cm.method.isin(SCORED_ONLY)]
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
    """The leakage strata, each on the population matched to carry both keys.

    Both controls at once. Reading the strata off the full corpus would leave the symbol
    columns containing the single-file pull requests that the matching control exists to
    remove, which is the one place the two controls could have disagreed.
    """
    d = pd.read_csv(OUT / "per_source_joint.csv")
    d = d[d["rank"].notna()]
    rows = []
    for name in KEEP:
        cells = [m(name)]
        for st in ("no_full_path", "no_explicit", "no_stem"):
            for src in ("co_edited", "symbol"):
                g = d[(d.stratum == st) & (d.source == src) & (d.method == name)]
                cells.append("%s (%d)" % (("%.3f" % g.auc.iloc[0]).lstrip("0"),
                                          int(g["rank"].iloc[0])) if len(g) else "--")
        rows.append(" & ".join(cells) + " " + NL)
    n = [int(d[(d.stratum == st) & (d.source == "co_edited")].n_pr.iloc[0])
         for st in ("no_full_path", "no_explicit", "no_stem")]
    rows.append(BS + "midrule")
    rows.append(BS + "textit{pull requests} & " + " & ".join(
        r"%s" % ("{:,}".format(x).replace(",", "{,}")) for x in n
        for _ in (0, 1)) + " " + NL)
    write("leak", LF.join(rows))


def issue_table():
    """What the issue text adds to a fusion, by how explicitly the issue names the answer.

    Each pair is one fusion against the identical fusion with every issue-derived input
    replaced by its seed-derived counterpart: same walk, same number of lists, same BM25,
    no issue. The difference is therefore what the issue contributes, and it is read off
    within each leakage stratum rather than over the corpus as a whole.
    """
    pw = pd.read_csv(OUT / "pairwise.csv")
    pairs = [("rrf_pprpl_issue_path", "rrf_pprpl_seedpath"),
             ("rrf_hops_path", "rrf_hops_pathseed")]
    rows = []
    for st in STRATA:
        cells = [STRATUM_LABEL[st]]
        n = None
        for a, b in pairs:
            for src in ("co_edited", "symbol"):
                g = pw[(pw.unit == "repo") & (pw.stratum == st)
                       & (pw.population == "shared") & (pw.source == src)
                       & (((pw.a == a) & (pw.b == b)) | ((pw.a == b) & (pw.b == a)))]
                if not len(g):
                    cells.append("--")
                    continue
                r = g.iloc[0]
                d = (1 if r.a == a else -1) * r.delta
                n = int(r.n_pr)
                star = ("^{" + BS + "ast}" if r.p_holm < 0.05 else "")
                cells.append("$%+.3f%s$" % (d, star))
        rows.append(("%s & %d & " % (cells[0], n)) + " & ".join(cells[1:]) + " " + NL)
        if st == "all":
            rows.append(BS + "midrule")
    write("issue", LF.join(rows))


def shared_table():
    """The two keys re-scored on the pull requests that carry both of them."""
    sh = pd.read_csv(OUT / "per_source_shared.csv")
    full = pd.read_csv(OUT / "per_source.csv")
    sh, full = sh[sh["rank"].notna()], full[full["rank"].notna()]
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


def heldout_table():
    """How often each fusion is selected on one half, and how it then does on the other."""
    h = pd.read_csv(OUT / "heldout.csv")
    n = len(h)
    rows = []
    for name, k in h.chosen.value_counts().items():
        g = h[h.chosen == name]
        cells = [m(name), "%d/%d" % (k, n)]
        for src in ("co_edited", "symbol"):
            cells.append("%d/%d" % (int((g["rank_" + src] == 2).sum()), k))
            cells.append(("%.3f" % (g["best_" + src] - g["auc_" + src]).mean()).lstrip("0"))
        rows.append(" & ".join(cells) + " " + NL)
    write("heldout", LF.join(rows))


def _group_prs() -> dict:
    from depgraphs.analysis2 import leak_strata, shared_prs
    rows = pd.read_parquet(OUT / "rows.parquet",
                           columns=["task_id", "instance_id", "method", "source", "auc"])
    st = leak_strata(rows)
    out = {}
    for group, key in (("names removed", "explicit"), ("nothing removed", "no_explicit")):
        out[group] = len(shared_prs(rows[rows.task_id.isin(st[key])]))
    return out


PRS: dict = {}


def redaction_table():
    """What deleting the key files' names -- and, in the wider arms, their paths and the
    symbols they define -- from the issue costs, within task, per arm."""
    PRS.update(_group_prs())
    d = pd.read_csv(OUT / "redaction.csv")
    if "arm" not in d:
        d = d.assign(arm="names")
    arms = [a for a in ("names", "paths", "symbols") if a in set(d.arm)]
    order = ["path_issue", "bm25_issue", "rrf_hops_path", "rrf_pprpl_issue_path"]
    ncol = 1 + 2 * (1 + len(arms))
    rows = []
    for group in ("names removed", "nothing removed"):
        g0 = d[(d.group == group) & (d.arm == "names")]
        label = ("%s (%d pull requests in %d repositories)"
                 % ("issue names a key file as code" if group == "names removed"
                    else "issue names no key file as code",
                    PRS[group], int(g0.n.max())))
        rows.append(BS + "multicolumn{%d}{@{}l}{" % ncol + BS + "textit{%s}} %s"
                    % (label, NL))
        for name in order:
            cells = [m(name)]
            for src in ("co_edited", "symbol"):
                base = d[(d.group == group) & (d.method == name) & (d.source == src)]
                if not len(base):
                    break
                cells.append(("%.3f" % base.auc.iloc[0]).lstrip("0"))
                for arm in arms:
                    r = base[base.arm == arm].iloc[0]
                    star = "^{" + BS + "ast}" if r.p_holm < 0.05 else ""
                    # the column is the change caused by redaction, so a loss prints negative
                    cells.append("$%+.3f%s$" % (-r.delta, star))
            else:
                rows.append(" & ".join(cells) + " " + NL)
        if group == "names removed":
            rows.append(BS + "midrule")
    write("redact", LF.join(rows))


def comp_table():
    """How each key file is reached within the top k of each family (RQ4)."""
    c = pd.read_csv(OUT / "complementarity.csv")
    rows = []
    for src in ("co_edited", "symbol"):
        for x in c[c.source == src].sort_values("k").itertuples():
            rows.append("%s & %d & %s %s" % (m(src), x.k, " & ".join(
                "%.1f\\%%" % (100 * v)
                for v in (x.both, x.struct_only, x.lex_only, x.neither)), NL))
    write("comp", LF.join(rows))


def distance_table():
    """Key files by hop distance from the seed, and the size of the two-hop ball (RQ1)."""
    d = pd.read_csv(OUT / "distance_profile.csv").set_index(["source", "hops"])["share"]
    b = pd.read_csv(OUT / "ball.csv")
    hit = b.ball_recall * b.key_files
    prec = (hit / b.ball_files.where(b.ball_files > 0)).median()
    lift = b.ball_recall.mean() / b.ball_share_of_repo.mean()
    med = b[["ball_files", "ball_lines", "key_files", "key_lines"]].median()
    rows = ["%s & %s %s" % (m(src), " & ".join(
        "%.1f\\%%" % (100 * d.get((src, h), 0.0))
        for h in ("1", "2", "3+", "unreachable")), NL)
        for src in ("co_edited", "symbol")]
    rows.append(BS + "midrule")
    rows.append("%s{5}{l}{%s{The two-hop ball:} %d files, %s lines, %.0f\\%% of the "
                "repository} %s" % (BS + "multicolumn", BS + "emph", med.ball_files,
                                    "{:,}".format(int(med.ball_lines)).replace(",", "{,}"),
                                    100 * b.ball_share_of_repo.mean(), NL))
    rows.append("%s{5}{l}{%squad recall %.1f\\%%, precision %.1f\\%%, recall lift over a "
                "same-sized random sample %.2f$%stimes$} %s" % (
                    BS + "multicolumn", BS, 100 * b.ball_recall.mean(), 100 * prec, lift,
                    BS, NL))
    rows.append("%s{5}{l}{%s{The union key:} %d files, %s lines} %s" % (
        BS + "multicolumn", BS + "emph", med.key_files,
        "{:,}".format(int(med.key_lines)).replace(",", "{,}"), NL))
    write("distance", LF.join(rows))


def families_table():
    """Every Holm family in the paper: what is tested together, and how many tests."""
    pw = pd.read_csv(OUT / "pairwise.csv")
    rows = []
    g = pw.groupby(["unit", "population", "stratum"]).agg(
        fam=("source", "nunique"), n=("p", "size"))
    per = pw.groupby(["unit", "population", "stratum", "source"]).size()
    for (unit, pop, st), r in g.iterrows():
        sizes = sorted(set(per.loc[(unit, pop, st)]))
        rows.append("paired tests, %s as unit & %s & %s & %d & %s %s" % (
            "repository" if unit == "repo" else "pull request",
            "matched" if pop == "shared" else "full",
            st.replace("_", " "), r.fam, "/".join(map(str, sizes)), NL))
    rd = pd.read_csv(OUT / "redaction.csv")
    arms = rd.arm.unique() if "arm" in rd else ["names"]
    for arm in arms:
        n = int((rd.arm == arm).sum()) if "arm" in rd else len(rd)
        rows.append("redaction, %s arm & matched & by group & 1 & %d %s" % (arm, n, NL))
    mx = OUT / "mixed.csv"
    if mx.exists():
        rows.append("mixed model, headline comparisons & both & several & 1 & %d %s"
                    % (len(pd.read_csv(mx)), NL))
    write("families", LF.join(rows))


def mixed_table():
    """Headline comparisons re-estimated with a random intercept per repository."""
    d = pd.read_csv(OUT / "mixed.csv")
    pops = {"all": "full", "shared": "matched"}
    rows = []
    for x in d.itertuples():
        p = ("$<10^{%d}$" % (math.floor(math.log10(x.p_holm)) + 1)
             if x.p_holm < 0.001 else "%.3f" % x.p_holm if x.p_holm < 1 else "1")
        rows.append("%s & %s & %s & %s & %s & %d & %+.3f %s & %s %s" % (
            m(x.a), m(x.b), m(x.source), x.stratum.replace("_", " "), pops[x.population],
            x.n_pr, x.estimate, ci(x.ci_lo, x.ci_hi).replace("[.", "[0.").replace(",.", ",0.")
            .replace("-.", "-0."), p, NL))
    write("mixed", LF.join(rows))


def external_table():
    """The four predictions of paper/external_prereg.md and what the external set showed."""
    import json
    f = ROOT / "external" / "results" / "study2" / "predictions.json"
    if not f.exists():
        return
    r = json.loads(f.read_text())
    ok = {True: "pass", False: BS + "textbf{fail}", None: "not testable"}

    def est(t):
        return "%+.3f ($p_{%s{Holm}} = %.3f$)" % (t["estimate"], BS + "text", t["p_holm"])
    e1, e2, e3, e4 = r["E1"], r["E2"], r["E3"], r["E4"]
    worst2 = min(e2["tests"], key=lambda t: t["estimate"])
    rows = [
        "E1 & fusion in the top three non-oracle orderings under both keys, worst shortfall "
        "$" + BS + "le 0.030$ & rank %d and %d (oracle included); shortfall %.3f & %s %s" % (
            e1["co_edited"]["rank"], e1["symbol"]["rank"], e1["worst_shortfall"],
            ok[e1["pass"]], NL),
        "E2 & fusion never significantly worse than four pure orderings, either key & "
        "smallest difference %s & %s %s" % (est(worst2), ok[e2["pass"]], NL),
        "E3 & outward walk beats inward on the symbol key & %+.3f ($p = %.3f$) & %s %s" % (
            e3["estimate"], e3["p"], ok[e3["pass"]], NL),
        "E4 & names redaction costs the fusion under both keys; nothing where nothing is named "
        "& %s and %s; control $" % tuple(est(t) for t in e4["named"])
        + BS + "le %.3f$ & %s %s" % (max(abs(v) for v in e4["unnamed_mean_move"].values()),
                                    ok[e4["pass"]], NL),
    ]
    write("external", LF.join(rows))


def contextbench_table():
    """The four predictions of paper/contextbench_prereg.md and what the human key showed."""
    import json
    f = ROOT / "contextbench" / "results" / "study2" / "predictions.json"
    if not f.exists():
        return
    r = json.loads(f.read_text())
    ok = {True: "pass", False: BS + "textbf{fail}"}
    g1, g2, g3, g4 = r["G1"], r["G2"], r["G3"], r["G4"]
    worst2 = min(g2["tests"], key=lambda t: t["estimate"])
    rows = [
        "G1 & fusion in the top three non-oracle orderings on the human key, shortfall "
        "$" + BS + "le 0.030$ & rank %d (oracle included); shortfall %.3f & %s %s" % (
            g1["rank"], g1["shortfall"], ok[g1["pass"]], NL),
        "G2 & fusion never significantly worse than four pure orderings & smallest "
        "difference %+.3f ($p_{%s{Holm}} %s$) & %s %s" % (
            worst2["estimate"], BS + "text", ("< 0.001" if worst2["p_holm"] < 0.001
                                              else "= %.3f" % worst2["p_holm"]),
            ok[g2["pass"]], NL),
        "G3 & outward walk beats inward & %+.3f ($p = %.3f$) & %s %s" % (
            g3["estimate"], g3["p"], ok[g3["pass"]], NL),
        "G4 & Kendall $" + BS + "tau " + BS + "ge 0.5$ between the human key's ranking and "
        "each proxy's & symbol %.2f, co-edited %.2f & %s %s" % (
            g4["symbol"]["tau"], g4["co_edited"]["tau"], ok[g4["pass"]], NL),
    ]
    write("cb_pred", LF.join(rows))

    t = pd.read_csv(f.parent / "per_source.csv")
    t = t[t["rank"].notna()]
    au = t.pivot(index="method", columns="source", values="auc")
    rk = t.pivot(index="method", columns="source", values="rank").astype(int)
    keys = ["gold", "gold_readonly", "co_edited", "symbol"]
    show = ["rrf_hops_issue_path", "rrf_pprpl_issue_path", "rrf_hops_path", "bm25_issue",
            "path_issue", "hops_lines", "ppr_und_pl", "ppr_out_pl", "pagerank", "random"]
    out = []
    for name in show:
        out.append(m(name) + " & " + " & ".join(
            "%s (%d)" % (("%.3f" % au.loc[name, k]).lstrip("0"), rk.loc[name, k])
            for k in keys) + " " + NL)
    out.append(BS + "midrule")
    out.append("oracle & " + " & ".join(("%.3f" % au.loc["oracle", k]).lstrip("0")
                                          for k in keys) + " " + NL)
    write("cb_auc", LF.join(out))


def metric_table():
    """Ranks of the leading orderings under the three cost rules, matched population."""
    f = OUT / "metric_auc.csv"
    if not f.exists():
        return
    t = pd.read_csv(f)
    t = t[t.population == "shared"]
    rules = ["lines, stop", "lines, skip", "files"]
    show = ["rrf_pprpl_issue_path", "rrf_ppr_issue_path", "rrf_hops_issue_path",
            "rrf_hops_path", "hops_lines", "ppr_und_pl", "ppr_und", "path_issue",
            "bm25_issue"]
    out = []
    for name in show:
        cells = []
        for src in ("co_edited", "symbol"):
            for rule in rules:
                g = t[(t.method == name) & (t.source == src) & (t.rule == rule)].iloc[0]
                cells.append("%s (%d)" % (("%.3f" % g.auc).lstrip("0"), int(g["rank"])))
        out.append(m(name) + " & " + " & ".join(cells) + " " + NL)
    write("metric", LF.join(out))


def seedless_table():
    """Without a free seed: AUC by key and by whether the issue names an edited file."""
    f = ROOT / "results" / "seedless" / "rows.parquet"
    if not f.exists():
        return
    d = pd.read_parquet(f)
    show = ["rrf_pprpl_dense_path", "rrf_pprpl_issue_path", "rrf_hops_path", "localiser",
            "dense_issue", "path_issue", "bm25_issue", "ppr_und_pl", "hops_lines", "random"]
    show = [s for s in show if s in set(d.method)]
    g = d.groupby(["method", "source", "named"]).auc.mean()
    a = d.groupby(["method", "source"]).auc.mean()
    label = {"localiser": BS + "textit{issue-only fusion (picks the seed)}"}
    out = []
    for name in show:
        cells = []
        for src in ("edited", "symbol"):
            cells += [a[(name, src)], g[(name, src, True)], g[(name, src, False)]]
        out.append(label.get(name, m(name)) + " & " + " & ".join(
            ("%.3f" % c).lstrip("0") for c in cells) + " " + NL)
    out.append(BS + "midrule")
    cells = []
    for src in ("edited", "symbol"):
        cells += [a[("oracle", src)], g[("oracle", src, True)], g[("oracle", src, False)]]
    out.append("oracle & " + " & ".join(("%.3f" % c).lstrip("0") for c in cells) + " " + NL)
    write("seedless", LF.join(out))


def dense_tables():
    """The dense retriever against BM25, and the decomposition for each fusion."""
    fa, ft = OUT / "dense_auc.csv", OUT / "dense_tests.csv"
    if not (fa.exists() and ft.exists()):
        return
    a = pd.read_csv(fa)
    a = a[a.population == "shared"]
    show = ["rrf_pprpl_issue_path_dense", "rrf_pprpl_dense_path", "rrf_pprpl_issue_path",
            "rrf_pprpl_dense", "dense_issue", "path_issue", "bm25_issue", "dense_seed",
            "bm25_seed"]
    out = []
    for name in show:
        cells = []
        for src in ("co_edited", "symbol"):
            r = a[(a.method == name) & (a.source == src)].iloc[0]
            cells.append("%s (%d)" % (("%.3f" % r.auc).lstrip("0"), int(r.rank_if_ranked)))
        out.append(m(name) + " & " + " & ".join(cells) + " " + NL)
    write("dense_auc", LF.join(out))

    t = pd.read_csv(ft)
    t = t[t.family == "decomposition"]

    def cell(what, stratum, src):
        r = t[(t.what == what) & (t.stratum == stratum) & (t.source == src)].iloc[0]
        d = r.delta
        star = "^{" + BS + "ast}" if r.p_holm < 0.05 else ""
        return "$%+.3f%s$" % (d, star)
    rows = [("issue worth, named", "explicit", "issue worth, %s fusion"),
            ("issue worth, not named", "no_explicit", "issue worth, %s fusion"),
            ("names arm, named", "explicit", "names cost (_rd), %s"),
            ("paths arm, named", "explicit", "names cost (_rdp), %s"),
            ("symbols arm, named", "explicit", "names cost (_rds), %s"),
            ("symbols arm, not named", "no_explicit", "names cost (_rds), %s")]
    fus = {"BM25": ("BM25", "rrf_pprpl_issue_path"), "dense": ("dense", "rrf_pprpl_dense_path")}
    out = []
    for label, st, pat in rows:
        cells = []
        for src in ("co_edited", "symbol"):
            for kind in ("BM25", "dense"):
                word, meth = fus[kind]
                what = pat % (word if "worth" in pat else meth)
                cells.append(cell(what, st, src))
        out.append(label + " & " + " & ".join(cells) + " " + NL)
    write("dense_decomp", LF.join(out))


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
    issue_table()
    heldout_table()
    redaction_table()
    comp_table()
    distance_table()
    families_table()
    mixed_table()
    external_table()
    contextbench_table()
    metric_table()
    seedless_table()
    dense_tables()
    figure_data()


if __name__ == "__main__":
    main()
