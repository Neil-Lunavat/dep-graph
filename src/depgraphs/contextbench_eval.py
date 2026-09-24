"""Test the predictions of paper/contextbench_prereg.md against ContextBench's human key.

Each function is one prediction, implemented as that file words it; the criteria were
committed before any ContextBench result existed. Run with DEPGRAPHS_ROOT pointing at the
contextbench tree, after study2 has run there.

Writes <contextbench>/results/study2/predictions.json and per_source.csv.

Usage:  DEPGRAPHS_ROOT=contextbench python -m depgraphs.contextbench_eval
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from scipy import stats

from depgraphs.analysis2 import auc_table, holm, pr_level
from depgraphs.external_eval import F, mixed
from depgraphs.lexfeat import ROOT
from depgraphs.study2 import OUT, SCORED_ONLY


def e_g1(rows):
    t = auc_table(rows, ("gold",), ci=False)
    g = t[t["rank"].notna()].set_index("method")
    best = g.drop("oracle").auc.max()
    # the oracle holds rank 1, so "among the three best non-oracle" is rank <= 4
    out = {"rank": int(g.loc[F, "rank"]), "auc": float(g.loc[F, "auc"]),
           "best_non_oracle": g.drop("oracle").auc.idxmax(),
           "shortfall": float(best - g.loc[F, "auc"]),
           "top5": g.drop("oracle").auc.sort_values(ascending=False).head(5).round(4).to_dict()}
    out["pass"] = out["rank"] <= 4 and out["shortfall"] <= 0.030
    return out


def e_g2(rows, repo):
    mat = pr_level(rows, "gold")
    tests = [{"b": b, **mixed(mat[F] - mat[b], repo)}
             for b in ("hops_lines", "ppr_und_pl", "ppr_out_pl", "path_issue")]
    for t, p in zip(tests, holm([t["p"] for t in tests])):
        t["p_holm"] = p
    return {"pass": not [t for t in tests if t["estimate"] < 0 and t["p_holm"] < 0.05],
            "tests": tests}


def e_g3(rows, repo):
    mat = pr_level(rows, "gold")
    r = mixed(mat["ppr_out_pl"] - mat["ppr_in_pl"], repo)
    return {"pass": r["estimate"] > 0 and r["p"] < 0.05, **r}


def e_g4(rows):
    ranked = [m for m in rows.method.unique() if m not in SCORED_ONLY and m != "oracle"]
    out = {}
    for other in ("symbol", "co_edited"):
        both = (set(rows[rows.source == "gold"].task_id)
                & set(rows[rows.source == other].task_id))
        sub = rows[rows.task_id.isin(both) & rows.method.isin(ranked)]
        a = pr_level(sub, "gold").mean()
        b = pr_level(sub, other).mean()
        tau, p = stats.kendalltau(a[ranked], b[ranked])
        out[other] = {"tau": float(tau), "p": float(p), "n_tasks": len(both),
                      "n_prs": int(sub.instance_id.nunique()), "n_methods": len(ranked)}
    out["pass"] = all(v["tau"] >= 0.5 for v in out.values())
    return out


def descriptive(rows):
    tasks = [json.loads(l) for l in open(ROOT / "data" / "tasks.jsonl", encoding="utf-8")]
    scored = set(rows.task_id)
    gk = [t for t in tasks if t["task_id"] in scored and t["keys"].get("gold")]
    size = [len(t["keys"]["gold"]) for t in gk]
    ov = {}
    for other in ("co_edited", "symbol"):
        inter = [len(set(t["keys"]["gold"]) & set(t["keys"].get(other, []))) for t in gk]
        ov[other] = {"share_of_gold_in_other": float(sum(inter) / sum(size)),
                     "tasks_with_empty_other": int(sum(not t["keys"].get(other)
                                                       for t in gk))}
    single = {t["instance_id"] for t in gk if t["file_group"] == "single"}
    rd = json.loads((ROOT / "data" / "issue_bags_redacted.json").read_text())
    named = {t for t, v in rd.items() if v["removed"] > 0}
    arms = {}
    sub = rows[rows.task_id.isin(named)]
    mat = pr_level(sub, "gold")
    for sfx in ("_rd", "_rdp", "_rds"):
        if F + sfx in mat:
            arms[sfx] = float((mat[F] - mat[F + sfx]).mean())
    return {"n_tasks_gold": len(gk), "n_prs_gold": len({t["instance_id"] for t in gk}),
            "n_repos_gold": len({t["repo_key"] for t in gk}),
            "gold_size_median": float(np.median(size)), "gold_size_mean": float(np.mean(size)),
            "overlap": ov, "single_file_prs_with_gold": len(single),
            "names_arm_named_prs": int(mat.shape[0]), "redaction_arms_named": arms}


def exploratory(rows, repo):
    """Not pre-registered (POSTHOC.md). On the gold files the fix reads but does not edit,
    does a structural walk find them better than the issue does? One Holm family."""
    mat = pr_level(rows, "gold_readonly")
    pairs = [(a, b) for a in ("hops_lines", "ppr_und_pl", "ppr_out_pl")
             for b in ("path_issue", "bm25_issue")]
    pairs += [(F, b) for b in ("hops_lines", "ppr_und_pl", "ppr_out_pl", "path_issue",
                               "bm25_issue")]
    tests = [{"a": a, "b": b, **mixed(mat[a] - mat[b], repo)} for a, b in pairs]
    for t, p in zip(tests, holm([t["p"] for t in tests])):
        t["p_holm"] = p
    t = auc_table(rows, ("gold_readonly",), ci=False)
    t = t[t["rank"].notna()].sort_values("rank")
    return {"n_prs": int(mat.dropna(how="all").shape[0]),
            "top": t[["method", "auc", "rank"]].head(12).round(4).to_dict("records"),
            "tests": tests}


def main():
    rows = pd.read_parquet(OUT / "rows.parquet")
    repo = rows.groupby("instance_id")["repo_key"].first()
    res = {"G1": e_g1(rows), "G2": e_g2(rows, repo), "G3": e_g3(rows, repo),
           "G4": e_g4(rows), "descriptive": descriptive(rows),
           "exploratory_readonly": exploratory(rows, repo)}
    (OUT / "predictions.json").write_text(json.dumps(res, indent=1, default=float))
    for k in ("G1", "G2", "G3", "G4"):
        print(k, "PASS" if res[k]["pass"] else "FAIL")
    print(json.dumps(res, indent=1, default=float))
    auc_table(rows, ("gold", "gold_readonly", "co_edited", "symbol"), ci=False).to_csv(
        OUT / "per_source.csv", index=False)


if __name__ == "__main__":
    np.seterr(all="ignore")
    main()
