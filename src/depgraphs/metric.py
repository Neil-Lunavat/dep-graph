"""How much of the ranking is the cost rule? The same orderings under three budgets.

The frozen metric charges whole files by lines and stops at the first file that would
overflow the budget. Under that rule, preferring short files is close to a knapsack heuristic
for the metric itself, and a long file placed early is punished twice. A review asked whether
"length-awareness is what separates the fusions" is a property of the signals or of the
rule. study2 scores every ordering under two more rules:

  lines, skip   a file that does not fit is skipped and reading continues (greedy fill)
  files         one unit per file whatever its length, budgets 1..128 files

and this module reports the rankings and the length-aware-versus-unscaled pairs under all
three, on the matched population and with the repository as the unit, Holm within each rule.

Writes results/study2/metric_auc.csv, results/study2/metric_pairs.csv
"""
from __future__ import annotations

import pandas as pd

from depgraphs.analysis2 import auc_table, holm, pairwise, shared_prs
from depgraphs.study2 import OUT

RULES = {"auc": "lines, stop", "auc_skip": "lines, skip", "auc_files": "files"}
# each pair differs only in dividing the walk's (or BM25's) score by file length
PAIRS = [("ppr_und_pl", "ppr_und"), ("ppr_out_pl", "ppr_out"), ("ppr_in_pl", "ppr_in"),
         ("bm25_issue_pl", "bm25_issue"), ("rrf_pprpl_issue_path", "rrf_ppr_issue_path")]
HEAD = ["rrf_pprpl_issue_path", "rrf_hops_path", "rrf_hops_issue_path", "rrf_ppr_issue_path",
        "hops_lines", "ppr_und_pl", "ppr_und", "ppr_out_pl", "path_issue", "bm25_issue"]


def main():
    rows = pd.read_parquet(OUT / "rows.parquet")
    shared = shared_prs(rows)
    tabs, pairs = [], []
    for col, rule in RULES.items():
        r = rows.assign(auc=rows[col])
        for pop, prs in (("shared", shared), ("all", None)):
            t = auc_table(r, ("co_edited", "symbol"), prs=prs, ci=False)
            t = t[t["rank"].notna()].assign(rule=rule, population=pop)
            tabs.append(t)
        fam = []
        for src in ("co_edited", "symbol"):
            for a, b in PAIRS:
                fam.append(pairwise(r, src, [a, b], unit="repo", population=shared)
                           .assign(rule=rule))
        fam = pd.concat(fam, ignore_index=True)
        fam["p_holm"] = holm(fam["p"].tolist())
        pairs.append(fam)
    tab = pd.concat(tabs, ignore_index=True)
    tab.to_csv(OUT / "metric_auc.csv", index=False)
    pr = pd.concat(pairs, ignore_index=True)
    pr.to_csv(OUT / "metric_pairs.csv", index=False)
    s = tab[tab.population == "shared"].pivot_table(
        index="method", columns=["source", "rule"], values="rank")
    print(s.loc[[m for m in HEAD if m in s.index]].astype(int).to_string())
    print(pr[["rule", "source", "a", "b", "delta", "p_holm"]].round(4).to_string(index=False))


if __name__ == "__main__":
    main()
