"""Check every number quoted in the paper against the file it came from.

A reviewer's suggestion, and the right one: rather than reading the manuscript for numbers
that disagree with the tables, compute each claimed number from the result files and assert
that the manuscript contains it. Each entry below pairs a *context* -- a literal phrase that
must occur in paper.tex, used to locate the sentence -- with a *value* computed here. The
check passes when the computed value, formatted as the paper formats it, occurs within a
window of text following the context.

This catches the failure mode that actually happened repeatedly in this project: a number
correct when written, left behind when the analysis under it changed.

Usage:  python -m depgraphs.claims
"""
from __future__ import annotations

import json
import sys

import pandas as pd

from depgraphs.lexfeat import ROOT
from depgraphs.study2 import OUT

PAPER = ROOT / "paper" / "paper.tex"
BACK, FORWARD = 400, 1100

ORDINAL = ["", "first", "second", "third", "fourth", "fifth", "sixth", "seventh",
           "eighth", "ninth", "tenth", "eleventh", "twelfth", "thirteenth",
           "fourteenth", "fifteenth", "sixteenth", "seventeenth", "eighteenth",
           "nineteenth", "twentieth", "twenty-first", "twenty-second",
           "twenty-third"]


def spellings(value: str) -> list[str]:
    """The paper writes 0.434 or .434, and a rank as a digit or as a word."""
    out = [value]
    if value.startswith("0."):
        out.append(value[1:])
    if value.isdigit() and int(value) < len(ORDINAL):
        out.append(ORDINAL[int(value)])
    return out


_cache: dict = {}


def csv(name: str) -> pd.DataFrame:
    if name not in _cache:
        _cache[name] = pd.read_csv(OUT / name)
    return _cache[name]


def auc(table: str, source: str, method: str, **where) -> float:
    d = csv(table)
    for k, v in where.items():
        d = d[d[k] == v]
    d = d[(d.source == source) & (d.method == method)]
    col = "auc" if "auc" in d.columns else "auc_no_leak"
    return float(d[col].iloc[0])


def rank(table: str, source: str, method: str, **where) -> int:
    d = csv(table)
    for k, v in where.items():
        d = d[d[k] == v]
    d = d[(d.source == source) & (d.method == method)]
    col = "rank" if "rank" in d.columns else "rank_no_leak"
    # the paper ranks without the oracle; the result files include it at rank 1
    return int(d[col].iloc[0]) - 1


def delta(a: str, b: str, source: str, stratum="all", population="shared") -> float:
    pw = csv("pairwise.csv")
    g = pw[(pw.unit == "repo") & (pw.stratum == stratum) & (pw.population == population)
           & (pw.source == source)
           & (((pw.a == a) & (pw.b == b)) | ((pw.a == b) & (pw.b == a)))]
    r = g.iloc[0]
    return float((1 if r.a == a else -1) * r.delta)


def p_holm(a: str, b: str, source: str, stratum="all", population="shared") -> float:
    pw = csv("pairwise.csv")
    g = pw[(pw.unit == "repo") & (pw.stratum == stratum) & (pw.population == population)
           & (pw.source == source)
           & (((pw.a == a) & (pw.b == b)) | ((pw.a == b) & (pw.b == a)))]
    return float(g.iloc[0].p_holm)


def redact_delta(method: str, source: str, group: str = "names removed",
                 arm: str = "names") -> float:
    d = csv("redaction.csv")
    if "arm" in d:
        d = d[d.arm == arm]
    r = d[(d.group == group) & (d.method == method) & (d.source == source)].iloc[0]
    return float(r.delta)


_ext = ROOT / "external" / "results" / "study2" / "predictions.json"
EXT = json.loads(_ext.read_text()) if _ext.exists() else {}
_cb = ROOT / "contextbench" / "results" / "study2" / "predictions.json"
CB = json.loads(_cb.read_text()) if _cb.exists() else {}
_sl = ROOT / "results" / "seedless" / "summary.json"
SL = json.loads(_sl.read_text()) if _sl.exists() else {}


def metric_delta(rule: str, source: str, a: str, b: str) -> float:
    p = csv("metric_pairs.csv")
    r = p[(p.rule == rule) & (p.source == source) & (p.a == a) & (p.b == b)].iloc[0]
    return float(r.delta)


def metric_auc(rule: str, source: str, method: str, population: str = "shared") -> dict:
    t = csv("metric_auc.csv")
    g = t[(t.rule == rule) & (t.source == source) & (t.population == population)]
    best = g[g.method != "oracle"].auc.max()
    r = g[g.method == method].iloc[0]
    return {"auc": float(r.auc), "rank": int(r["rank"]), "short": float(best - r.auc)}


