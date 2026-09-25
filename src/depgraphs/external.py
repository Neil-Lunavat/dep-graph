"""An external test set: repositories the study never saw, drawn by the study's own rules.

A review observed that the 200 repository splits of the held-out analysis are resamples of the
same 112 repositories, so they show the recommendation is stable, not that it generalises. The
test for that is repositories outside the sample. Seven exist that pass every sampling rule
(R1-R5 and the exclusions, under the same variant b) and were left out only because D11
restricted the task sources to SWE-bench, SWE-bench-Live and SWE-rebench: their eligible tasks
come from SWE-Gym and SWE-bench Pro. Nothing in the study has touched them.

This module draws their tasks exactly as `sample.py` draws the main sample -- the same
eligibility rule, the same seed, the same cap of 20 pull requests per repository -- with the
two extra sources admitted, and lays out a separate tree for the pipeline to run in:

    external/data/{sample_tasks.csv, repos.csv}   written here
    external/data/datasets, external/results/step2 -> the main tree's copies (read-only use)

Then every later stage runs unchanged with DEPGRAPHS_ROOT=external, and writes only there.
The predictions tested on this set were committed before any of it was scored
(paper/external_predictions.md).

Usage:  python -m depgraphs.external          (prepare the tree)
        DEPGRAPHS_ROOT=external python run.py graphs keys_static tasks lexfeat issues redact
        DEPGRAPHS_ROOT=external python -m depgraphs.study2
        ...
"""
from __future__ import annotations

import json
import os

import pandas as pd

from depgraphs.datasets import ROOT
from depgraphs.sample import DATASETS, K, OUT, SEED, TASK_CAP
from depgraphs.sampling import draw_key

EXT = ROOT / "external"
# D11's sources first, so that a pull request present in both keeps its D11 row, as the
# main sample's de-duplication would have done; then the two sources D11 left out
SOURCES = DATASETS + ["swegym", "swebench_pro"]


def external_repos() -> list[str]:
    rules = pd.read_csv(OUT / "gate_a_repos.csv").set_index("repo_key")
    main = set(pd.read_csv(ROOT / "data" / "repos.csv").repo_key)
    return sorted(rk for rk, ok in rules.passes_variant_b.items()
                  if bool(ok) and rk not in main)


def main():
    from depgraphs.sample import eligible_tasks

    if os.environ.get("DEPGRAPHS_ROOT"):
        raise SystemExit("run this from the main tree; it builds the external one")
    repos = external_repos()
    t = eligible_tasks(SOURCES)
    t = t[t.repo_key.isin(repos)].copy()
    per = t.groupby("repo_key").size()
    keep = [rk for rk in repos if per.get(rk, 0) >= K]
    t = t[t.repo_key.isin(keep)].copy()
    t["draw_key"] = [draw_key(SEED, i) for i in t.instance_id]
    t["draw_rank"] = t.groupby("repo_key").draw_key.rank(method="first").astype(int)
    s = t[t.draw_rank <= TASK_CAP].sort_values(["repo_key", "draw_rank"]).copy()
    s["file_group"] = s.n_src_py_files_study.map(lambda n: "single" if n == 1 else "multi")
    cols = ["repo", "repo_key", "dataset", "instance_id", "pr_number", "base_commit",
            "created_at", "image", "n_src_py_files_study", "file_group",
            "src_changed_lines_study", "n_new_src_py_study", "n_f2p", "draw_rank"]

    (EXT / "data").mkdir(parents=True, exist_ok=True)
    (EXT / "results").mkdir(parents=True, exist_ok=True)
    s[cols].to_csv(EXT / "data" / "sample_tasks.csv", index=False)

    rules = pd.read_csv(OUT / "gate_a_repos.csv").set_index("repo_key").loc[keep]
    pd.DataFrame({
        "repo_key": keep, "name": rules.repo.values,
        "url": ["https://github.com/" + r for r in rules.repo],
        "pinned_sha": rules.provisional_sha.values,
        "licence": rules.licence_spdx.values,
        "nontest_py_files": rules.nontest_py_files_b.astype(int).values,
        "python_share": rules.python_share_b.values,
        "datasets": rules.datasets.values,
        "eligible_tasks": per.loc[keep].values,
        "sampled_tasks": s.groupby("repo_key").size().reindex(keep).values,
    }).to_csv(EXT / "data" / "repos.csv", index=False)

    # shared, read-only inputs: the downloaded datasets and the Gate A tables
    for link, target in ((EXT / "data" / "datasets", ROOT / "data" / "datasets"),
                         (EXT / "results" / "step2", ROOT / "results" / "step2")):
        if not link.exists():
            link.symlink_to(target, target_is_directory=True)
    (EXT / "logs").mkdir(exist_ok=True)
    print(len(keep), "repos;", len(s), "pull requests;",
          (s.file_group == "single").sum(), "single-file")
    print(s.groupby(["repo_key", "dataset"]).size().to_string())
    print(json.dumps({"repos": keep}))


if __name__ == "__main__":
    main()
