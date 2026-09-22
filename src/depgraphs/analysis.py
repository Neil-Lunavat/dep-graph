"""Step 8: statistics exactly as fixed in D14 / paper/metrics.md.

Reads results/scores/<condition>.parquet, results/table1.csv, data/tasks.jsonl.
Writes results/analysis/*.csv and results/analysis/findings.json (every number the report
uses, each traceable to a CSV here).
"""
from __future__ import annotations

import json
import math
from itertools import combinations

import numpy as np
import pandas as pd
from scipy import stats

from depgraphs.datasets import ROOT

OUT = ROOT / "results" / "analysis"
REFS = {"random", "same_dir", "whole_repo", "seed_alone", "oracle"}
EXCLUDED = {"embedding"}          # not computed in time (D23 note); reported as pending
SEED = 20260922


def a12(x, y) -> float:
    """Vargha–Delaney A12: P(X > Y) + 0.5 P(X = Y), paired values."""
    x, y = np.asarray(x), np.asarray(y)
    gt = (x[:, None] > y[None, :]).mean()
    eq = (x[:, None] == y[None, :]).mean()
    return float(gt + 0.5 * eq)


def holm(p: pd.Series) -> pd.Series:
    order = p.sort_values().index
    m = len(p)
    adj, prev = {}, 0.0
    for i, k in enumerate(order):
        v = min(1.0, max(prev, (m - i) * p[k]))
        adj[k] = v
        prev = v
    return pd.Series(adj).reindex(p.index)


def bh(p: pd.Series) -> pd.Series:
    order = p.sort_values().index
    m = len(p)
    adj = {}
    prev = 1.0
    for i, k in reversed(list(enumerate(order, 1))):
        prev = min(prev, p[k] * m / i)
        adj[k] = prev
    return pd.Series(adj).reindex(p.index)


def pr_level(s: pd.DataFrame, source: str, metric="auc_lines", group=None) -> pd.DataFrame:
    d = s[(s.source == source) & (s.method != "*") & ~s.method.isin(EXCLUDED)]
    if group:
        d = d[d.file_group == group]
    return d.groupby(["repo_key", "instance_id", "method"])[metric].mean().unstack("method")


def boot_ci(pr: pd.DataFrame, col: str, n=2000) -> tuple[float, float]:
    rng = np.random.default_rng(SEED)
    per_repo = pr[col].groupby(level=0).agg(["sum", "count"])
    repos = per_repo.index.values
    vals = []
    for _ in range(n):
        pick = rng.choice(repos, len(repos), replace=True)
        sub = per_repo.loc[pick]
        vals.append(sub["sum"].sum() / sub["count"].sum())
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def rq1(s: pd.DataFrame, source: str, group=None) -> pd.DataFrame:
    pr = pr_level(s, source, group=group).dropna(axis=1, how="all")
    rows = []
    for m in pr.columns:
        x, r = pr[m], pr["random"]
        ok = x.notna() & r.notna()
        diff = (x[ok] - r[ok])
        p = stats.wilcoxon(x[ok], r[ok]).pvalue if (diff != 0).any() else 1.0
        lo, hi = boot_ci(pr[[m]].dropna(), m)
        rows.append({"method": m, "is_reference": m in REFS, "n_prs": int(ok.sum()),
                     "n_repos": int(pr[m].dropna().index.get_level_values(0).nunique()),
                     "mean_auc": float(x.mean()), "ci_lo": lo, "ci_hi": hi,
                     "median_auc": float(x.median()),
                     "diff_vs_random": float(diff.mean()),
                     "a12_vs_random": a12(x[ok].values, r[ok].values) if ok.sum() < 4000 else float("nan"),
                     "p_vs_random": float(p)})
    out = pd.DataFrame(rows).set_index("method")
    mask = ~out.index.isin(["random"])
    out.loc[mask, "p_holm_vs_random"] = holm(out.loc[mask, "p_vs_random"])
    return out.sort_values("mean_auc", ascending=False)


