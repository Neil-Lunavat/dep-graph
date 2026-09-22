"""Analysis for the structure-vs-words study.

The unit of analysis is the pull request: task AUCs are averaged within an instance first,
so a PR that touches many files does not count many times. Paired tests are Wilcoxon
signed-rank with Vargha-Delaney A12 and Holm correction within each family of comparisons;
confidence intervals are 2000-resample bootstraps over repositories.

Writes results/study2/*.csv and results/study2/findings.json
"""
from __future__ import annotations

import gzip
import json
from itertools import combinations

import numpy as np
import pandas as pd
from scipy import stats

from depgraphs.lexfeat import ROOT
from depgraphs.study2 import BUDGETS, FUSION, GLOBAL, LEXICAL, METHODS, STRUCTURE, OUT

SEED = 20260923
SOURCES = ["co_edited", "symbol", "union_static"]
FAMILY = ({m: "structure" for m in STRUCTURE} | {m: "global" for m in GLOBAL}
          | {m: "lexical" for m in LEXICAL} | {m: "fusion" for m in FUSION}
          | {"same_dir": "reference", "random": "reference", "oracle": "reference"})


def pr_level(rows: pd.DataFrame, source: str) -> pd.DataFrame:
    """method x instance_id matrix of AUC, averaged over the tasks of a PR."""
    d = rows[rows["source"] == source]
    return d.pivot_table(index="instance_id", columns="method", values="auc", aggfunc="mean")


def a12(x: np.ndarray, y: np.ndarray) -> float:
    """P(x > y) + 0.5 P(x == y), computed from the rank-sum."""
    n, m = len(x), len(y)
    r = stats.rankdata(np.concatenate([x, y]))[:n].sum()
    return (r / n - (n + 1) / 2) / m


def holm(pvals: list[float]) -> list[float]:
    order = np.argsort(pvals)
    adj = np.empty(len(pvals))
    running = 0.0
    for i, idx in enumerate(order):
        running = max(running, (len(pvals) - i) * pvals[idx])
        adj[idx] = min(1.0, running)
    return adj.tolist()


def boot_ci(values: np.ndarray, groups: np.ndarray, n=2000, seed=SEED):
    """Bootstrap the mean by resampling repositories, not tasks."""
    rng = np.random.default_rng(seed)
    uniq = np.unique(groups)
    idx = {g: np.flatnonzero(groups == g) for g in uniq}
    out = []
    for _ in range(n):
        pick = rng.choice(uniq, size=len(uniq), replace=True)
        sel = np.concatenate([idx[g] for g in pick])
        out.append(values[sel].mean())
    return float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))


def table_per_source(rows: pd.DataFrame) -> pd.DataFrame:
    recs = []
    for src in SOURCES:
        mat = pr_level(rows, src)
        repo = (rows[rows["source"] == src].groupby("instance_id")["repo_key"].first()
                .reindex(mat.index))
        for m in mat.columns:
            v = mat[m].to_numpy()
            ok = ~np.isnan(v)
            lo, hi = boot_ci(v[ok], repo.to_numpy()[ok])
            recs.append({"source": src, "method": m, "family": FAMILY.get(m, "?"),
                         "n_pr": int(ok.sum()), "auc": float(v[ok].mean()),
                         "ci_lo": lo, "ci_hi": hi})
    df = pd.DataFrame(recs)
    df["rank"] = df.groupby("source")["auc"].rank(ascending=False, method="min").astype(int)
    return df.sort_values(["source", "rank"])


def pairwise(rows: pd.DataFrame, source: str, methods: list[str]) -> pd.DataFrame:
    mat = pr_level(rows, source)[methods].dropna()
    recs, pvals = [], []
    for a, b in combinations(methods, 2):
        x, y = mat[a].to_numpy(), mat[b].to_numpy()
        try:
            p = stats.wilcoxon(x, y, zero_method="wilcox").pvalue
        except ValueError:
            p = 1.0
        recs.append({"source": source, "a": a, "b": b, "n_pr": len(x),
                     "mean_a": float(x.mean()), "mean_b": float(y.mean()),
                     "delta": float(x.mean() - y.mean()), "a12": a12(x, y), "p": p})
        pvals.append(p)
    df = pd.DataFrame(recs)
    df["p_holm"] = holm(pvals)
    return df


