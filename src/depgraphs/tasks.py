"""Step 5e: turn PRs into tasks (one per starting file) with per-source answer keys.

A PR whose change touches k existing non-test source files that are graph nodes gives k tasks;
each file in turn is the seed, the rest of the evidence is the key (ROADMAP 5e).

Key sources (N4 — always kept separate):
  co_edited : other existing source files modified by the PR
  symbol    : files defining names used on the PR's added lines (minus the seed)
  execution : filled in later from the Docker runs (keys_exec.py), per D20 rule
Every key file must exist at the base commit and be a graph node; files that are not
(new files, non-importable paths) are counted per task, never silently dropped.

Also records RQ3 graph distances from the seed to every key file: following import
direction, against it, and ignoring direction (None = no path).

Writes data/tasks.jsonl and results/step5/tasks_summary.csv
"""
from __future__ import annotations

import json

import networkx as nx
import pandas as pd

from depgraphs.datasets import ROOT
from depgraphs.graphs import load_graph

KEYS = ROOT / "data" / "keys_static"
EXEC = ROOT / "data" / "keys_exec"


def distances(g: nx.DiGraph, seed: str, targets: list[str]) -> dict:
    fwd = nx.single_source_shortest_path_length(g, seed)
    rev = nx.single_source_shortest_path_length(g.reverse(copy=False), seed)
    und = nx.single_source_shortest_path_length(g.to_undirected(as_view=True), seed)
    return {t: {"forward": fwd.get(t), "reverse": rev.get(t), "undirected": und.get(t)}
            for t in targets}


def main():
    sample = pd.read_csv(ROOT / "data" / "sample_tasks.csv")
    exec_keys = {}
    if EXEC.exists():
        for p in EXEC.glob("*.json"):
            exec_keys[p.stem] = json.loads(p.read_text())
    rows, out = [], []
    for pr in sample.itertuples():
        k = json.loads((KEYS / f"{pr.instance_id}.json").read_text())
        gdata = load_graph(pr.repo_key, pr.base_commit)
        nodes = set(gdata["nodes"])
        g = nx.DiGraph()
        g.add_nodes_from(gdata["nodes"])
        g.add_edges_from(map(tuple, gdata["edges"]))
        edited = k.get("co_edited", [])
        seeds = [f for f in edited if f in nodes]
        ex = exec_keys.get(pr.instance_id)
        pr_row = {"instance_id": pr.instance_id, "repo_key": pr.repo_key,
                  "n_edited": len(edited), "n_seeds": len(seeds),
                  "edited_not_in_graph": len(edited) - len(seeds),
                  "n_new_files": len(k.get("new_files", [])),
                  "has_exec": ex is not None}
        rows.append(pr_row)
        for seed in seeds:
            src = {"co_edited": [f for f in edited if f != seed],
                   "symbol": [f for f in k.get("symbol", {}) if f != seed]}
            if ex is not None:
                for rule, files in ex.get("keys", {}).items():
                    src[f"execution_{rule}"] = [f for f in files if f != seed]
            dropped = {s: sorted(set(v) - nodes) for s, v in src.items()}
            src = {s: sorted(set(v) & nodes) for s, v in src.items()}
            all_files = sorted(set().union(*src.values()))
            out.append({
                "task_id": f"{pr.instance_id}::{seed}",
                "instance_id": pr.instance_id, "repo_key": pr.repo_key,
                "dataset": pr.dataset, "base_commit": pr.base_commit,
                "created_at": pr.created_at, "file_group": pr.file_group,
                "seed": seed, "keys": src,
                "dropped_not_in_graph": {s: v for s, v in dropped.items() if v},
                "new_files": k.get("new_files", []),
                "distances": distances(g, seed, all_files),
            })
    with open(ROOT / "data" / "tasks.jsonl", "w", encoding="utf-8") as f:
        for t in out:
            f.write(json.dumps(t) + "\n")
    s = pd.DataFrame(rows)
    (ROOT / "results" / "step5").mkdir(parents=True, exist_ok=True)
    s.to_csv(ROOT / "results" / "step5" / "tasks_summary.csv", index=False)
    print(len(out), "tasks from", (s.n_seeds > 0).sum(), "PRs;",
          (s.n_seeds == 0).sum(), "PRs gave no seed;",
          int(s.edited_not_in_graph.sum()), "edited files not graph nodes")


if __name__ == "__main__":
    main()