def friedman(s: pd.DataFrame, source: str) -> dict:
    pr = pr_level(s, source)
    methods = [m for m in pr.columns if m not in REFS or m == "random"]
    rep = pr[methods].groupby(level=0).mean().dropna()
    stat, p = stats.friedmanchisquare(*[rep[m].values for m in methods])
    ranks = rep.rank(axis=1, ascending=False).mean().sort_values()
    k, n = len(methods), len(rep)
    q = stats.studentized_range.ppf(0.95, k, np.inf) / math.sqrt(2)
    cd = q * math.sqrt(k * (k + 1) / (6 * n))
    return {"chi2": float(stat), "p": float(p), "n_repos": n, "k_methods": k,
            "nemenyi_cd": float(cd), "avg_rank": ranks.round(3).to_dict()}


def pairwise(s: pd.DataFrame, source: str, top: list[str]) -> pd.DataFrame:
    pr = pr_level(s, source)
    rows = []
    for a, b in combinations(top, 2):
        ok = pr[a].notna() & pr[b].notna()
        d = pr[a][ok] - pr[b][ok]
        p = stats.wilcoxon(pr[a][ok], pr[b][ok]).pvalue if (d != 0).any() else 1.0
        rows.append({"a": a, "b": b, "mean_diff": float(d.mean()),
                     "a12": a12(pr[a][ok].values, pr[b][ok].values), "p": float(p),
                     "a_wins_prs": int((d > 0).sum()), "b_wins_prs": int((d < 0).sum()),
                     "ties": int((d == 0).sum())})
    out = pd.DataFrame(rows)
    out["p_holm"] = holm(out.p).values
    return out


def rq2(s: pd.DataFrame, source: str, table1: pd.DataFrame) -> pd.DataFrame:
    pr = pr_level(s, source)
    rep = pr.groupby(level=0).mean()
    methods = [m for m in rep.columns if m not in REFS]
    gain = rep[methods].sub(rep["random"], axis=0)
    t1 = table1.set_index("repo_key")
    props = [c for c in t1.columns if c != "sha" and pd.api.types.is_numeric_dtype(t1[c])]
    rows = []
    for m in methods:
        for pcol in props:
            x = t1.loc[gain.index, pcol]
            y = gain[m]
            ok = x.notna() & y.notna()
            if ok.sum() < 5 or x[ok].nunique() < 3:
                continue
            rho, p = stats.spearmanr(x[ok], y[ok])
            rows.append({"method": m, "property": pcol, "rho": float(rho), "p": float(p),
                         "n_repos": int(ok.sum())})
    out = pd.DataFrame(rows)
    out["p_bh"] = bh(out.p).values
    return out.sort_values("p")


def winners_per_repo(s: pd.DataFrame, source: str) -> pd.DataFrame:
    pr = pr_level(s, source)
    rep = pr.groupby(level=0).mean()
    methods = [m for m in rep.columns if m not in REFS]
    best = rep[methods].idxmax(axis=1)
    return pd.DataFrame({"best_method": best, "best_auc": rep[methods].max(axis=1),
                         "random_auc": rep["random"]})


def rq3(tasks: list[dict]) -> pd.DataFrame:
    rows = []
    for t in tasks:
        for src, files in t["keys"].items():
            for f in files:
                d = t["distances"].get(f, {})
                rows.append({"task_id": t["task_id"], "source": src, "file_group": t["file_group"],
                             "fwd": d.get("forward"), "rev": d.get("reverse"),
                             "und": d.get("undirected")})
    return pd.DataFrame(rows)


