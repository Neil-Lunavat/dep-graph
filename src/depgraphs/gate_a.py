"""Gate A tables: what each (D11 task source, D19 filter, K) combination leaves, after 9.4 rules.

Reads data/candidates.csv, data/github_meta.jsonl, results/step2/env_availability.csv.
Writes results/step2/gate_a_options.csv, gate_a_repos.csv, gate_a_power.csv,
gate_a_strata.csv. Nothing here draws a sample.
"""
from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd

from depgraphs.datasets import ROOT
from depgraphs.recount import eligible

OUT = ROOT / "results" / "step2"

OPTIONS = {
    "A_swebench": ["swebench_full"],
    "B_swebench+gym": ["swebench_full", "swegym"],
    "C_fresh": ["swebench_live_full", "swerebench_filtered"],
    "D_mixed": ["swebench_full", "swebench_live_full", "swerebench_filtered"],
    "D+gym+pro": ["swebench_full", "swegym", "swebench_live_full", "swerebench_filtered",
                  "swebench_pro"],
}
FILTERS = {"2-10": 2, "1-10": 1}
KS = [10, 15, 20]


def load_all():
    cand = pd.read_csv(ROOT / "data" / "candidates.csv").set_index("repo_key")
    gh_path = ROOT / "data" / "github_meta.jsonl"
    gh = pd.DataFrame([json.loads(l) for l in gh_path.read_text(encoding="utf-8").splitlines()]
                      ) if gh_path.exists() else pd.DataFrame(columns=["repo_key"])
    gh = gh.drop_duplicates("repo_key").set_index("repo_key")
    env_path = OUT / "env_availability.csv"
    env = pd.read_csv(env_path) if env_path.exists() else None
    t = pd.read_parquet(OUT / "task_index.parquet")
    return cand, gh, env, t


def repo_rules(cand: pd.DataFrame, gh: pd.DataFrame) -> pd.DataFrame:
    r = cand.copy()
    r = r.join(gh[[c for c in ["fork", "archived", "licence_spdx", "description", "parent",
                               "stargazers_count", "topics"] if c in gh]], how="left")
    r["measured"] = r.nontest_py_files.notna()
    r["R2_python_share"] = r.python_share >= 0.80
    r["R3_min_files"] = r.nontest_py_files >= 50
    from depgraphs.candidates import CLONES, licence_files
    r["licence_files"] = [";".join(licence_files(CLONES / k.replace("/", "__")))
                          if (CLONES / k.replace("/", "__")).exists() else ""
                          for k in r.index]
    lic = r.licence_dataset.notna() | r.licence_files.fillna("").ne("")
    if "licence_spdx" in r:
        lic |= r.licence_spdx.notna() & r.licence_spdx.ne("NOASSERTION")
    r["R5_licence"] = lic
    r["X_fork"] = r.get("fork", pd.Series(False, index=r.index)).fillna(False).astype(bool)
    r["X_notebooks"] = r.ipynb_files > r.py_files
    r["X_generated_vendored"] = r.generated_or_vendored_share > 0.30
    r["flag_monorepo_check"] = r.packaging_files >= 5     # flag for Neil; not an auto-exclusion
    r["passes_R2_R3_R5_X"] = (r.measured & r.R2_python_share & r.R3_min_files & r.R5_licence
                              & ~r.X_fork & ~r.X_notebooks & ~r.X_generated_vendored)
    vb = OUT / "r2_variants.csv"
    if vb.exists():   # variant b of R2/R3 (see r2_variant.py) — shown to Neil, not applied
        v = pd.read_csv(vb).set_index("repo_key")
        r = r.join(v[["python_share_b", "nontest_py_files_b"]], how="left")
        r["passes_variant_b"] = (r.measured & (r.python_share_b >= 0.80)
                                 & (r.nontest_py_files_b >= 50) & r.R5_licence & ~r.X_fork
                                 & ~r.X_notebooks & ~r.X_generated_vendored)
    return r


def option_table(t, env, rules, col="passes_R2_R3_R5_X"):
    rows, per_repo_rows = [], []
    has_img = set(env[env.on_dockerhub == True].instance_id) if env is not None else None
    checked = set(env.instance_id) if env is not None else set()
    for opt, dsets in OPTIONS.items():
        d = t[t.dataset.isin(dsets)].copy()
        d["task_key"] = d.repo_key + "#" + d.pr_number.fillna(d.base_commit)
        d["_o"] = d.dataset.map({x: i for i, x in enumerate(dsets)})
        d = d.sort_values(["_o", "instance_id"]).drop_duplicates("task_key")
        for fname, lo in FILTERS.items():
            e = d[eligible(d, lo)]
            n_unchecked = (~e.instance_id.isin(checked)).sum()
            if has_img is not None:
                e_img = e[e.instance_id.isin(has_img) | ~e.instance_id.isin(checked)]
            else:
                e_img = e
            per = e_img.groupby("repo_key").agg(tasks=("task_key", "size"),
                                                prs=("pr_number", "nunique"))
            per = per.join(rules[[col, "nontest_py_files"]].rename(
                columns={col: "passes_R2_R3_R5_X"}), how="left")
            for K in KS:
                ok = per[(per.tasks >= K) & per.passes_R2_R3_R5_X.fillna(False).astype(bool)]
                unmeasured = per[(per.tasks >= K) & per.passes_R2_R3_R5_X.isna()]
                rows.append({"option": opt, "filter": fname, "K": K,
                             "repos_passing": len(ok), "tasks_in_passing": int(ok.tasks.sum()),
                             "median_tasks_per_repo": float(ok.tasks.median()) if len(ok) else 0,
                             "repos_K_but_failing_rules": int(((per.tasks >= K)
                                 & (per.passes_R2_R3_R5_X == False)).sum()),
                             "repos_K_not_measured": len(unmeasured),
                             "eligible_without_image": int(len(e) - len(e_img)),
                             "eligible_image_unchecked": int(n_unchecked)})
                for rk, x in ok.iterrows():
                    per_repo_rows.append({"option": opt, "filter": fname, "K": K,
                                          "repo_key": rk, "tasks": int(x.tasks)})
    return pd.DataFrame(rows), pd.DataFrame(per_repo_rows)


def power_table():
    """Smallest Spearman correlation detectable with 80% power, two-sided, via Fisher z with
    the Fieller et al. (1957) variance 1.06/(n-3). Uncorrected alpha and a Holm-style worst
    case alpha/m for m pre-listed pairs."""
    from statistics import NormalDist
    z = NormalDist().inv_cdf
    rows = []
    for n in (12, 20, 30, 40, 60, 80, 120):
        for m in (1, 20, 100):
            a = 0.05 / m
            zz = (z(1 - a / 2) + z(0.80)) * math.sqrt(1.06 / (n - 3))
            rows.append({"n_repos": n, "pairs_tested": m, "alpha_per_test": round(a, 5),
                         "min_detectable_rho": round(math.tanh(zz), 2)})
    return pd.DataFrame(rows)


def main():
    cand, gh, env, t = load_all()
    rules = repo_rules(cand, gh)
    rules.to_csv(OUT / "gate_a_repos.csv")
    opts, per = option_table(t, env, rules)
    opts.to_csv(OUT / "gate_a_options.csv", index=False)
    if "passes_variant_b" in rules:
        ob, _ = option_table(t, env, rules, "passes_variant_b")
        ob.to_csv(OUT / "gate_a_options_variant_b.csv", index=False)
    per.to_csv(OUT / "gate_a_option_repos.csv", index=False)
    power_table().to_csv(OUT / "gate_a_power.csv", index=False)


if __name__ == "__main__":
    main()