def sl_auc(method: str, source: str) -> float:
    return float(SL["auc_all"][source][method])


def sl_delta(b: str, source: str, stratum: str = "all",
             a: str = "rrf_pprpl_issue_path") -> float:
    t = pd.read_csv(ROOT / "results" / "seedless" / "tests.csv")
    r = t[(t.stratum == stratum) & (t.source == source) & (t.a == a) & (t.b == b)].iloc[0]
    return float(r.delta)


def dn(what: str, source: str, stratum: str = "all") -> float:
    t = csv("dense_tests.csv")
    return float(t[(t.what == what) & (t.source == source) & (t.stratum == stratum)]
                 .iloc[0].delta)


def cb_test(name: str, b: str) -> dict:
    return next(t for t in CB[name]["tests"] if t["b"] == b)


def gap(source: str = "co_edited") -> float:
    """What the issue is worth to the fusion where it names a key file, minus where not."""
    return (delta("rrf_pprpl_issue_path", "rrf_pprpl_seedpath", source, stratum="explicit")
            - delta("rrf_pprpl_issue_path", "rrf_pprpl_seedpath", source,
                    stratum="no_explicit"))


def leak_share(arm: str, source: str = "co_edited") -> float:
    """The part of that gap an arm removes: its cost where the issue names a key file,
    less its cost where the issue names none."""
    return (redact_delta("rrf_pprpl_issue_path", source, arm=arm)
            - redact_delta("rrf_pprpl_issue_path", source, "nothing removed", arm))


def split_stat(what: str, source: str = "co_edited") -> int:
    h = csv("heldout.csv")
    top = h.chosen.value_counts().idxmax()
    if what == "selected":
        return int((h.chosen == top).sum())
    g = h[h.chosen == top]
    return int((g["rank_" + source] == 2).sum())


def pct(x: float) -> str:
    return "%.1f" % (100 * x)


def num3(x: float) -> str:
    """The paper writes AUC as 0.434 in prose and .434 in tables; accept either."""
    return "%.3f" % x


# --------------------------------------------------------------------------- the claims
def big(n: int) -> str:
    """1886 -> 1{,}886, as the paper writes it."""
    return "{:,}".format(int(n)).replace(",", "{,}")


def _corpus() -> dict:
    tasks = [json.loads(l) for l in open(ROOT / "data" / "tasks.jsonl", encoding="utf-8")]
    t = pd.DataFrame(tasks)
    rows = pd.read_parquet(OUT / "rows.parquet", columns=["task_id", "instance_id", "method",
                                                          "source", "n_nodes", "key_size"])
    scored = set(rows.task_id)
    t["scored"] = t.task_id.isin(scored)
    single = t[t.file_group == "single"]
    r = rows[rows.method == "random"]
    return {
        "sampled": len(pd.read_csv(ROOT / "data" / "sample_tasks.csv")),
        "tasks": len(t), "prs": t.instance_id.nunique(), "repos": t.repo_key.nunique(),
        "unscored": int((~t.scored).sum()),
        "unscored_single": int((~t.scored & (t.file_group == "single")).sum()),
        "single_tasks": len(single),
        "median_nodes": int(r.drop_duplicates("task_id").n_nodes.median()),
        "co_tasks": int(r[r.source == "co_edited"].task_id.nunique()),
        "co_prs": int(r[r.source == "co_edited"].instance_id.nunique()),
        "sym_tasks": int(r[r.source == "symbol"].task_id.nunique()),
        "sym_prs": int(r[r.source == "symbol"].instance_id.nunique()),
        "single_prs": int(len(set(r[r.source == "symbol"].instance_id)
                              - set(r[r.source == "co_edited"].instance_id))),
    }


def _unit_flips() -> dict:
    pw = csv("pairwise.csv")
    pw = pw[(pw.stratum == "all") & pw.source.isin(["co_edited", "symbol"])]
    k = ["source", "population", "a", "b"]
    m = pw[pw.unit == "pr"].merge(pw[pw.unit == "repo"], on=k, suffixes=("_pr", "_repo"))
    s1, s2 = m.p_holm_pr < 0.05, m.p_holm_repo < 0.05
    return {"sig_pr": int(s1.sum()), "lost": int((s1 & ~s2).sum()),
            "gained": int((~s1 & s2).sum()),
            "flips": int((m.delta_pr * m.delta_repo < 0)[s1 & s2].sum())}


