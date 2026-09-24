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
BACK, FORWARD = 400, 700

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
    return int(d[col].iloc[0])


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
def claims() -> list[tuple[str, str, str]]:
    """(context phrase that must appear in paper.tex, what is claimed, value to find)."""
    leak = csv("issue_path_leak.csv")
    n = len(leak)
    inc_only = int(((leak["full"] == 0) & (leak["explicit"] == 0)
                    & (leak["stem"] > 0)).sum())
    ps, joint = csv("per_source.csv"), csv("per_source_joint.csv")
    sh = csv("per_source_shared.csv")

    C = [
        # ---- leakage rates
        ("A mention is \\emph{explicit}", "explicit rate", pct(leak.explicit.mean())),
        ("The full path of a key file appears verbatim", "full-path rate",
         pct(leak["full"].mean())),
        ("The full path of a key file appears verbatim", "stem rate",
         pct(leak.stem.mean())),
        ("A further", "incidental-only rate", pct(inc_only / n)),
        ("issues quoting no full key path", "no-full-path tasks",
         "{:,}".format(int((leak["full"] == 0).sum())).replace(",", "{,}")),
        ("issues quoting no full key path", "no-explicit tasks",
         "{:,}".format(int(((leak["full"] == 0) & (leak["explicit"] == 0)).sum()))
         .replace(",", "{,}")),
        ("issues quoting no full key path", "no-stem tasks",
         "{:,}".format(int(((leak["full"] == 0) & (leak["stem"] == 0)).sum()))
         .replace(",", "{,}")),

        # ---- the issue ablation, the paper's headline
        ("Over the corpus the issue is worth", "issue worth, co_edited, all corpus",
         num3(delta("rrf_pprpl_issue_path", "rrf_pprpl_seedpath", "co_edited"))),
        ("Over the corpus the issue is worth", "issue worth, symbol, all corpus",
         num3(delta("rrf_pprpl_issue_path", "rrf_pprpl_seedpath", "symbol"))),
        ("that becomes", "issue worth where explicit, co_edited",
         num3(delta("rrf_pprpl_issue_path", "rrf_pprpl_seedpath", "co_edited",
                    stratum="explicit"))),
        ("that becomes", "issue worth where explicit, symbol",
         num3(delta("rrf_pprpl_issue_path", "rrf_pprpl_seedpath", "symbol",
                    stratum="explicit"))),
        ("that becomes", "issue worth where not, co_edited",
         num3(delta("rrf_pprpl_issue_path", "rrf_pprpl_seedpath", "co_edited",
                    stratum="no_explicit"))),
        ("that becomes", "issue worth where not, symbol",
         num3(delta("rrf_pprpl_issue_path", "rrf_pprpl_seedpath", "symbol",
                    stratum="no_explicit"))),
        ("requiring the stem to be absent as well", "issue worth, no stem, co_edited",
         num3(delta("rrf_pprpl_issue_path", "rrf_pprpl_seedpath", "co_edited",
                    stratum="no_stem"))),
        ("The issue-free twins of Section",
         "issue-free twin over its own walk",
         num3(delta("rrf_pprpl_seedpath", "ppr_und_pl", "co_edited", population="all"))),

        # ---- the decomposition
        ("the issue as a whole is worth", "issue worth where explicit, co_edited",
         num3(delta("rrf_pprpl_issue_path", "rrf_pprpl_seedpath", "co_edited",
                    stratum="explicit"))),
        ("Of that, the names", "names share of it, co_edited",
         num3(redact_delta("rrf_pprpl_issue_path", "co_edited"))),
        ("the issue as a" + chr(10) + "whole is worth", "issue worth where not, co_edited",
         num3(delta("rrf_pprpl_issue_path", "rrf_pprpl_seedpath", "co_edited",
                    stratum="no_explicit"))),

        # ---- population matching
        ("the 702 pull requests that carry both",
         "matched population size",
         "{:,}".format(int(sh[sh.source == "symbol"].n_pr.iloc[0])).replace(",", "{,}")),
        ("Reciprocal-rank fusion of a\nlength-aware walk", "fusion over best lexical, co_ed",
         num3(delta("rrf_pprpl_issue_path", "path_issue", "co_edited"))),
        ("Reciprocal-rank fusion of a\nlength-aware walk", "fusion over best lexical, sym",
         num3(delta("rrf_pprpl_issue_path", "path_issue", "symbol"))),
        ("Reciprocal-rank fusion of a\nlength-aware walk", "fusion over best structural, co_ed",
         num3(delta("rrf_pprpl_issue_path", "hops_lines", "co_edited"))),
        ("Reciprocal-rank fusion of a\nlength-aware walk", "fusion over best structural, sym",
         num3(delta("rrf_pprpl_issue_path", "ppr_und_pl", "symbol"))),

        # ---- held-out confirmation over repeated splits
        ("is selected in", "splits selecting the winner", str(split_stat("selected"))),
        ("and in 195 of those it is the best", "splits confirming it on co_edited", str(split_stat("best", "co_edited"))),
        ("did not select it,", "splits confirming it on symbol",
         str(split_stat("best", "symbol"))),

        # ---- redaction: the within-task experiment
        ("removing just the names costs", "redaction cost, path_issue, co_edited",
         num3(redact_delta("path_issue", "co_edited"))),
        ("removing just the names costs", "redaction cost, path_issue, symbol",
         num3(redact_delta("path_issue", "symbol"))),
        ("and the best fusion 0.061 and", "redaction cost, fusion, co_edited",
         num3(redact_delta("rrf_pprpl_issue_path", "co_edited"))),
        ("and the best fusion 0.061 and", "redaction cost, fusion, symbol",
         num3(redact_delta("rrf_pprpl_issue_path", "symbol"))),
        ("where the names arm found nothing to remove",
         "redaction is a no-op where nothing was removed",
         "0.002" if all(abs(redact_delta(m, src, "nothing removed")) <= 0.0025
                        for m in ("path_issue", "bm25_issue", "rrf_hops_path",
                                  "rrf_pprpl_issue_path")
                        for src in ("co_edited", "symbol")) else "CONTROL-ARM-NOT-FLAT"),

        # ---- the leakage strata, jointly controlled
        ("Under the weak\nfull-path control it barely moves", "path_issue full corpus",
         num3(auc("per_source.csv", "co_edited", "path_issue"))),
        ("Under the weak\nfull-path control it barely moves", "path_issue, no full path",
         num3(auc("per_source_joint.csv", "co_edited", "path_issue",
                  stratum="no_full_path"))),
        ("Under the\nprimary control it falls to", "path_issue, no explicit",
         num3(auc("per_source_joint.csv", "co_edited", "path_issue",
                  stratum="no_explicit"))),
        ("under the strictest, to", "path_issue, no stem",
         num3(auc("per_source_joint.csv", "co_edited", "path_issue", stratum="no_stem"))),
        ("and \\m{hops\\_lines} lead instead", "ppr_und_pl symbol primary",
         num3(auc("per_source_joint.csv", "symbol", "ppr_und_pl", stratum="no_explicit"))),
        ("and \\m{hops\\_lines} lead instead", "hops_lines symbol primary",
         num3(auc("per_source_joint.csv", "symbol", "hops_lines", stratum="no_explicit"))),
        ("with the best fusion fourth at", "fusion symbol primary",
         num3(auc("per_source_joint.csv", "symbol", "rrf_pprpl_issue_path",
                  stratum="no_explicit"))),
        ("on co-edited\nfiles is", "hops_lines over path_issue, no full path",
         num3(abs(delta("hops_lines", "path_issue", "co_edited",
                        stratum="no_full_path")))),
        ("under the\nprimary control ($p_{\\text{Holm}}",
         "hops_lines over path_issue, primary",
         num3(delta("hops_lines", "path_issue", "co_edited", stratum="no_explicit"))),
        ("under the\nprimary control ($p_{\\text{Holm}}",
         "hops_lines over path_issue, primary, p_Holm",
         "%.2f" % p_holm("hops_lines", "path_issue", "co_edited", stratum="no_explicit")),
        ("under the\nprimary control ($p_{\\text{Holm}}",
         "hops_lines over path_issue, strictest, p_Holm",
         "%.2f" % p_holm("hops_lines", "path_issue", "co_edited", stratum="no_stem")),

        # ---- the rank movements the leakage section states in words
        (r"On the full corpus \m{path\_issue} is", "path_issue rank, full corpus",
         str(rank("per_source.csv", "co_edited", "path_issue"))),
        ("Under the weak", "path_issue rank, no full path",
         str(rank("per_source_joint.csv", "co_edited", "path_issue",
                  stratum="no_full_path"))),
        ("primary control it falls to", "path_issue rank, no explicit",
         str(rank("per_source_joint.csv", "co_edited", "path_issue",
                  stratum="no_explicit"))),
        ("under the strictest, to", "path_issue rank, no stem",
         str(rank("per_source_joint.csv", "co_edited", "path_issue",
                  stratum="no_stem"))),
        ("pure structure, no issue text --- rises from", "hops_lines rank, full corpus",
         str(rank("per_source.csv", "co_edited", "hops_lines"))),
        ("pure structure, no issue text --- rises from", "hops_lines rank, no explicit",
         str(rank("per_source_joint.csv", "co_edited", "hops_lines",
                  stratum="no_explicit"))),

        # ---- the length-aware ablation
        ("their worst-case ranks are", "length-aware ablation, co_edited",
         num3(delta("rrf_pprpl_issue_path", "rrf_ppr_issue_path", "co_edited"))),
        ("their worst-case ranks are", "length-aware ablation, symbol",
         num3(delta("rrf_pprpl_issue_path", "rrf_ppr_issue_path", "symbol"))),
        ("their worst-case ranks are", "length-aware ablation, unscaled worst rank",
         str(int(csv("rank_by_source.csv").set_index("method")
                 .loc["rrf_ppr_issue_path", "worst_case"]))),
        ("fusions differing only in that are", "contributions: length-aware pair, co_edited",
         num3(delta("rrf_pprpl_issue_path", "rrf_ppr_issue_path", "co_edited"))),
        ("fusions differing only in that are", "contributions: length-aware pair, symbol",
         num3(delta("rrf_pprpl_issue_path", "rrf_ppr_issue_path", "symbol"))),

        # ---- size quartiles, on the same rank scale as everything else
        # ---- size quartiles, on the same rank scale as everything else
        ("largest quartile, issue-text path matching is", "path_issue Q4 co_edited rank",
         str(rank("by_size.csv", "co_edited", "path_issue", size_q="Q4"))),
        ("largest quartile, issue-text path matching is", "path_issue Q4 symbol rank",
         str(rank("by_size.csv", "symbol", "path_issue", size_q="Q4"))),
        ("never falls below", "rrf_hops_path worst size-cell rank",
         str(int(csv("by_size.csv").pipe(
             lambda d: d[(d.method == "rrf_hops_path")
                         & d.source.isin(["co_edited", "symbol"])]["rank"].max())))),

        # ---- direction
        ("The like-for-like gap is",
         "direction, matched",
         num3(delta("ppr_out_pl", "ppr_in_pl", "symbol"))),
        ("undirected walk leads by",
         "undirected vs outward walk, matched, p_Holm",
         "%.2f" % p_holm("ppr_und_pl", "ppr_out_pl", "symbol")),
        ("Committing to an orientation costs", "orientation cost on co_edited, smallest",
         num3(min(delta(u, d, "co_edited", population="all")
                  for u, d in (("ppr_und_pl", "ppr_out_pl"), ("ppr_und_pl", "ppr_in_pl"),
                               ("ppr_und", "ppr_out"), ("ppr_und", "ppr_in"))))),
        ("Committing to an orientation costs", "orientation cost on co_edited, largest",
         num3(max(delta(u, d, "co_edited", population="all")
                  for u, d in (("ppr_und_pl", "ppr_out_pl"), ("ppr_und_pl", "ppr_in_pl"),
                               ("ppr_und", "ppr_out"), ("ppr_und", "ppr_in"))))),

        # ---- the priors, the seed-path control, the twin and the size quartiles
        ("difference is significant but negligible", "pagerank over random, co_edited, p_Holm",
         "%.3f" % p_holm("pagerank", "random", "co_edited", population="all")),
        ("path instead of the issue, scores", "path_issue over path_seed, co_edited",
         num3(delta("path_issue", "path_seed", "co_edited", population="all"))),
        ("path instead of the issue, scores", "path_issue over path_seed, symbol",
         num3(delta("path_issue", "path_seed", "symbol", population="all"))),
        ("path instead of the issue, scores", "path_issue over path_seed, symbol, p_Holm",
         "%.2f" % p_holm("path_issue", "path_seed", "symbol", population="all")),
        ("beats its own walk", "seed-path twin over its walk, co_edited",
         num3(delta("rrf_pprpl_seedpath", "ppr_und_pl", "co_edited", population="all"))),
        ("beats its own walk", "issue-aware fusion over its twin, co_edited",
         num3(delta("rrf_pprpl_issue_path", "rrf_pprpl_seedpath", "co_edited",
                    population="all"))),
        ("between a third and seven tenths of what the issue adds",
         "issue-aware fusion over its twin, matched, every task",
         num3(delta("rrf_pprpl_issue_path", "rrf_pprpl_seedpath", "co_edited"))),
        ("between a third and seven tenths of what the issue adds",
         "redaction cost, fusion, co_edited, every task",
         num3(redact_delta("rrf_pprpl_issue_path", "co_edited", "all tasks"))),
        ("between a third and seven tenths of what the issue adds",
         "redaction cost, fusion, co_edited, every task, paths arm",
         num3(redact_delta("rrf_pprpl_issue_path", "co_edited", "all tasks", "paths"))),
        ("between a third and seven tenths of what the issue adds",
         "redaction cost, fusion, co_edited, every task, symbols arm",
         num3(redact_delta("rrf_pprpl_issue_path", "co_edited", "all tasks", "symbols"))),
        ("The wider arms cost more, as they must", "path_issue, paths arm",
         num3(redact_delta("path_issue", "co_edited", arm="paths"))),
        ("The wider arms cost more, as they must", "path_issue, symbols arm",
         num3(redact_delta("path_issue", "co_edited", arm="symbols"))),
        ("The wider arms cost more, as they must", "fusion, paths arm",
         num3(redact_delta("rrf_pprpl_issue_path", "co_edited", arm="paths"))),
        ("The wider arms cost more, as they must", "fusion, symbols arm",
         num3(redact_delta("rrf_pprpl_issue_path", "co_edited", arm="symbols"))),
        ("The wider arms do find something there", "fusion, paths arm, nothing named",
         num3(redact_delta("rrf_pprpl_issue_path", "co_edited", "nothing removed", "paths"))),
        ("The wider arms do find something there", "fusion, symbols arm, nothing named",
         num3(redact_delta("rrf_pprpl_issue_path", "co_edited", "nothing removed",
                           "symbols"))),
        # the abstract states these in words; the words are checked against the ratios
        ("as it does in two tasks in five: there it is worth", "abstract: 'ten times'",
         "ten times" if 9 <= (delta("rrf_pprpl_issue_path", "rrf_pprpl_seedpath", "co_edited",
                                    stratum="explicit")
                              / delta("rrf_pprpl_issue_path", "rrf_pprpl_seedpath",
                                      "co_edited", stratum="no_explicit")) <= 11
         else "RATIO-CHANGED"),
        ("as it does in two tasks in five: there it is worth", "abstract: 'about half'",
         "about half" if all(0.4 <= x / gap() <= 0.6 for x in (
             redact_delta("rrf_pprpl_issue_path", "co_edited"), leak_share("symbols")))
         else "SHARE-CHANGED"),
        ("and between 0.061 and 0.078 of that 0.140", "conclusion: leakage share, widest arm",
         num3(leak_share("symbols"))),
        ("where one of four predictions, about redaction,", "contributions: external E4 failed",
         "failed" if EXT and EXT["E4"]["pass"] is False else "E4-DID-NOT-FAIL"),
        ("on the oracle-inclusive scale under both keys", "external: E1 rank",
         "third" if EXT and EXT["E1"]["co_edited"]["rank"] == 3
         and EXT["E1"]["symbol"]["rank"] == 3 else "E1-RANK-CHANGED"),
        ("under the widest arm, taking into account", "decomposition, widest arm, leakage",
         num3(leak_share("symbols"))),
        ("under the widest arm, taking into account", "decomposition, widest arm, residual",
         num3(gap() - leak_share("symbols"))),
        ("under the widest arm, taking into account", "decomposition, symbol key, widest arm",
         num3(leak_share("symbols", "symbol"))),
        ("after the widest\nredaction against", "path_issue named tasks after widest arm",
         num3(csv("redaction.csv").query("arm == 'symbols' and group == 'names removed' and "
                                        "source == 'co_edited' and method == 'path_issue'")
              .auc_redacted.iloc[0])),
        ("after the widest\nredaction against", "path_issue unnamed tasks after widest arm",
         num3(csv("redaction.csv").query("arm == 'symbols' and group == 'nothing removed' and "
                                        "source == 'co_edited' and method == 'path_issue'")
              .auc_redacted.iloc[0])),
        # ---- the external test set (numbers from its own tree, predictions fixed in advance)
        ("Table~\\ref{tab:external} gives the four outcomes", "external: E1 worst shortfall",
         num3(EXT["E1"]["worst_shortfall"])),
        ("The fourth fails", "external: names arm, symbol",
         num3(EXT["E4"]["named"][1]["estimate"])),
        ("The fourth fails", "external: names arm, co_edited",
         num3(EXT["E4"]["named"][0]["estimate"])),
        ("The fourth fails", "external: named matched PRs",
         str(EXT["E4"]["named_matched_prs"])),
        ("The fourth fails", "external: paths arm, co_edited",
         num3(EXT["descriptive"]["redaction_arms_named_matched"]["co_edited"]["_rdp"])),
        ("The fourth fails", "external: symbols arm, co_edited",
         num3(EXT["descriptive"]["redaction_arms_named_matched"]["co_edited"]["_rds"])),
        ("The share of issues naming a key\nfile as code", "external: explicit naming rate",
         pct(EXT["descriptive"]["explicit_rate"])),
        ("Of the 140 pull requests, 139 yield", "external: PRs with a key",
         str(EXT["descriptive"]["n_prs"])),
        ("Of the 140 pull requests, 139 yield", "external: matched PRs",
         str(EXT["descriptive"]["n_prs_matched"])),
        ("query-independent prior degrades fastest", "random, largest quartile, co_edited",
         num3(auc("by_size.csv", "co_edited", "random", size_q="Q4"))),
    ]
    F = "rrf_pprpl_issue_path"
    C += [
        # the cost rules (metric.py)
        ("Under the skip rule the recommendation stands", "skip: fusion shortfall, co_edited",
         num3(metric_auc("lines, skip", "co_edited", F)["short"])),
        ("Under the skip rule the recommendation stands", "skip: shortfall, full corpus",
         num3(metric_auc("lines, skip", "co_edited", F, "all")["short"])),
        ("Section~\\ref{sec:fusion} separates by", "skip: length-aware fusion pair, co",
         "%+.3f" % metric_delta("lines, skip", "co_edited", F, "rrf_ppr_issue_path")),
        ("Section~\\ref{sec:fusion} separates by", "skip: length-aware fusion pair, sym",
         "%+.3f" % metric_delta("lines, skip", "symbol", F, "rrf_ppr_issue_path")),
        ("no longer helps at all", "skip: ppr_und_pl - ppr_und, co_edited",
         "%.3f" % metric_delta("lines, skip", "co_edited", "ppr_und_pl", "ppr_und")),
        ("Under the per-file rule length-awareness", "files: fusion rank, co_edited",
         str(metric_auc("files", "co_edited", F)["rank"])),
        ("Under the per-file rule length-awareness", "files: fusion rank, symbol",
         str(metric_auc("files", "symbol", F)["rank"])),
        ("Under the per-file rule length-awareness", "files: shortfall, co_edited",
         num3(metric_auc("files", "co_edited", F)["short"])),
        ("Under the per-file rule length-awareness", "files: shortfall, symbol",
         num3(metric_auc("files", "symbol", F)["short"])),
        # ContextBench (contextbench_eval.py)
        ("Of the resulting tasks, 215 from", "cb: PRs with gold key",
         str(CB["descriptive"]["n_prs_gold"])),
        ("Of the resulting tasks, 215 from", "cb: tasks with gold key",
         str(CB["descriptive"]["n_tasks_gold"])),
        ("A gold key has a median of", "cb: gold files also co-edited",
         "%d" % round(100 * CB["descriptive"]["overlap"]["co_edited"]["share_of_gold_in_other"])),
        ("A gold key has a median of", "cb: gold files also symbol",
         "%d" % round(100 * CB["descriptive"]["overlap"]["symbol"]["share_of_gold_in_other"])),
        ("All four predictions hold (Table", "cb: G1 shortfall", num3(CB["G1"]["shortfall"])),
        ("All four predictions hold (Table", "cb: G2 smallest margin",
         num3(min(t["estimate"] for t in CB["G2"]["tests"]))),
        ("All four predictions hold (Table", "cb: G2 largest margin",
         num3(max(t["estimate"] for t in CB["G2"]["tests"]))),
        ("All four predictions hold (Table", "cb: G3 estimate", num3(CB["G3"]["estimate"])),
        ("All four predictions hold (Table", "cb: G4 tau symbol", "%.2f" % CB["G4"]["symbol"]["tau"]),
        ("All four predictions hold (Table", "cb: G4 tau co_edited",
         "%.2f" % CB["G4"]["co_edited"]["tau"]),
        ("reads but does not edit} --- the context", "cb: read-only PRs",
         str(CB["exploratory_readonly"]["n_prs"])),
        ("the fusion leads: it beats the issue-only", "cb: read-only fusion - path_issue",
         num3(next(t for t in CB["exploratory_readonly"]["tests"]
                   if t["a"] == F and t["b"] == "path_issue")["estimate"])),
        ("the fusion leads: it beats the issue-only", "cb: read-only fusion - bm25_issue",
         num3(next(t for t in CB["exploratory_readonly"]["tests"]
                   if t["a"] == F and t["b"] == "bm25_issue")["estimate"])),
        ("Three checks added in response to review", "cb: fusion shortfall (discussion)",
         num3(CB["G1"]["shortfall"])),
        ("Three checks added in response to review", "seedless: guess correct",
         "%d" % round(100 * SL["guess_correct"])),
        # without a free seed (seedless.py)
        ("The guess is right in", "seedless: guess correct", "%d" % round(100 * SL["guess_correct"])),
        ("The guess is right in", "seedless: correct when named",
         "%d" % round(100 * SL["guess_correct_named"])),
        ("The guess is right in", "seedless: correct when not named",
         "%d" % round(100 * SL["guess_correct_not_named"])),
        ("The guess is right in", "seedless: PRs named", str(SL["n_named"])),
        ("The guess is right in", "seedless: PRs not named", str(SL["n_not_named"])),
        ("walking from the guess and fusing is the best non-oracle ordering",
         "seedless: dense fusion, edited", num3(sl_auc("rrf_pprpl_dense_path", "edited"))),
        ("walking from the guess and fusing is the best non-oracle ordering",
         "seedless: dense fusion, symbol", num3(sl_auc("rrf_pprpl_dense_path", "symbol"))),
        ("On the symbol key it adds", "seedless: dense fusion - dense, symbol",
         num3(sl_delta("dense_issue", "symbol", a="rrf_pprpl_dense_path"))),
        ("On the symbol key it adds", "seedless: wrong guess same top",
         "%d" % round(100 * SL["wrong_guess_same_top"])),
        ("On the symbol key it adds", "seedless: wrong guess same dir",
         "%d" % round(100 * SL["wrong_guess_same_dir"])),
        ("On the edited files it adds nothing measurable", "seedless: dense fusion - dense, edited",
         "%+.3f" % sl_delta("dense_issue", "edited", a="rrf_pprpl_dense_path")),
        ("It helps where the issue names", "seedless: named, edited",
         "%+.3f" % sl_delta("dense_issue", "edited", "named", a="rrf_pprpl_dense_path")),
        ("It helps where the issue names", "seedless: not named, edited",
         "%+.3f" % sl_delta("dense_issue", "edited", "not named", a="rrf_pprpl_dense_path")),
        ("The BM25 fusion of the main study fares", "seedless: BM25 fusion vs dense, not named",
         num3(-sl_delta("dense_issue", "edited", "not named"))),
    ]
    if (OUT / "dense_tests.csv").exists():
        W = "issue worth, dense fusion"
        dgap = dn(W, "co_edited", "explicit") - dn(W, "co_edited", "no_explicit")
        wide = (dn("names cost (_rds), rrf_pprpl_dense_path", "co_edited", "explicit")
                - dn("names cost (_rds), rrf_pprpl_dense_path", "co_edited", "no_explicit"))
        C += [
            ("The dense retriever is the better issue reader", "dense vs bm25, co",
             num3(dn("dense_issue vs bm25_issue", "co_edited"))),
            ("The dense retriever is the better issue reader", "dense vs bm25, sym",
             num3(dn("dense_issue vs bm25_issue", "symbol"))),
            ("The dense retriever is the better issue reader", "dense vs path, co",
             num3(dn("dense_issue vs path_issue", "co_edited"))),
            ("The dense retriever is the better issue reader", "dense vs path, sym",
             num3(dn("dense_issue vs path_issue", "symbol"))),
            ("Put in place of BM25 over contents", "dense in place, co",
             num3(dn("rrf_pprpl_dense_path vs rrf_pprpl_issue_path", "co_edited"))),
            ("Put in place of BM25 over contents", "dense as fourth list, co",
             num3(dn("rrf_pprpl_issue_path_dense vs rrf_pprpl_issue_path", "co_edited"))),
            ("Put in place of BM25 over contents", "dense as fourth list, sym",
             num3(dn("rrf_pprpl_issue_path_dense vs rrf_pprpl_issue_path", "symbol"))),
            ("On issues that\nname no key file the dense fusion gains", "dense worth, not named, co",
             num3(dn(W, "co_edited", "no_explicit"))),
            ("On issues that\nname no key file the dense fusion gains", "dense worth, not named, sym",
             num3(dn(W, "symbol", "no_explicit"))),
            ("But it is a fifth of what", "dense worth, named, co",
             num3(dn(W, "co_edited", "explicit"))),
            ("The\nnames arm costs the dense fusion", "dense names arm",
             num3(dn("names cost (_rd), rrf_pprpl_dense_path", "co_edited", "explicit"))),
            ("The\nnames arm costs the dense fusion", "dense widest arm",
             num3(dn("names cost (_rds), rrf_pprpl_dense_path", "co_edited", "explicit"))),
            ("The\nnames arm costs the dense fusion", "dense widest arm, not named",
             num3(dn("names cost (_rds), rrf_pprpl_dense_path", "co_edited", "no_explicit"))),
            ("The\nnames arm costs the dense fusion", "dense stratum gap", num3(dgap)),
            ("The\nnames arm costs the dense fusion", "dense leakage share low",
             "%d" % round(100 * dn("names cost (_rd), rrf_pprpl_dense_path", "co_edited",
                                   "explicit") / dgap)),
            ("The\nnames arm costs the dense fusion", "dense leakage share high",
             "%d" % round(100 * wide / dgap)),
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
