"""A third answer key, written by people: ContextBench's gold context.

Both of the study's keys are proxies. `co_edited` is what the fix happened to touch, and
`symbol` is built by resolving names through imports, the same substrate the structural
orderings walk. ContextBench (Li et al., 2026) annotates by hand the code an agent must see
to reconstruct a passing fix. Its Python tasks from SWE-bench Verified and SWE-bench Pro are
in datasets this study already holds, so they can be run through the pipeline unchanged and
scored against a key no part of the pipeline built.

This module draws those tasks with the main sample's eligibility rule, seed and cap of 20
pull requests per repository, lays out a separate tree as `external.py` does, and, after the
`tasks` stage has run there, adds each task's `gold` key: the Python files in the task's gold
context, minus the seed, restricted to graph nodes like every other key. `gold_readonly` is that key less every file
the pull request edits: exploratory, added after the predictions committed before scoring had been scored.

The predictions tested on this set were committed before any of it was scored
(paper/contextbench_predictions.md).

Usage:  python -m depgraphs.contextbench prepare
        DEPGRAPHS_ROOT=contextbench python run.py graphs keys_static tasks
        DEPGRAPHS_ROOT=contextbench python -m depgraphs.contextbench addkey
        DEPGRAPHS_ROOT=contextbench python run.py lexfeat issues redact
        DEPGRAPHS_ROOT=contextbench python -m depgraphs.study2
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

from depgraphs.datasets import ROOT
from depgraphs.recount import eligible
from depgraphs.sample import OUT, SEED, TASK_CAP
from depgraphs.sampling import draw_key

 # the main tree, whatever DEPGRAPHS_ROOT says
MAIN = Path(__file__).resolve().parents[2]
CB = MAIN / "contextbench"
PARQUET = MAIN / "data" / "contextbench" / "full.parquet"
URL = ("https://huggingface.co/datasets/Contextbench/ContextBench/resolve/"
       "c2855792b006af41c67202d33883fb9d46362853/data/full.parquet")
# ContextBench's sources, mapped to the study's names for the same datasets
SOURCES = {"Verified": "swebench_full", "Pro": "swebench_pro"}


def load() -> pd.DataFrame:
    if not PARQUET.exists():
        PARQUET.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["curl", "-sSL", "-o", str(PARQUET), URL], check=True)
    cb = pd.read_parquet(PARQUET)
    return cb[(cb.language.str.lower() == "python") & cb.source.isin(list(SOURCES))]


def gold_files(cb: pd.DataFrame) -> dict[str, list[str]]:
    return {r.original_inst_id: sorted({d["file"] for d in json.loads(r.gold_context)
                                        if d["file"].endswith(".py")})
            for r in cb.itertuples()}


def prepare():
    if ROOT != MAIN:
        raise SystemExit("run this from the main tree; it builds the contextbench one")
    cb = load()
    src = {r.original_inst_id: SOURCES[r.source] for r in cb.itertuples()}
    t = pd.read_parquet(OUT / "task_index.parquet")
    t = t[t.instance_id.isin(src) & (t.dataset == t.instance_id.map(src))].copy()
    # the study's eligibility rule; the Docker-image condition is dropped because nothing
    # here is executed
    t = t[eligible(t, 1, study=True)].copy()
    t["draw_key"] = [draw_key(SEED, i) for i in t.instance_id]
    t["draw_rank"] = t.groupby("repo_key").draw_key.rank(method="first").astype(int)
    s = t[t.draw_rank <= TASK_CAP].sort_values(["repo_key", "draw_rank"]).copy()
    s["file_group"] = s.n_src_py_files_study.map(lambda n: "single" if n == 1 else "multi")
    s["image"] = ""
    cols = ["repo", "repo_key", "dataset", "instance_id", "pr_number", "base_commit",
            "created_at", "image", "n_src_py_files_study", "file_group",
            "src_changed_lines_study", "n_new_src_py_study", "n_f2p", "draw_rank"]
    (CB / "data").mkdir(parents=True, exist_ok=True)
    (CB / "results").mkdir(parents=True, exist_ok=True)
    (CB / "logs").mkdir(exist_ok=True)
    s[cols].to_csv(CB / "data" / "sample_tasks.csv", index=False)

    pinned = {}
    for f in (MAIN / "data" / "repos.csv", MAIN / "external" / "data" / "repos.csv"):
        pinned.update(pd.read_csv(f).set_index("repo_key").pinned_sha.to_dict())
    repos = sorted(s.repo_key.unique())
    latest = s.sort_values("created_at").groupby("repo_key").base_commit.last()
    pd.DataFrame({"repo_key": repos, "name": repos,
                  "url": ["https://github.com/" + r for r in repos],
                  "pinned_sha": [pinned.get(r, latest[r]) for r in repos],
                  "sampled_tasks": s.groupby("repo_key").size().reindex(repos).values,
                  }).to_csv(CB / "data" / "repos.csv", index=False)

    for link, target in ((CB / "data" / "datasets", MAIN / "data" / "datasets"),
                         (CB / "results" / "step2", MAIN / "results" / "step2")):
        if not link.exists():
            link.symlink_to(target, target_is_directory=True)
    # clones: share objects with an existing clone where there is one, so that checking out
    # a commit here never touches the main tree's working copy
    for rk in repos:
        d = CB / "data" / "repos" / rk.replace("/", "__")
        if (d / ".git").exists():
            continue
        have = [p / rk.replace("/", "__") for p in (MAIN / "data" / "repos",
                                                     MAIN / "external" / "data" / "repos")]
        have = [p for p in have if (p / ".git").exists()]
        d.parent.mkdir(parents=True, exist_ok=True)
        if have:
            subprocess.run(["git", "clone", "-q", "--shared", "--no-checkout", str(have[0]),
                            str(d)], check=True)
            subprocess.run(["git", "remote", "set-url", "origin",
                            "https://github.com/%s.git" % rk], cwd=d, check=True)
        else:
            d.mkdir(parents=True)
            subprocess.run(["git", "init", "-q"], cwd=d, check=True)
            subprocess.run(["git", "remote", "add", "origin",
                            "https://github.com/%s.git" % rk], cwd=d, check=True)
    print(len(repos), "repos;", len(s), "pull requests;",
          (s.file_group == "single").sum(), "single-file")
    print(s.groupby("repo_key").size().to_string())


def addkey():
    """Add the `gold` key to the contextbench tree's tasks.jsonl, in place."""
    from depgraphs.graphs import load_graph

    if ROOT.resolve() != CB.resolve():
        raise SystemExit("run with DEPGRAPHS_ROOT=contextbench")
    gold = gold_files(load())
    path = CB / "data" / "tasks.jsonl"
    tasks = [json.loads(l) for l in open(path, encoding="utf-8")]
    nodes_of = {}
    n_empty = 0
    for t in tasks:
        k = (t["repo_key"], t["base_commit"])
        if k not in nodes_of:
            nodes_of[k] = set(load_graph(*k)["nodes"])
        g = [f for f in gold.get(t["instance_id"], []) if f != t["seed"]]
        t["keys"]["gold"] = sorted(set(g) & nodes_of[k])
        # exploratory, added after G1-G4 were scored (POSTHOC.md): the gold files the fix
        # reads but does not edit, which is the context a graph walk is claimed to find
        edited = set(t["keys"].get("co_edited", [])) | {t["seed"]}
        t["keys"]["gold_readonly"] = sorted(set(t["keys"]["gold"]) - edited)
        dropped = sorted(set(g) - nodes_of[k])
        if dropped:
            t["dropped_not_in_graph"]["gold"] = dropped
        n_empty += not t["keys"]["gold"]
    with open(path, "w", encoding="utf-8") as f:
        for t in tasks:
            f.write(json.dumps(t) + "\n")
    print(len(tasks), "tasks;", len(tasks) - n_empty, "with a non-empty gold key")


if __name__ == "__main__":
    {"prepare": prepare, "addkey": addkey}[sys.argv[1]]()