def key_agreement(tasks: list[dict]) -> dict:
    rows = []
    for t in tasks:
        k = t["keys"]
        if "execution_B" not in k:
            continue
        static = set(k.get("co_edited", [])) | set(k.get("symbol", []))
        ex = set(k["execution_B"])
        rows.append({"static": len(static), "exec": len(ex), "both": len(static & ex),
                     "jaccard": len(static & ex) / len(static | ex) if static | ex else float("nan"),
                     "exec_A": len(k.get("execution_A", [])), "exec_C": len(k.get("execution_C", []))})
    d = pd.DataFrame(rows)
    if d.empty:
        return {}
    return {"tasks": len(d), "mean_jaccard": float(d.jaccard.mean()),
            "share_static_found_by_exec": float(d.both.sum() / max(d.static.sum(), 1)),
            "share_exec_found_by_static": float(d.both.sum() / max(d.exec.sum(), 1)),
            "mean_size_static": float(d.static.mean()), "mean_size_exec_B": float(d.exec.mean()),
            "mean_size_exec_A": float(d.exec_A.mean()), "mean_size_exec_C": float(d.exec_C.mean())}


def curves(s_path, source="union") -> pd.DataFrame:
    """Mean coverage at each lines budget, per method (PR-weighted), for the figure."""
    return pd.DataFrame()   # filled by curves.py from the raw lists (kept separate)


def main(condition="true"):
    OUT.mkdir(parents=True, exist_ok=True)
    s = pd.read_parquet(ROOT / "results" / "scores" / f"{condition}.parquet")
    table1 = pd.read_csv(ROOT / "results" / "table1.csv")
    tasks = [json.loads(l) for l in open(ROOT / "data" / "tasks.jsonl", encoding="utf-8")]
    findings = {"condition": condition}
    for src in ["union", "co_edited", "symbol", "execution_B", "execution_C", "execution_A",
                "union_static"]:
        if not (s.source == src).any():
            continue
        r = rq1(s, src)
        r.to_csv(OUT / f"rq1_{src}.csv")
        findings[f"rq1_{src}"] = r.round(4).reset_index().to_dict("records")
    for g in ("single", "multi"):
        r = rq1(s, "union", group=g)
        r.to_csv(OUT / f"rq1_union_{g}.csv")
        findings[f"rq1_union_{g}"] = r.round(4).reset_index().to_dict("records")
    fr = friedman(s, "union")
    findings["friedman_union"] = fr
    top = [m for m in pd.read_csv(OUT / "rq1_union.csv").method if m not in REFS][:8]
    pw = pairwise(s, "union", top)
    pw.to_csv(OUT / "pairwise_union_top8.csv", index=False)
    findings["pairwise_top8"] = pw.round(5).to_dict("records")
    r2 = rq2(s, "union", table1)
    r2.to_csv(OUT / "rq2_spearman_union.csv", index=False)
    findings["rq2"] = {"pairs": len(r2), "sig_bh_005": int((r2.p_bh < 0.05).sum()),
                       "sig_raw_005": int((r2.p < 0.05).sum()),
                       "top": r2.head(15).round(4).to_dict("records")}
    w = winners_per_repo(s, "union")
    w.to_csv(OUT / "winner_per_repo_union.csv")
    findings["winners"] = w.best_method.value_counts().to_dict()
    d = rq3(tasks)
    d.to_csv(OUT / "rq3_distances.csv", index=False)
    rq3s = {}
    for src, g in d.groupby("source"):
        rq3s[src] = {"pairs": len(g),
                     "no_path_und": float(g.und.isna().mean()),
                     "no_path_fwd": float(g.fwd.isna().mean()),
                     "no_path_rev": float(g.rev.isna().mean()),
                     "und_dist_counts": g.und.fillna(-1).astype(int).value_counts().sort_index().to_dict()}
    findings["rq3"] = rq3s
    findings["key_agreement"] = key_agreement(tasks)
    findings["counts"] = {"tasks": len(tasks), "prs": len({t["instance_id"] for t in tasks}),
                          "repos": len({t["repo_key"] for t in tasks}),
                          "scored_rows": int(len(s)),
                          "empty_key_rows": int(s.get("empty_key", pd.Series()).fillna(0).sum())}
    (OUT / "findings.json").write_text(json.dumps(findings, indent=1, default=str))
    print("analysis written")


if __name__ == "__main__":
    import sys
    main(sys.argv[1] if len(sys.argv) > 1 else "true")
