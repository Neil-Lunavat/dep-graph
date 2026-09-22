"""Step 2: fix the repository sample and the task sample (D10, D11, D19 as recorded).

Repos: every candidate that passes R1–R5 + exclusions under R2/R3 variant b and has >= K
eligible tasks (1–10 files, 200-line source cap, fail-to-pass test, prebuilt image) in the
D11 datasets after G18 dedup. No draw of repos (D10c = take all).
Tasks: within each repo, sort eligible tasks by SHA-256(seed + instance_id), keep the first
TASK_CAP (D10d).

Writes data/repos.csv and data/sample_tasks.csv
"""
from __future__ import annotations

import json

import pandas as pd

from depgraphs.datasets import ROOT
from depgraphs.recount import eligible
from depgraphs.sampling import draw_key, size_terciles

SEED = 20260922
K = 10
TASK_CAP = 20
DATASETS = ["swebench_full", "swebench_live_full", "swerebench_filtered"]   # D11 option D
OUT = ROOT / "results" / "step2"


def eligible_tasks() -> pd.DataFrame:
    t = pd.read_parquet(OUT / "task_index.parquet")
    t = t[t.dataset.isin(DATASETS)].copy()
    t["task_key"] = t.repo_key + "#" + t.pr_number.fillna(t.base_commit)
    t["_o"] = t.dataset.map({d: i for i, d in enumerate(DATASETS)})
    t = t.sort_values(["_o", "instance_id"]).drop_duplicates("task_key").drop(columns="_o")
    env = pd.read_csv(OUT / "env_availability.csv")
    img = env.drop_duplicates("instance_id").set_index("instance_id")
    t["image"] = t.instance_id.map(img.image)
    t = t[eligible(t, 1, study=True) & t.instance_id.map(img.on_dockerhub).fillna(False).astype(bool)]
    return t


def main():
    rules = pd.read_csv(OUT / "gate_a_repos.csv").set_index("repo_key")
    t = eligible_tasks()
    per = t.groupby("repo_key").size()
    ok = [rk for rk, n in per.items() if n >= K and bool(rules.passes_variant_b.get(rk, False))]
    t = t[t.repo_key.isin(ok)].copy()
    t["draw_key"] = [draw_key(SEED, i) for i in t.instance_id]
    t["draw_rank"] = t.groupby("repo_key").draw_key.rank(method="first").astype(int)
    s = t[t.draw_rank <= TASK_CAP].sort_values(["repo_key", "draw_rank"])
    s["file_group"] = s.n_src_py_files_study.map(lambda n: "single" if n == 1 else "multi")
    cols = ["repo", "repo_key", "dataset", "instance_id", "pr_number", "base_commit",
            "created_at", "image", "n_src_py_files_study", "file_group",
            "src_changed_lines_study", "n_new_src_py_study", "n_f2p", "draw_rank"]
    (ROOT / "data").mkdir(exist_ok=True)
    s[cols].to_csv(ROOT / "data" / "sample_tasks.csv", index=False)

    r = rules.loc[sorted(ok)].copy()
    gh_path = ROOT / "data" / "github_meta.jsonl"
    gh = pd.DataFrame([json.loads(l) for l in gh_path.read_text(encoding="utf-8").splitlines()]
                      ).drop_duplicates("repo_key").set_index("repo_key")
    out = pd.DataFrame({
        "name": r.repo,
        "url": "https://github.com/" + r.repo,
        "pinned_sha": r.provisional_sha,
        "licence": r.licence_spdx.where(r.licence_spdx.notna() & r.licence_spdx.ne("NOASSERTION"),
                                        r.licence_dataset).fillna("see " + r.licence_files.fillna("")),
        "nontest_py_files": r.nontest_py_files_b.astype(int),
        "python_share": r.python_share_b,
        "block": ["swebench" if "swebench_full" in d else "fresh" for d in r.datasets],
        "eligible_tasks": per.loc[r.index].values,
        "sampled_tasks": s.groupby("repo_key").size().reindex(r.index).values,
        "description": gh.description.reindex(r.index).values,
        "archived": gh.archived.reindex(r.index).values,
    }, index=r.index)
    out["size_tercile"] = size_terciles(out.nontest_py_files.reset_index(drop=True)).values
    out.index.name = "repo_key"
    labels = ROOT / "data" / "domain_labels.csv"   # assigned from descriptions (G17)
    if labels.exists():
        out = out.join(pd.read_csv(labels).set_index("repo_key"), how="left")
    out.to_csv(ROOT / "data" / "repos.csv")
    print(len(out), "repos;", len(s), "tasks;", (s.file_group == "single").sum(), "single-file")
    print(out.block.value_counts().to_dict(), out.size_tercile.value_counts().to_dict())


if __name__ == "__main__":
    main()
