"""Step 7: score every stored list against every answer-key source (paper/metrics.md).

Writes results/scores/<condition>.parquet: one row per (task, method, key source), metrics
averaged over the 5 tie-breaking runs (plus the spread of AUC across runs).
The `oracle` cheat ceiling is built here, per key source, because it needs the key.
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed

import networkx as nx
import numpy as np
import pandas as pd

from depgraphs.datasets import ROOT
from depgraphs.graphs import load_graph
from depgraphs.run_methods import FEAT, LISTS, load_blob_features, rng_for, task_hash

LINES_GRID = [250, 500, 1000, 2000, 4000, 8000, 16000, 32000]
FILES_GRID = [1, 2, 4, 8, 16, 32, 64, 128]
TOKENS_GRID = [10 * b for b in LINES_GRID]


def coverage_auc(costs: list[float], hits: list[bool], n_key: int, grid) -> float:
    """Mean over the grid of the share of the key within budget b (prefix whose cumulative
    cost <= b)."""
    if n_key == 0:
        return float("nan")
    cum = np.cumsum(costs) if costs else np.array([])
    hit_cum = np.cumsum(hits) if hits else np.array([])
    vals = []
    for b in grid:
        k = int(np.searchsorted(cum, b, side="right"))     # items with cum <= b
        vals.append((hit_cum[k - 1] if k else 0) / n_key)
    return float(np.mean(vals))


def rank_metrics(lst: list[str], key: set[str], n_candidates: int) -> dict:
    pos = {p: i + 1 for i, p in enumerate(lst)}
    ranks = sorted(pos[p] for p in key if p in pos)
    n, K = len(lst), len(key)
    out = {f"acc{k}": float(all(p in pos and pos[p] <= k for p in key)) for k in (1, 3, 5, 10)}
    out.update({f"top{k}": float(bool(ranks) and ranks[0] <= k) for k in (1, 5, 10)})
    out["mrr"] = 1 / ranks[0] if ranks else 0.0
    out["ap"] = sum((i + 1) / r for i, r in enumerate(ranks)) / K if K else float("nan")
    dcg = sum(1 / math.log2(r + 1) for r in ranks if r <= 10)
    idcg = sum(1 / math.log2(i + 2) for i in range(min(K, 10)))
    out["ndcg10"] = dcg / idcg if idcg else float("nan")
    out["empty"] = float(n == 0)
    out["first_key_rank"] = ranks[0] if ranks else float("nan")
    if n:
        m = min(10, n)
        h = sum(1 for r in ranks if r <= m)
        e = m * K / n_candidates if n_candidates else 0
        out["odds_ratio"] = ((h + 0.5) / (m - h + 0.5)) / ((e + 0.5) / (m - e + 0.5))
    else:
        out["odds_ratio"] = float("nan")
    return out


def topo_check(lst: list[str], g: nx.DiGraph, member: dict) -> tuple[float, float]:
    pos = {p: i for i, p in enumerate(lst)}
    pairs = bad = 0
    for u, v in g.edges:
        if u in pos and v in pos and member[u] != member[v]:
            pairs += 1
            bad += pos[v] > pos[u]         # dependency listed after its importer
    if not pairs:
        return float("nan"), float("nan")
    return float(bad == 0), bad / pairs


def key_sources(task: dict) -> dict[str, set]:
    k = {s: set(v) for s, v in task["keys"].items()}
    out = dict(k)
    out["union_static"] = k.get("co_edited", set()) | k.get("symbol", set())
    if "execution_B" in k:
        out["union"] = out["union_static"] | k["execution_B"]
    else:
        out["union"] = out["union_static"]
    return out


def score_repo(repo_key: str, tasks: list[dict], condition: str) -> list[dict]:
    blobs = load_blob_features(repo_key)
    rows = []
    cache = {}
    for t in tasks:
        p = LISTS / condition / repo_key.replace("/", "__") / f"{task_hash(t['task_id'])}.json.gz"
        if not p.exists():
            rows.append({"task_id": t["task_id"], "method": "*", "source": "*", "missing_lists": 1})
            continue
        with gzip.open(p, "rt", encoding="utf-8") as f:
            rec = json.load(f)
        nodes = rec["nodes"]
        sha = t["base_commit"]
        if sha not in cache:
            mapping = json.loads((FEAT / repo_key.replace("/", "__") / "commits" / f"{sha}.json").read_text())
            gd = load_graph(repo_key, sha)
            g = nx.DiGraph()
            g.add_nodes_from(gd["nodes"])
            g.add_edges_from(map(tuple, gd["edges"]))
            member = {f: i for i, c in enumerate(nx.strongly_connected_components(g)) for f in c}
            cache = {sha: (mapping, g, member)}
        mapping, g, member = cache[sha]
        lines = {p_: blobs.get(mapping.get(p_), {}).get("lines", 0) for p_ in nodes}
        tokens = {p_: blobs.get(mapping.get(p_), {}).get("tokens", 0) for p_ in nodes}
        n_cand = len(nodes) - 1
        sources = key_sources(t)
        if not rec["runs"]:
            continue
        methods = list(rec["runs"][0])
        for src, key in sources.items():
            if not key:
                rows.append({"task_id": t["task_id"], "method": "*", "source": src, "empty_key": 1})
                continue
            per_method = {m: [] for m in methods + ["oracle"]}
            for i, run in enumerate(rec["runs"]):
                items = {m: [nodes[j] for j in run[m]["list"]] for m in methods if m in run}
                orng = rng_for(t["task_id"], i)
                tb = {p_: orng.random() for p_ in sorted(key)}
                items["oracle"] = sorted(key, key=lambda p_: (lines[p_], tb[p_]))
                for m, lst in items.items():
                    hits = [p_ in key for p_ in lst]
                    r = {"auc_lines": coverage_auc([lines[p_] for p_ in lst], hits, len(key), LINES_GRID),
                         "auc_files": coverage_auc([1] * len(lst), hits, len(key), FILES_GRID),
                         "auc_tokens": coverage_auc([tokens[p_] for p_ in lst], hits, len(key), TOKENS_GRID),
                         "list_len": len(lst), "list_lines": sum(lines[p_] for p_ in lst),
                         "seconds": run[m]["seconds"] if m in run else float("nan")}
                    r.update(rank_metrics(lst, key, n_cand))
                    r["valid_topo"], r["inversions"] = topo_check(lst, g, member)
                    per_method[m].append(r)
            for m, rs in per_method.items():
                if not rs:
                    continue
                df = pd.DataFrame(rs)
                row = df.mean(numeric_only=True).to_dict()
                row["auc_lines_run_sd"] = float(df.auc_lines.std(ddof=0))
                row.update({"task_id": t["task_id"], "instance_id": t["instance_id"],
                            "repo_key": repo_key, "file_group": t["file_group"],
                            "dataset": t["dataset"], "method": m, "source": src,
                            "key_size": len(key), "condition": condition,
                            "seed_used": rec["seed_used"]})
                rows.append(row)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--condition", default="true")
    ap.add_argument("--repos", nargs="*")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--out")
    a = ap.parse_args()
    tasks = [json.loads(l) for l in open(ROOT / "data" / "tasks.jsonl", encoding="utf-8")]
    by_repo = defaultdict(list)
    for t in tasks:
        if not a.repos or t["repo_key"] in a.repos:
            by_repo[t["repo_key"]].append(t)
    rows = []
    with ProcessPoolExecutor(a.workers) as ex:
        futs = {ex.submit(score_repo, rk, ts, a.condition): rk for rk, ts in by_repo.items()}
        for f in as_completed(futs):
            rows += f.result()
    out = a.out or str(ROOT / "results" / "scores" / f"{a.condition}.parquet")
    from pathlib import Path
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(out, index=False)
    print(len(rows), "rows ->", out)


if __name__ == "__main__":
    main()