def complementarity(top_path, k=20):
    """How each key file is reachable: by structure only, words only, both, neither."""
    struct = ["ppr_und", "hops_lines"]
    lex = ["bm25_issue", "path_issue"]
    tally = {s: {"struct_only": 0, "lex_only": 0, "both": 0, "neither": 0, "total": 0}
             for s in SOURCES}
    with gzip.open(top_path, "rt", encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            S = set().union(*[rec["lists"].get(m, [])[:k] for m in struct])
            L = set().union(*[rec["lists"].get(m, [])[:k] for m in lex])
            for src in SOURCES:
                for p in rec["keys"].get(src, []):
                    t = tally[src]
                    t["total"] += 1
                    if p in S and p in L:
                        t["both"] += 1
                    elif p in S:
                        t["struct_only"] += 1
                    elif p in L:
                        t["lex_only"] += 1
                    else:
                        t["neither"] += 1
    recs = []
    for src, t in tally.items():
        n = t["total"] or 1
        recs.append({"source": src, "k": k, "n_key_files": t["total"],
                     **{c: t[c] / n for c in ["both", "struct_only", "lex_only", "neither"]}})
    return pd.DataFrame(recs)


def overlap(top_path, k=20):
    """Jaccard between the top-k sets of the structural and lexical families."""
    pairs = [("ppr_und", "bm25_issue"), ("ppr_und", "path_issue"),
             ("ppr_und", "pagerank"), ("bm25_issue", "path_issue"),
             ("ppr_und", "bm25_seed"), ("bm25_issue", "bm25_seed")]
    acc = {p: [] for p in pairs}
    with gzip.open(top_path, "rt", encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            for a, b in pairs:
                A, B = set(rec["lists"].get(a, [])[:k]), set(rec["lists"].get(b, [])[:k])
                if A or B:
                    acc[(a, b)].append(len(A & B) / len(A | B))
    return pd.DataFrame([{"a": a, "b": b, "k": k, "jaccard": float(np.mean(v)),
                          "n": len(v)} for (a, b), v in acc.items()])


def leak_sensitivity(rows: pd.DataFrame, methods: list[str]) -> pd.DataFrame:
    """Re-rank on the tasks whose issue text contains no key file path verbatim.

    Path-matching methods would look good for a trivial reason if issue reports simply
    quoted the paths of the files that had to change, so the comparison is repeated with
    those tasks removed.
    """
    leak = pd.read_csv(OUT / "issue_path_leak.csv")
    clean = set(leak.loc[leak["full"] == 0, "task_id"])
    sub = rows[rows["task_id"].isin(clean)]
    recs = []
    for src in SOURCES:
        mat = pr_level(sub, src)
        for m in methods:
            if m in mat:
                v = mat[m].dropna()
                recs.append({"source": src, "method": m, "n_pr": len(v),
                             "auc_no_leak": float(v.mean())})
    df = pd.DataFrame(recs)
    df["rank_no_leak"] = df.groupby("source")["auc_no_leak"].rank(
        ascending=False, method="min").astype(int)
    return df


def rank_agreement(per_source: pd.DataFrame) -> dict:
    """Spearman correlation between the method rankings induced by two evidence sources.

    Reported twice: over everything scored, and over the contenders only. The references
    (random, same_dir, oracle) sit at the same end of both rankings by construction and
    inflate the agreement, so the contender-only figure is the one that answers the
    question "does it matter which evidence you grade against".
    """
    out = {}
    for label, drop in (("all", {"oracle"}),
                        ("contenders", {"oracle", "random", "same_dir"})):
        piv = per_source[~per_source.method.isin(drop)].pivot(
            index="method", columns="source", values="auc")
        r, p = stats.spearmanr(piv["co_edited"], piv["symbol"])
        out[label] = {"spearman": float(r), "p": float(p), "n_methods": int(len(piv))}
    return out


def lines_table(rows: pd.DataFrame, methods: list[str]) -> pd.DataFrame:
    """Median lines that must be read to reach half, then all, of the key files."""
    recs = []
    for src in SOURCES:
        d = rows[(rows["source"] == src) & (rows["method"].isin(methods))]
        for m, g in d.groupby("method"):
            recs.append({"source": src, "method": m,
                         "lines_half_median": float(g["lines_half"].median()),
                         "lines_all_median": float(g["lines_all"].median()),
                         "n_task": int(len(g))})
    return pd.DataFrame(recs).sort_values(["source", "lines_half_median"])


def main():
    rows = pd.read_parquet(OUT / "rows.parquet")
    curves = pd.read_parquet(OUT / "curves.parquet")

    per_source = table_per_source(rows)
    per_source.to_csv(OUT / "per_source.csv", index=False)

    contenders = ["ppr_und", "ppr_und_pl", "hops_lines", "pagerank", "bm25_issue",
                  "bm25_issue_pl", "path_issue", "bm25_seed", "path_seed",
                  "rrf_ppr_issue", "rrf_ppr_issue_path", "rrf_hops_path",
                  "rrf_hops_issue_path", "rrf_pprpl_issue_path", "same_dir", "random"]
    pw = pd.concat([pairwise(rows, s, contenders) for s in SOURCES])
    pw.to_csv(OUT / "pairwise.csv", index=False)

    cur = (curves.groupby(["source", "method", "budget"])["coverage"].mean()
           .reset_index())
    cur.to_csv(OUT / "curves_mean.csv", index=False)

    comp = pd.concat([complementarity(OUT / "top.jsonl.gz", k) for k in (10, 20, 50)])
    comp.to_csv(OUT / "complementarity.csv", index=False)
    ov = pd.concat([overlap(OUT / "top.jsonl.gz", k) for k in (10, 20, 50)])
    ov.to_csv(OUT / "overlap.csv", index=False)

    # rank reversal across key sources
    piv = per_source.pivot(index="method", columns="source", values="rank")
    piv["worst_case"] = piv[["co_edited", "symbol"]].max(axis=1)
    piv.sort_values("worst_case").to_csv(OUT / "rank_by_source.csv")

    leak = leak_sensitivity(rows, contenders)
    leak.to_csv(OUT / "leak_sensitivity.csv", index=False)

    lines_table(rows, contenders + ["oracle"]).to_csv(OUT / "lines_to_reach.csv",
                                                      index=False)

    findings = {
        "rank_agreement": rank_agreement(per_source),
        "n_tasks": int(rows["task_id"].nunique()),
        "n_prs": int(rows["instance_id"].nunique()),
        "n_repos": int(rows["repo_key"].nunique()),
        "budgets": BUDGETS,
        "per_source_top5": {s: per_source[per_source.source == s]
                            .nsmallest(6, "rank")[["method", "auc", "rank"]]
                            .to_dict("records") for s in SOURCES},
        "rank_reversal": piv.to_dict("index"),
    }
    (OUT / "findings.json").write_text(json.dumps(findings, indent=1))
    print(per_source[per_source.source == "union_static"]
          [["method", "family", "auc", "ci_lo", "ci_hi", "rank"]].to_string(index=False))
    print()
    print(piv.to_string())


if __name__ == "__main__":
    main()
