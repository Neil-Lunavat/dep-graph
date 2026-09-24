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


def redact_delta(method: str, source: str, group: str = "names removed") -> float:
    d = csv("redaction.csv")
    r = d[(d.group == group) & (d.method == method) & (d.source == source)].iloc[0]
    return float(r.delta)


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
        ("it costs the best fusion", "redaction cost, fusion, co_edited",
         num3(redact_delta("rrf_pprpl_issue_path", "co_edited"))),
        ("it costs the best fusion", "redaction cost, fusion, symbol",
         num3(redact_delta("rrf_pprpl_issue_path", "symbol"))),
        ("where the redactor found nothing to remove",
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
        ("lead under both real controls", "ppr_und_pl symbol primary",
         num3(auc("per_source_joint.csv", "symbol", "ppr_und_pl", stratum="no_explicit"))),
        ("lead under both real controls", "hops_lines symbol primary",
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
        ("On the full corpus \m{path\_issue} is", "path_issue rank, full corpus",
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
        ("which differ only in whether the walk's scores are divided by file",
         "length-aware ablation, unscaled worst rank (contributions)",
         str(int(csv("rank_by_source.csv").set_index("method")
                 .loc["rrf_ppr_issue_path", "worst_case"]))),

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
        ("following imports outward beats the same walk run inward by",
         "direction, full corpus",
         num3(delta("ppr_out_pl", "ppr_in_pl", "symbol", population="all"))),
        ("following imports outward beats the same walk run inward by",
         "direction, matched",
         num3(delta("ppr_out_pl", "ppr_in_pl", "symbol"))),
        ("literature is indistinguishable from the outward one",
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
        ("about a third of what the issue adds to it is leakage",
         "issue-aware fusion over its twin, matched, every task",
         num3(delta("rrf_pprpl_issue_path", "rrf_pprpl_seedpath", "co_edited"))),
        ("about a third of what the issue adds to it is leakage",
         "redaction cost, fusion, co_edited, every task",
         num3(redact_delta("rrf_pprpl_issue_path", "co_edited", "all tasks"))),
        ("query-independent prior degrades fastest", "random, largest quartile, co_edited",
         num3(auc("by_size.csv", "co_edited", "random", size_q="Q4"))),
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
