"""Step 4: Table 1 — structure metrics per repository, exactly as fixed in paper/table1_metrics.md.

Writes results/table1.csv (pinned SHA, one row per repo) and
results/step4/table1_task_commits_median.csv (median over each repo's task commits).
"""
from __future__ import annotations

import math
from concurrent.futures import ProcessPoolExecutor

import networkx as nx
import numpy as np
import pandas as pd

from depgraphs.datasets import ROOT
from depgraphs.graphs import graph_path, load_graph


def gini(x) -> float:
    x = np.sort(np.asarray(x, dtype=float))
    n = len(x)
    if n == 0 or x.sum() == 0:
        return 0.0
    return float((2 * np.arange(1, n + 1) - n - 1).dot(x) / (n * x.sum()))


def metrics(nodes, edges, lines=None, unresolved=0, internal=0) -> dict:
    g = nx.DiGraph()
    g.add_nodes_from(nodes)
    g.add_edges_from((a, b) for a, b in edges if a != b)
    n, m = g.number_of_nodes(), g.number_of_edges()
    indeg = np.array([d for _, d in g.in_degree()]) if n else np.array([])
    outdeg = np.array([d for _, d in g.out_degree()]) if n else np.array([])

    k = math.ceil(0.05 * n)
    top = sorted(g.nodes, key=lambda v: (-g.in_degree(v), v))[:k]
    hub = sum(g.in_degree(v) for v in top) / m if m else 0.0

    sccs = [c for c in nx.strongly_connected_components(g) if len(c) > 1]
    largest = max((len(c) for c in sccs), default=0)
    cond = nx.condensation(g)
    depth = nx.dag_longest_path_length(cond) if cond.number_of_nodes() else 0

    total = cnt = mx = 0
    for src, dist in nx.all_pairs_shortest_path_length(g):
        for dst, d in dist.items():
            if dst != src:
                total += d
                cnt += 1
                mx = max(mx, d)
    wcc = list(nx.weakly_connected_components(g))
    gu = g.to_undirected()
    if m:
        comms = nx.community.louvain_communities(gu, resolution=1, seed=0)
        mod = nx.community.modularity(gu, comms)
    else:
        comms, mod = [{v} for v in g.nodes], 0.0
    depths = [p.count("/") for p in g.nodes]
    loc = [lines[p] for p in g.nodes] if lines else []
    return {
        "files": n, "import_edges": m,
        "density": m / (n * (n - 1)) if n > 1 else float("nan"),
        "indeg_mean": indeg.mean() if n else float("nan"), "indeg_median": float(np.median(indeg)) if n else float("nan"),
        "indeg_max": int(indeg.max()) if n else 0, "indeg_gini": gini(indeg),
        "outdeg_mean": outdeg.mean() if n else float("nan"), "outdeg_median": float(np.median(outdeg)) if n else float("nan"),
        "outdeg_max": int(outdeg.max()) if n else 0, "outdeg_gini": gini(outdeg),
        "hub_share_top5pct": hub,
        "n_loops": len(sccs), "largest_loop": largest,
        "largest_loop_share": largest / n if n else 0.0,
        "share_in_loops": sum(map(len, sccs)) / n if n else 0.0,
        "depth_condensed": depth,
        "spl_mean": total / cnt if cnt else float("nan"), "spl_max": mx if cnt else float("nan"),
        "n_wcc": len(wcc), "largest_wcc_share": max(map(len, wcc)) / n if n else 0.0,
        "isolated": int(sum(1 for v in g.nodes if g.degree(v) == 0)),
        "isolated_share": sum(1 for v in g.nodes if g.degree(v) == 0) / n if n else 0.0,
        "modularity": mod, "n_clusters": len(comms),
        "clustering": nx.average_clustering(gu) if n else 0.0,
        "single_importer_share": float((indeg == 1).mean()) if n else 0.0,
        "nesting_max": max(depths, default=0), "nesting_mean": float(np.mean(depths)) if depths else 0.0,
        "unresolved_share": unresolved / internal if internal else 0.0,
        "loc_total": int(sum(loc)), "loc_mean": float(np.mean(loc)) if loc else 0.0,
        "loc_median": float(np.median(loc)) if loc else 0.0,
    }


def for_graph(args) -> dict:
    rk, sha = args
    g = load_graph(rk, sha)
    return {"repo_key": rk, "sha": sha,
            **metrics(g["nodes"], g["edges"], g["lines"],
                      g["counts"].get("unresolved_internal", 0), g["internal_statements"])}


def main(workers: int = 8):
    repos = pd.read_csv(ROOT / "data" / "repos.csv")
    tasks = pd.read_csv(ROOT / "data" / "sample_tasks.csv")
    pinned = [(r.repo_key, r.pinned_sha) for r in repos.itertuples()
              if graph_path(r.repo_key, r.pinned_sha).exists()]
    task_commits = [(r.repo_key, r.base_commit) for r in
                    tasks.drop_duplicates(["repo_key", "base_commit"]).itertuples()
                    if graph_path(r.repo_key, r.base_commit).exists()]
    with ProcessPoolExecutor(workers) as ex:
        t1 = pd.DataFrame(list(ex.map(for_graph, pinned)))
        tc = pd.DataFrame(list(ex.map(for_graph, task_commits, chunksize=4)))
    missing = sorted(set(repos.repo_key) - set(t1.repo_key))
    t1.to_csv(ROOT / "results" / "table1.csv", index=False)
    (ROOT / "results" / "step4").mkdir(parents=True, exist_ok=True)
    tc.drop(columns="sha").groupby("repo_key").median().to_csv(
        ROOT / "results" / "step4" / "table1_task_commits_median.csv")
    print(len(t1), "repos in Table 1; missing:", missing)


if __name__ == "__main__":
    main()