def _mixed() -> dict:
    mx = csv("mixed.csv")
    r = mx[(mx.a == "hops_lines") & (mx.b == "path_issue") & (mx.source == "co_edited")
           & (mx.stratum == "all") & (mx.population == "all")].iloc[0]
    return {"n": len(mx), "hops_path": -float(r.estimate)}


def sysd(what: str, source: str) -> float:
    t = csv("dense_tests.csv")
    return float(t[(t.family == "systems") & (t.what == what) & (t.source == source)]
                 .iloc[0].delta)


def claims() -> list[tuple[str, str, str]]:
    """(context phrase that must appear in paper.tex, what is claimed, value to find)."""
    leak = csv("issue_path_leak.csv")
    sh = csv("per_source_shared.csv")
    co = _corpus()
    uf = _unit_flips()
    mx = _mixed()
    ball = csv("ball.csv")
    dist = csv("distance_profile.csv")
    tok = csv("token_calibration.csv").iloc[0]
    comp = csv("complementarity.csv")
    cm = csv("ceiling_method.csv")
    cm = cm[cm.budget == 8000]
    F, T = "rrf_pprpl_issue_path", "rrf_pprpl_seedpath"
    W = "issue worth, dense fusion"
    cb_ro = CB["exploratory_readonly"]
    cbt = pd.read_csv(ROOT / "contextbench" / "results" / "study2" / "per_source.csv")
    cbt = cbt[cbt["rank"].notna()].set_index(["source", "method"])
    dauc = csv("dense_auc.csv")
    dauc = dauc[dauc.population == "shared"].set_index(["source", "method"])
    kr = json.loads((ROOT / "results" / "key_rebuild" / "summary.json").read_text())

    def within2(src):
        d = dist[dist.source == src].set_index("hops").share
        return pct(d["1"] + d["2"])

    def worth(src, st="all"):
        return delta(F, T, src, stratum=st)

    dgap = dn(W, "co_edited", "explicit") - dn(W, "co_edited", "no_explicit")
    dwide = (dn("names cost (_rds), rrf_pprpl_dense_path", "co_edited", "explicit")
             - dn("names cost (_rds), rrf_pprpl_dense_path", "co_edited", "no_explicit"))
    shr = sh[sh.method.isin(["random", "oracle", F])].set_index(["source", "method"]).auc
    norm = {s: (shr[(s, F)] - shr[(s, "random")]) / (shr[(s, "oracle")] - shr[(s, "random")])
            for s in ("co_edited", "symbol")}
    E1 = EXT["E1"]
    sysnames = ["sys_aider_repomap", "sys_repograph_k2", "sys_locagent_bfs"]
    sys_ranks = [int(dauc.loc[(s, m), "rank_if_ranked"]) - 1 for s in ("co_edited", "symbol")
                 for m in sysnames]

    C = [
        # ---- abstract
        ("change tasks from", "abstract: scored tasks", big(co["tasks"] - co["unscored"])),
        ("the unchanged pipeline, drawn by our sampling rules", "corpus: ContextBench PRs",
         str(CB["descriptive"]["n_prs_gold"])),
        ("Our main contribution is a measurement protocol", "abstract: worth where named",
         num3(worth("co_edited", "explicit"))),
        ("Our main contribution is a measurement protocol", "abstract: worth elsewhere",
         num3(worth("co_edited", "no_explicit"))),
        ("Our main contribution is a measurement protocol", "abstract: elsewhere not significant",
         "non-significant" if p_holm(F, T, "co_edited", stratum="no_explicit") >= 0.05
         else "NOW-SIGNIFICANT"),
        ("Our main contribution is a measurement protocol", "abstract: 'about half'",
         "about half" if all(0.4 <= x / gap() <= 0.6 for x in (
             redact_delta(F, "co_edited"), leak_share("symbols"))) else "SHARE-CHANGED"),
        ("What survives is a protocol and a recommendation", "conclusion: worth where named",
         num3(worth("co_edited", "explicit"))),
        ("What survives is a protocol and a recommendation", "conclusion: worth elsewhere",
         num3(worth("co_edited", "no_explicit"))),

        # ---- contributions
        ("A protocol for measuring what issue text is worth", "contrib: worth where named",
         num3(worth("co_edited", "explicit"))),
        ("A protocol for measuring what issue text is worth", "contrib: names arm share",
         num3(redact_delta(F, "co_edited"))),
        ("A protocol for measuring what issue text is worth", "contrib: widest arm share",
         num3(leak_share("symbols"))),
        ("A protocol for measuring what issue text is worth", "contrib: worth elsewhere",
         num3(worth("co_edited", "no_explicit"))),
        ("Controls that changed conclusions here", "contrib: lost significance",
         str(uf["lost"])),
        ("Controls that changed conclusions here", "contrib: significant by PR",
         big(uf["sig_pr"])),
        ("Corrections to common arguments for graph retrieval", "contrib: ball recall",
         pct(ball.ball_recall.mean())),
        ("Corrections to common arguments for graph retrieval", "contrib: ball share",
         "%d" % round(100 * ball.ball_share_of_repo.mean())),

        # ---- related work
        ("Our rate,", "related: explicit naming rate", pct(leak.explicit.mean())),

        # ---- corpus
        ("pull requests from SWE-bench, SWE-bench-Live and SWE-rebench", "corpus: sampled PRs", big(co["sampled"])),
        ("This gives", "corpus: tasks", big(co["tasks"])),
        ("This gives", "corpus: PRs with a task", big(co["prs"])),
        ("This gives", "corpus: repositories", str(co["repos"])),
        ("pull requests edit no graph file", "corpus: PRs without a task",
         str(co["sampled"] - co["prs"])),
        ("Of the 711 unscored", "corpus: unscored tasks", str(co["unscored"])),
        ("Of the 711 unscored", "corpus: unscored single-file", str(co["unscored_single"])),
        ("Of the 711 unscored", "corpus: share of single-file tasks",
         pct(co["unscored_single"] / co["single_tasks"])),
        ("Of the 711 unscored", "corpus: single-file tasks", big(co["single_tasks"])),
        ("The median task's repository has", "corpus: median nodes", str(co["median_nodes"])),
        ("Available only when a pull", "corpus: co_edited tasks", big(co["co_tasks"])),
        ("Available only when a pull", "corpus: co_edited PRs", str(co["co_prs"])),
        ("change depends on.", "corpus: symbol tasks", big(co["sym_tasks"])),
        ("change depends on.", "corpus: symbol PRs", big(co["sym_prs"])),
        ("form the \\emph{matched population}", "corpus: matched PRs",
         str(int(sh[sh.source == "symbol"].n_pr.iloc[0]))),
        ("have no co-edited key because they edit a", "corpus: single-file PRs",
         str(co["single_prs"])),
        ("the unchanged pipeline, drawn by our sampling rules", "corpus: CB repos",
         str(CB["descriptive"]["n_repos_gold"])),

        # ---- metric
        ("Python source runs to", "metric: tokens per line",
         "%.2f" % tok.aggregate_tokens_per_line),
        ("Python source runs to", "metric: file versions", big(tok.n_blobs)),
        ("AUC has no intuitive scale", "metric: random, co",
         num3(shr[("co_edited", "random")])),
        ("AUC has no intuitive scale", "metric: oracle, co",
         num3(shr[("co_edited", "oracle")])),
        ("AUC has no intuitive scale", "metric: random, sym", num3(shr[("symbol", "random")])),
        ("AUC has no intuitive scale", "metric: oracle, sym", num3(shr[("symbol", "oracle")])),
        ("AUC has no intuitive scale", "metric: normalised fusion, co",
         "%d" % round(100 * norm["co_edited"])),
        ("AUC has no intuitive scale", "metric: normalised fusion, sym",
         "%d" % round(100 * norm["symbol"])),

        # ---- statistics
        ("The unit matters for borderline comparisons", "stats: significant by PR",
         big(uf["sig_pr"])),
        ("The unit matters for borderline comparisons", "stats: lost", str(uf["lost"])),
        ("The unit matters for borderline comparisons", "stats: gained", str(uf["gained"])),
        ("The unit matters for borderline comparisons", "stats: no sign flips",
         "no estimate changes sign" if uf["flips"] == 0 else "SIGN-FLIPS"),
        ("The unit matters for borderline comparisons", "stats: mixed comparisons",
         str(mx["n"])),
        ("where the mixed model finds path matching better", "stats: mixed hops vs path",
         num3(mx["hops_path"])),

        # ---- RQ1
        ("Table~\\ref{tab:main} is the comparison as it is usually run", "rq1: best structural co",
         ORDINAL[min(rank("per_source.csv", "co_edited", m) for m in
                     ("bfs_und", "hops_lines", "ppr_und", "ppr_und_pl", "ppr_out",
                      "ppr_out_pl", "ppr_in", "ppr_in_pl"))]),
        ("Table~\\ref{tab:main} is the comparison as it is usually run", "rq1: best lexical sym",
         ORDINAL[min(rank("per_source.csv", "symbol", m) for m in
                     ("bm25_seed", "path_seed", "bm25_issue", "bm25_issue_pl", "path_issue"))]),
        ("The individual reversals are large and significant", "rq1: path over walk, co",
         num3(delta("path_issue", "ppr_und_pl", "co_edited", population="all"))),
        ("The individual reversals are large and significant", "rq1: walk over path, sym",
         num3(delta("ppr_und_pl", "path_issue", "symbol", population="all"))),
        ("On the 702 pull requests carrying both keys", "rq1: outward walk full",
         num3(auc("per_source.csv", "symbol", "ppr_out_pl"))),
        ("On the 702 pull requests carrying both keys", "rq1: outward walk matched",
         num3(auc("per_source_shared.csv", "symbol", "ppr_out_pl"))),
        ("On the 702 pull requests carrying both keys", "rq1: outward walk matched rank",
         ORDINAL[rank("per_source_shared.csv", "symbol", "ppr_out_pl")]),
        ("On the 702 pull requests carrying both keys", "rq1: path matched rank",
         ORDINAL[rank("per_source_shared.csv", "symbol", "path_issue")]),
        ("On the 702 pull requests carrying both keys", "rq1: walk lead full",
         num3(delta("ppr_out_pl", "path_issue", "symbol", population="all"))),
        ("On the 702 pull requests carrying both keys", "rq1: walk lead matched",
         num3(delta("ppr_out_pl", "path_issue", "symbol"))),
        ("On the 702 pull requests carrying both keys", "rq1: hops lead matched",
         num3(delta("hops_lines", "path_issue", "symbol"))),
        ("The lexical half is largely the issue naming", "rq1: full-path rate",
         pct(leak["full"].mean())),
        ("The lexical half is largely the issue naming", "rq1: stem rate", pct(leak.stem.mean())),
        ("The lexical half is largely the issue naming", "rq1: explicit rate",
         pct(leak.explicit.mean())),
        ("population control (Table~\\ref{tab:leak})", "rq1: path rank primary",
         ORDINAL[rank("per_source_joint.csv", "co_edited", "path_issue",
                      stratum="no_explicit")]),
        ("population control (Table~\\ref{tab:leak})", "rq1: hops rank primary",
         ORDINAL[rank("per_source_joint.csv", "co_edited", "hops_lines",
                      stratum="no_explicit")]),
        ("population control (Table~\\ref{tab:leak})", "rq1: hops-path full-path control",
         num3(delta("hops_lines", "path_issue", "co_edited", stratum="no_full_path"))),
        ("population control (Table~\\ref{tab:leak})", "rq1: hops-path primary",
         num3(delta("hops_lines", "path_issue", "co_edited", stratum="no_explicit"))),
        ("population control (Table~\\ref{tab:leak})", "rq1: hops-path primary p",
         "%.2f" % p_holm("hops_lines", "path_issue", "co_edited", stratum="no_explicit")),
        ("explanation: its full path appears in", "rq1: seed full-path rate",
         pct(leak.seed_full.mean())),
        ("Which proxy to believe", "rq1: tau co", "%.2f" % CB["G4"]["co_edited"]["tau"]),
        ("Which proxy to believe", "rq1: tau sym", "%.2f" % CB["G4"]["symbol"]["tau"]),
        ("Which proxy to believe", "rq1: pprpl gold rank",
         ORDINAL[int(cbt.loc[("gold", "ppr_und_pl"), "rank"]) - 1]),
        ("Which proxy to believe", "rq1: pprout gold rank",
         ORDINAL[int(cbt.loc[("gold", "ppr_out_pl"), "rank"]) - 1]),

        # ---- RQ2
        ("Across tasks: an issue-free twin", "rq2: worth all co", num3(worth("co_edited"))),
        ("Across tasks: an issue-free twin", "rq2: worth all sym", num3(worth("symbol"))),
        ("Across tasks: an issue-free twin", "rq2: worth named co",
         num3(worth("co_edited", "explicit"))),
        ("Across tasks: an issue-free twin", "rq2: worth named sym",
         num3(worth("symbol", "explicit"))),
        ("Across tasks: an issue-free twin", "rq2: worth rest co",
         num3(worth("co_edited", "no_explicit"))),
        ("Across tasks: an issue-free twin", "rq2: worth rest sym",
         num3(worth("symbol", "no_explicit"))),
        ("Removing just the names costs", "rq2: names cost path", num3(redact_delta("path_issue",
                                                                                   "co_edited"))),
        ("Removing just the names costs", "rq2: names cost fusion",
         num3(redact_delta(F, "co_edited"))),
        ("Removing just the names costs", "rq2: paths arm fusion",
         num3(redact_delta(F, "co_edited", arm="paths"))),
        ("Removing just the names costs", "rq2: symbols arm fusion",
         num3(redact_delta(F, "co_edited", arm="symbols"))),
        ("Removing just the names costs", "rq2: wider arms elsewhere, low",
         num3(min(redact_delta(F, "co_edited", "nothing removed", a)
                  for a in ("paths", "symbols")))),
        ("Removing just the names costs", "rq2: wider arms elsewhere, high",
         num3(max(redact_delta(F, "co_edited", "nothing removed", a)
                  for a in ("paths", "symbols")))),
        ("The decomposition.} Both experiments", "rq2: gap", num3(gap())),
        ("The decomposition.} Both experiments", "rq2: names share", num3(redact_delta(F, "co_edited"))),
        ("The decomposition.} Both experiments", "rq2: widest share", num3(leak_share("symbols"))),
        ("The decomposition.} Both experiments", "rq2: symbol gap", num3(gap("symbol"))),
        ("The decomposition.} Both experiments", "rq2: symbol names share",
         num3(redact_delta(F, "symbol"))),
        ("The decomposition.} Both experiments", "rq2: symbol widest share",
         num3(leak_share("symbols", "symbol"))),
        ("A better reader.", "rq2: dense vs bm25 co", num3(dn("dense_issue vs bm25_issue",
                                                              "co_edited"))),
        ("A better reader.", "rq2: dense vs bm25 sym", num3(dn("dense_issue vs bm25_issue",
                                                               "symbol"))),
        ("A better reader.", "rq2: dense in fusion",
         num3(dn("rrf_pprpl_dense_path vs rrf_pprpl_issue_path", "co_edited"))),
        ("A better reader.", "rq2: dense worth unnamed co", num3(dn(W, "co_edited",
                                                                    "no_explicit"))),
        ("A better reader.", "rq2: dense worth unnamed sym", num3(dn(W, "symbol",
                                                                     "no_explicit"))),
        ("A better reader.", "rq2: dense worth named", num3(dn(W, "co_edited", "explicit"))),
        ("A better reader.", "rq2: dense gap", num3(dgap)),
        ("A better reader.", "rq2: dense share low",
         "%d" % round(100 * dn("names cost (_rd), rrf_pprpl_dense_path", "co_edited",
                               "explicit") / dgap)),
        ("A better reader.", "rq2: dense share high", "%d" % round(100 * dwide / dgap)),
        ("A better reader.", "rq2: bm25 share low", "%d" % round(100 * redact_delta(
            F, "co_edited") / gap())),
        ("A better reader.", "rq2: bm25 share high",
         "%d" % round(100 * leak_share("symbols") / gap())),

        # ---- RQ3
        ("quantity to optimise is the worst a method does", "rq3: over lexical co",
         num3(delta(F, "path_issue", "co_edited"))),
        ("quantity to optimise is the worst a method does", "rq3: over lexical sym",
         num3(delta(F, "path_issue", "symbol"))),
        ("quantity to optimise is the worst a method does", "rq3: over structural co",
         num3(delta(F, "hops_lines", "co_edited"))),
        ("quantity to optimise is the worst a method does", "rq3: over structural sym",
         num3(delta(F, "ppr_und_pl", "symbol"))),
        ("Held-out repositories.", "rq3: splits selected", str(split_stat("selected"))),
        ("Held-out repositories.", "rq3: confirmed co", str(split_stat("best", "co_edited"))),
        ("Held-out repositories.", "rq3: confirmed sym", str(split_stat("best", "symbol"))),
        ("Seven unseen repositories.", "rq3: E1 rank",
         "second" if E1["co_edited"]["rank"] == 3 and E1["symbol"]["rank"] == 3
         else "E1-RANK-CHANGED"),
        ("Seven unseen repositories.", "rq3: E1 worst shortfall", num3(E1["worst_shortfall"])),
        ("Seven unseen repositories.", "rq3: E4 co",
         num3(EXT["E4"]["named"][0]["estimate"])),
        ("Seven unseen repositories.", "rq3: E4 co p", "%.2f" % EXT["E4"]["named"][0]["p_holm"]),
        ("Seven unseen repositories.", "rq3: E4 PRs", str(EXT["E4"]["named_matched_prs"])),
        ("Seven unseen repositories.", "rq3: E paths arm",
         num3(EXT["descriptive"]["redaction_arms_named_matched"]["co_edited"]["_rdp"])),
        ("Seven unseen repositories.", "rq3: E symbols arm",
         num3(EXT["descriptive"]["redaction_arms_named_matched"]["co_edited"]["_rds"])),
        ("A human-annotated key.} On ContextBench", "rq3: G1 shortfall",
         num3(CB["G1"]["shortfall"])),
        ("A human-annotated key.} On ContextBench", "rq3: G2 low",
         num3(min(t["estimate"] for t in CB["G2"]["tests"]))),
        ("A human-annotated key.} On ContextBench", "rq3: G2 high",
         num3(max(t["estimate"] for t in CB["G2"]["tests"]))),
        ("Other cost rules.", "rq3: skip shortfall co",
         num3(metric_auc("lines, skip", "co_edited", F)["short"])),
        ("Other cost rules.", "rq3: skip pair co",
         "%+.3f" % metric_delta("lines, skip", "co_edited", F, "rrf_ppr_issue_path")),
        ("Other cost rules.", "rq3: skip pair sym",
         "%+.3f" % metric_delta("lines, skip", "symbol", F, "rrf_ppr_issue_path")),
        ("Other cost rules.", "rq3: stop pair co",
         "%+.3f" % delta(F, "rrf_ppr_issue_path", "co_edited")),
        ("Other cost rules.", "rq3: stop pair sym",
         "%+.3f" % delta(F, "rrf_ppr_issue_path", "symbol")),
        ("Without a free seed.} An agent", "rq3: dense guess correct",
         "%d" % round(100 * SL["guess_dense_correct"])),
        ("Without a free seed.} An agent", "rq3: seedless edited",
         num3(sl_auc("rrf_pprpl_dense_path_ds", "edited"))),
        ("Without a free seed.} An agent", "rq3: seedless symbol",
         num3(sl_auc("rrf_pprpl_dense_path_ds", "symbol"))),
        ("Without a free seed.} An agent", "rq3: over dense edited",
         num3(sl_delta("dense_issue", "edited", a="rrf_pprpl_dense_path_ds"))),
        ("Without a free seed.} An agent", "rq3: over dense symbol",
         num3(sl_delta("dense_issue", "symbol", a="rrf_pprpl_dense_path_ds"))),
        ("Without a free seed.} An agent", "rq3: unnamed tie",
         "%+.3f" % sl_delta("dense_issue", "edited", "not named", a="rrf_pprpl_dense_path_ds")),
        ("Without a free seed.} An agent", "rq3: bm25 guess correct",
         "%d" % round(100 * SL["guess_correct"])),
        ("Published systems' selectors.", "rq3: systems best rank", ORDINAL[min(sys_ranks)]),
        ("Published systems' selectors.", "rq3: systems worst rank", ORDINAL[max(sys_ranks)]),
        ("Published systems' selectors.", "rq3: systems gap co low",
         num3(min(sysd("%s vs %s" % (F, m), "co_edited") for m in sysnames))),
        ("Published systems' selectors.", "rq3: systems gap co high",
         num3(max(sysd("%s vs %s" % (F, m), "co_edited") for m in sysnames))),
        ("Published systems' selectors.", "rq3: systems gap sym low",
         num3(min(sysd("%s vs %s" % (F, m), "symbol") for m in sysnames))),
        ("Published systems' selectors.", "rq3: systems gap sym high",
         num3(max(sysd("%s vs %s" % (F, m), "symbol") for m in sysnames))),

        # ---- RQ4
        ("The two-hop neighbourhood is half the repository", "rq4: within two, sym",
         within2("symbol")),
        ("The two-hop neighbourhood is half the repository", "rq4: within two, co",
         within2("co_edited")),
        ("The two-hop neighbourhood is half the repository", "rq4: ball files",
         str(int(ball.ball_files.median()))),
        ("The two-hop neighbourhood is half the repository", "rq4: ball share median",
         pct(ball.ball_share_of_repo.median())),
        ("The two-hop neighbourhood is half the repository", "rq4: ball precision",
         pct((ball.ball_recall * ball.key_files
              / ball.ball_files.where(ball.ball_files > 0)).median())),
        ("The two-hop neighbourhood is half the repository", "rq4: ball lift",
         "%.2f" % (ball.ball_recall.mean() / ball.ball_share_of_repo.mean())),
        ("Direction: reversing a walk is costly", "rq4: outward sym",
         num3(auc("per_source.csv", "symbol", "ppr_out_pl"))),
        ("Direction: reversing a walk is costly", "rq4: inward sym",
         num3(auc("per_source.csv", "symbol", "ppr_in_pl"))),
        ("Direction: reversing a walk is costly", "rq4: inward rank",
         ORDINAL[rank("per_source.csv", "symbol", "ppr_in_pl")]),
        ("Direction: reversing a walk is costly", "rq4: gap full",
         num3(delta("ppr_out_pl", "ppr_in_pl", "symbol", population="all"))),
        ("Direction: reversing a walk is costly", "rq4: undirected",
         num3(auc("per_source.csv", "symbol", "ppr_und_pl"))),
        ("How much is a repository prior", "rq4: prior sym",
         num3(auc("per_source.csv", "symbol", "pagerank"))),
        ("How much is a repository prior", "rq4: prior margin share",
         "%d" % round(100 * (auc("per_source.csv", "symbol", "pagerank")
                             - auc("per_source.csv", "symbol", "random"))
                      / (auc("per_source.csv", "symbol", "ppr_out_pl")
                         - auc("per_source.csv", "symbol", "random")))),
        ("How much is a repository prior", "rq4: prior co",
         num3(auc("per_source.csv", "co_edited", "pagerank"))),
        ("How much is a repository prior", "rq4: random co",
         num3(auc("per_source.csv", "co_edited", "random"))),
        ("How much is a repository prior", "rq4: walk over prior co",
         num3(delta("ppr_und_pl", "pagerank", "co_edited", population="all"))),
        ("The signals find different files", "rq4: lex only co",
         pct(comp[(comp.source == "co_edited") & (comp.k == 20)].lex_only.iloc[0])),
        ("The signals find different files", "rq4: struct only co",
         pct(comp[(comp.source == "co_edited") & (comp.k == 20)].struct_only.iloc[0])),
        ("The signals find different files", "rq4: struct only sym",
         pct(comp[(comp.source == "symbol") & (comp.k == 20)].struct_only.iloc[0])),
        ("The signals find different files", "rq4: lex only sym",
         pct(comp[(comp.source == "symbol") & (comp.k == 20)].lex_only.iloc[0])),
        ("What the human key says about the graph", "rq4: read-only PRs", str(cb_ro["n_prs"])),
        ("What the human key says about the graph", "rq4: read-only vs path",
         num3(next(t for t in cb_ro["tests"] if t["a"] == F and t["b"] == "path_issue")
              ["estimate"])),
        ("What the human key says about the graph", "rq4: read-only vs bm25",
         num3(next(t for t in cb_ro["tests"] if t["a"] == F and t["b"] == "bm25_issue")
              ["estimate"])),
        ("The budget is rarely the constraint", "rq4: oracle full",
         pct(cm[(cm.source == "co_edited") & (cm.method == "oracle")].share_full.iloc[0])),
        ("The budget is rarely the constraint", "rq4: best full co",
         pct(cm[(cm.source == "co_edited") & (cm.method != "oracle")].share_full.max())),
        ("The budget is rarely the constraint", "rq4: best full sym",
         pct(cm[(cm.source == "symbol") & (cm.method != "oracle")].share_full.max())),

        # ---- threats
        ("rebuilding the keys of all", "threats: rebuilt PRs", big(kr["prs"])),
        ("rebuilding the keys of all", "threats: symbol keys changed",
         str(kr["symbol_key_differs"])),
        ("rebuilding the keys of all", "threats: max AUC change",
         "0.003" if max(kr["max_abs_auc_change"].values()) <= 0.003 else "BOUND-EXCEEDED"),
    ]
    return C


def main() -> int:
    text = PAPER.read_text(encoding="utf-8")
    bad = []
    for context, what, value in claims():
        at = text.find(context)
        if at < 0:
            bad.append("CONTEXT NOT FOUND  %-42s  (looking for %r)" % (what, context[:44]))
            continue
        if text.count(context) > 1:
            # an anchor that occurs twice would silently check the first occurrence
            bad.append("AMBIGUOUS CONTEXT  %-42s  (%r occurs %d times)"
                       % (what, context[:44], text.count(context)))
            continue
        window = text[max(0, at - BACK):at + FORWARD]
        if any(v in window for v in spellings(value)):
            print("  ok    %-42s %s" % (what, value))
        else:
            bad.append("MISMATCH           %-42s  computed %s, not in the sentence at %r"
                       % (what, value, context[:44]))
    print()
    for line in bad:
        print(line)
    print("\n%d claim(s) checked, %d disagree with the result files" % (len(claims()), len(bad)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
