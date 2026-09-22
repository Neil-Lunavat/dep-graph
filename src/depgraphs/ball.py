"""How much of a repository the two-hop neighbourhood of the seed actually is.

"The files you need are within two hops" is the usual defence of graph-based retrieval.
This measures the other half of that claim: how large the two-hop ball is relative to the
repository and to a reading budget, and how much recall it buys over taking the same
number of files at random.

Writes results/study2/ball.csv           per task
       results/study2/distance_profile.csv  key files by hop distance and key source
"""
from __future__ import annotations

import collections
import json

import networkx as nx
import pandas as pd

from depgraphs.lexfeat import ROOT
from depgraphs.study2 import OUT, load_graph


def main():
    tasks = [json.loads(l) for l in open(ROOT / "data" / "tasks.jsonl", encoding="utf-8")]
    by = collections.defaultdict(list)
    for t in tasks:
        by[(t["repo_key"], t["base_commit"])].append(t)

    rows = []
    prof = collections.defaultdict(collections.Counter)
    for (rk, sha), ts in by.items():
        rd = rk.replace("/", "__")
        try:
            nodes, edges, lines = load_graph(rd, sha)
        except FileNotFoundError:
            continue
        G = nx.DiGraph()
        G.add_nodes_from(nodes)
        G.add_edges_from(e for e in edges if e[0] != e[1])
        U = G.to_undirected()
        nodeset = set(nodes)
        for t in ts:
            s = t["seed"]
            if s not in U:
                continue
            k = (set(t["keys"].get("co_edited", [])) | set(t["keys"].get("symbol", []))) \
                & nodeset
            k -= {s}
            if not k:
                continue
            d = nx.single_source_shortest_path_length(U, s, cutoff=2)
            ball = set(d) - {s}
            rows.append({
                "task_id": t["task_id"], "repo_key": rk,
                "repo_files": len(nodes), "ball_files": len(ball),
                "ball_lines": sum(lines.get(p, 0) for p in ball),
                "key_files": len(k), "key_lines": sum(lines.get(p, 0) for p in k),
                "ball_recall": len(k & ball) / len(k),
                "ball_share_of_repo": len(ball) / max(len(nodes) - 1, 1),
            })
            full = nx.single_source_shortest_path_length(U, s)
            for src, files in t["keys"].items():
                for f in files:
                    if f == s or f not in nodeset:
                        continue
                    h = full.get(f)
                    prof[src][("unreachable" if h is None
                               else str(h) if h <= 2 else "3+")] += 1

    df = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT / "ball.csv", index=False)
    pr = pd.DataFrame([{"source": s, "hops": h, "n": n,
                        "share": n / sum(c.values())}
                       for s, c in prof.items() for h, n in sorted(c.items())])
    pr.to_csv(OUT / "distance_profile.csv", index=False)

    print("tasks", len(df))
    print(df[["repo_files", "ball_files", "ball_lines", "key_files", "key_lines"]]
          .median().round(1).to_string())
    print("ball recall      mean %.3f" % df["ball_recall"].mean())
    print("ball share repo  mean %.3f  median %.3f"
          % (df["ball_share_of_repo"].mean(), df["ball_share_of_repo"].median()))
    print("recall lift over taking the same share at random: %.2fx"
          % (df["ball_recall"].mean() / df["ball_share_of_repo"].mean()))
    print(pr.to_string(index=False))


if __name__ == "__main__":
    main()
