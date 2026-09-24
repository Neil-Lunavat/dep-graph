"""Test the predictions of paper/external_prereg.md on the external repositories.

Each function below is one prediction, implemented as that file words it; the criteria were
committed before any external result existed, and nothing here may change them. Run with
DEPGRAPHS_ROOT pointing at the external tree, after study2 and leakage have run there.

Writes <external>/results/study2/predictions.json and prints one line per prediction.

Usage:  DEPGRAPHS_ROOT=external python -m depgraphs.external_eval
"""
from __future__ import annotations

import json
import warnings

import numpy as np
import pandas as pd

from depgraphs.analysis2 import auc_table, holm, leak_strata, pr_level, shared_prs
from depgraphs.study2 import OUT

F = "rrf_pprpl_issue_path"


def mixed(d: pd.Series, repo: pd.Series) -> dict:
    """Random-intercept model of one paired difference per pull request."""
    import statsmodels.formula.api as smf

    df = d.dropna().rename("d").to_frame()
    df["repo"] = repo.reindex(df.index).to_numpy()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fit = smf.mixedlm("d ~ 1", df, groups=df["repo"]).fit(reml=True)
    lo, hi = fit.conf_int().loc["Intercept"]
    return {"estimate": float(fit.params["Intercept"]), "ci": [float(lo), float(hi)],
            "p": float(fit.pvalues["Intercept"]), "n_pr": int(len(df)),
            "n_repo": int(df["repo"].nunique())}


def e1(rows, shared):
    t = auc_table(rows, ("co_edited", "symbol"), prs=shared, ci=False)
    t = t[t["rank"].notna()]
    out = {}
    for src in ("co_edited", "symbol"):
        g = t[t.source == src].set_index("method")
        best = g.drop("oracle").auc.max()
        # the oracle holds rank 1, so "among the three best non-oracle" is rank <= 4
        out[src] = {"rank": int(g.loc[F, "rank"]), "auc": float(g.loc[F, "auc"]),
                    "best_non_oracle": g.drop("oracle").auc.idxmax(),
                    "shortfall": float(best - g.loc[F, "auc"])}
    shortfall = max(v["shortfall"] for v in out.values())
    ok = all(v["rank"] <= 4 for v in out.values()) and shortfall <= 0.030
    return {"pass": ok, "worst_shortfall": shortfall, **out}


def e2(rows, shared, repo):
    tests = []
    for src in ("co_edited", "symbol"):
        mat = pr_level(rows, src)
        mat = mat.loc[mat.index.intersection(shared)]
        for b in ("hops_lines", "ppr_und_pl", "ppr_out_pl", "path_issue"):
            tests.append({"source": src, "b": b, **mixed(mat[F] - mat[b], repo)})
    for t, p in zip(tests, holm([t["p"] for t in tests])):
        t["p_holm"] = p
    bad = [t for t in tests if t["estimate"] < 0 and t["p_holm"] < 0.05]
    return {"pass": not bad, "tests": tests}


def e3(rows, repo):
    mat = pr_level(rows, "symbol")
    r = mixed(mat["ppr_out_pl"] - mat["ppr_in_pl"], repo)
    return {"pass": r["estimate"] > 0 and r["p"] < 0.05, **r}


def e4(rows, repo):
    st = leak_strata(rows)
    out = {}
    named = rows[rows.task_id.isin(st["explicit"])]
    keep = shared_prs(named)
    if len(keep) < 20:
        return {"pass": None, "testable": False, "named_matched_prs": int(len(keep))}
    tests = []
    for src in ("co_edited", "symbol"):
        mat = pr_level(named, src).loc[lambda m: m.index.intersection(keep)]
        tests.append({"source": src, **mixed(mat[F] - mat[F + "_rd"], repo)})
    for t, p in zip(tests, holm([t["p"] for t in tests])):
        t["p_holm"] = p
    out["named"] = tests
    unnamed = rows[rows.task_id.isin(st["no_explicit"])]
    keep_u = shared_prs(unnamed)
    moves = {}
    for src in ("co_edited", "symbol"):
        mat = pr_level(unnamed, src).loc[lambda m: m.index.intersection(keep_u)]
        moves[src] = float((mat[F] - mat[F + "_rd"]).mean())
    out["unnamed_mean_move"] = moves
    ok = (all(t["estimate"] > 0 and t["p_holm"] < 0.05 for t in tests)
          and all(abs(v) <= 0.005 for v in moves.values()))
    return {"pass": ok, "testable": True, "named_matched_prs": int(len(keep)), **out}


def descriptive(rows, shared, repo):
    leak = pd.read_csv(OUT / "issue_path_leak.csv")
    ball = pd.read_csv(OUT / "ball.csv") if (OUT / "ball.csv").exists() else None
    st = leak_strata(rows)
    arms = {}
    named = rows[rows.task_id.isin(st["explicit"])]
    keep = shared_prs(named)
    for src in ("co_edited", "symbol"):
        mat = pr_level(named, src).loc[lambda m: m.index.intersection(keep)]
        arms[src] = {sfx: float((mat[F] - mat[F + sfx]).mean())
                     for sfx in ("_rd", "_rdp", "_rds") if F + sfx in mat}
    return {
        "n_tasks": int(rows.task_id.nunique()), "n_prs": int(rows.instance_id.nunique()),
        "n_repos": int(rows.repo_key.nunique()), "n_prs_matched": int(len(shared)),
        "explicit_rate": float(leak.explicit.mean()),
        "redaction_arms_named_matched": arms,
        "ball": None if ball is None else {
            "share_mean": float(ball.ball_share_of_repo.mean()),
            "recall_mean": float(ball.ball_recall.mean()),
            "precision_median": float((ball.ball_recall * ball.key_files
                                       / ball.ball_files.where(ball.ball_files > 0)).median())},
    }


def main():
    rows = pd.read_parquet(OUT / "rows.parquet")
    shared = shared_prs(rows)
    repo = rows.groupby("instance_id")["repo_key"].first()
    res = {"E1": e1(rows, shared), "E2": e2(rows, shared, repo), "E3": e3(rows, repo),
           "E4": e4(rows, repo), "descriptive": descriptive(rows, shared, repo)}
    (OUT / "predictions.json").write_text(json.dumps(res, indent=1, default=float))
    for k in ("E1", "E2", "E3", "E4"):
        print(k, {True: "PASS", False: "FAIL", None: "NOT TESTABLE"}[res[k]["pass"]])
    print(json.dumps(res, indent=1, default=float))
    auc_table(rows, ("co_edited", "symbol"), prs=shared, ci=False).to_csv(
        OUT / "per_source_shared.csv", index=False)
    auc_table(rows, ("co_edited", "symbol"), ci=False).to_csv(
        OUT / "per_source.csv", index=False)


if __name__ == "__main__":
    np.seterr(all="ignore")
    main()
