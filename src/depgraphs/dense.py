"""Does a dense retriever get more out of the issue than BM25 does?

Every issue-aware ordering in study2 is BM25, over identifier bags or over paths, so "what
the issue is worth" there means "what BM25 over the issue's tokens is worth". A code
embedding model might extract more from the prose that remains once the file names are gone.
study2 scores the D23 embedding model (embed.py) as a retriever on its own, fused with the
length-aware walk in place of BM25 over contents or beside it, with an issue-free twin, and
under the three redaction arms. The dense orderings are scored but not ranked, so none of the
paper's other ranks or corrected p-values move; they are tested here, in two families of
their own, Holm-corrected within each, with the repository as the unit on the matched
population as everywhere else.

  head-to-head   dense against BM25, alone and in the fusion
  decomposition  what the issue is worth to the dense fusion, and what the names are worth,
                 on the issues that name a key file and on those that do not

Writes results/study2/dense_auc.csv, results/study2/dense_tests.csv
"""
from __future__ import annotations

import pandas as pd

from depgraphs.analysis2 import auc_table, holm, leak_strata, pairwise, shared_prs
from depgraphs.study2 import DENSE, OUT, SCORED_ONLY

SHOW = ["rrf_pprpl_issue_path", "rrf_pprpl_issue_path_dense", "rrf_pprpl_dense_path",
        "rrf_pprpl_dense", "rrf_pprpl_seeddense_path", "rrf_pprpl_seedpath", "path_issue",
        "bm25_issue", "dense_issue", "dense_seed", "bm25_seed", "ppr_und_pl"]

HEAD = [("dense_issue", "bm25_issue"), ("dense_issue", "path_issue"),
        ("rrf_pprpl_dense_path", "rrf_pprpl_issue_path"),
        ("rrf_pprpl_issue_path_dense", "rrf_pprpl_issue_path")]

# (a, b, what a - b measures); within each leakage stratum
DECOMP = [("rrf_pprpl_dense_path", "rrf_pprpl_seeddense_path", "issue worth, dense fusion"),
          ("rrf_pprpl_issue_path", "rrf_pprpl_seedpath", "issue worth, BM25 fusion"),
          ("dense_issue", "dense_seed", "issue worth, dense alone"),
          ("bm25_issue", "bm25_seed", "issue worth, BM25 alone"),
          ("rrf_pprpl_dense_path", "rrf_pprpl_issue_path", "dense over BM25 fusion")]
DECOMP += [(m, m + sfx, "names cost (%s), %s" % (sfx, m))
           for sfx in ("_rd", "_rdp", "_rds")
           for m in ("rrf_pprpl_dense_path", "dense_issue", "rrf_pprpl_issue_path")]
DECOMP += [("rrf_pprpl_dense_path" + sfx, "rrf_pprpl_issue_path" + sfx,
            "dense over BM25 fusion after redaction (%s)" % sfx)
           for sfx in ("_rd", "_rdp", "_rds")]


def rank_if_ranked(t: pd.DataFrame) -> pd.DataFrame:
    """The rank each dense ordering would take if inserted, alone, into the paper's
    ranking (oracle included), without displacing anything else."""
    out = []
    for src, g in t.groupby("source"):
        ranked = g[~g.method.isin(SCORED_ONLY)]
        for r in g.itertuples():
            rk = (r.rank if r.method not in SCORED_ONLY
                  else 1 + int((ranked.auc > r.auc).sum()))
            out.append(rk)
    t = t.copy()
    t["rank_if_ranked"] = out
    return t


def main():
    rows = pd.read_parquet(OUT / "rows.parquet")
    if "dense_issue" not in set(rows.method):
        raise SystemExit("no dense orderings in rows.parquet; run embed.py, then study2")
    shared = shared_prs(rows)
    tabs = []
    for pop, prs in (("shared", shared), ("all", None)):
        t = auc_table(rows, ("co_edited", "symbol"), prs=prs, ci=pop == "shared")
        t = rank_if_ranked(t.sort_values(["source", "auc"], ascending=[True, False]))
        tabs.append(t[t.method.isin(SHOW + list(DENSE))].assign(population=pop))
    auc = pd.concat(tabs, ignore_index=True)
    auc.to_csv(OUT / "dense_auc.csv", index=False)

    tests = []
    head = []
    for src in ("co_edited", "symbol"):
        for a, b in HEAD:
            head.append(pairwise(rows, src, [a, b], unit="repo", population=shared)
                        .assign(family="head-to-head", what="%s vs %s" % (a, b)))
    head = pd.concat(head, ignore_index=True)
    head["p_holm"] = holm(head["p"].tolist())
    tests.append(head)

    st = leak_strata(rows)
    dec = []
    for stratum in ("explicit", "no_explicit", "all"):
        sub = rows[rows.task_id.isin(st[stratum])]
        keep = shared_prs(sub)
        for src in ("co_edited", "symbol"):
            for a, b, what in DECOMP:
                dec.append(pairwise(rows, src, [a, b], unit="repo", population=keep,
                                    tasks=st[stratum], stratum=stratum)
                           .assign(family="decomposition", what=what))
    dec = pd.concat(dec, ignore_index=True)
    dec["p_holm"] = holm(dec["p"].tolist())
    tests.append(dec)
    tests = pd.concat(tests, ignore_index=True)
    tests.to_csv(OUT / "dense_tests.csv", index=False)

    pd.set_option("display.width", 200)
    print(auc[auc.population == "shared"][["source", "method", "auc", "rank_if_ranked"]]
          .round(3).to_string(index=False))
    print(tests[["family", "stratum", "source", "what", "n_pr", "delta", "p_holm"]]
          .round(4).to_string(index=False))


if __name__ == "__main__":
    main()
