"""Structure vs. words: reading orders from the import graph, from the issue text, or both.

Every method returns an ordering of the graph nodes of a repository (seed excluded) and is
scored with the frozen coverage-cost metric: cumulative lines against budgets
250..32000, AUC = mean coverage over the eight doublings.

Families
  structure  seed-conditioned walks over the import graph (bfs_und, hops_lines, ppr_und)
  global     query-independent repository priors (pagerank, indegree) - no seed, no issue
  lexical    BM25 over identifier bags, queried by the seed file or by the issue text
  fusion     reciprocal-rank fusion of a structural and a lexical ordering

Writes results/study2/rows.parquet   per task x method x key source
       results/study2/curves.parquet per task x method x key source x budget
       results/study2/top.jsonl.gz   top-100 ordering per task x method (overlap analysis)
"""
from __future__ import annotations

import collections
import gzip
import json
import math
import random
import re
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed

import networkx as nx
import numpy as np
import pandas as pd

from depgraphs.lexfeat import ROOT, split_ident

OUT = ROOT / "results" / "study2"
BUDGETS = [250, 500, 1000, 2000, 4000, 8000, 16000, 32000]
RUNS = 3
TOPN = 100
RRF_K = 60


# ----------------------------------------------------------------- loading

def load_repo(repo_dir: str):
    base = ROOT / "data" / "lexfeat" / repo_dir
    commits = json.loads((base / "commits.json").read_text())
    blobs = {}
    with gzip.open(base / "blobs.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            blobs[r["blob"]] = r["bag"]
    return commits, blobs


def load_graph(repo_dir: str, sha: str):
    with gzip.open(ROOT / "data" / "graphs" / repo_dir / (sha + ".json.gz"), "rt",
                   encoding="utf-8") as f:
        g = json.load(f)
    return g["nodes"], g["edges"], g["lines"]


_PATHSPLIT = re.compile(r"[^A-Za-z0-9]+")


def path_bag(path: str) -> dict[str, int]:
    bag = collections.Counter()
    for part in _PATHSPLIT.split(path):
        bag.update(split_ident(part))
    return dict(bag)


# ----------------------------------------------------------------- scoring helpers

def by_score(scores: dict, rng: random.Random) -> list[str]:
    tb = {k: rng.random() for k in sorted(scores)}
    return sorted(scores, key=lambda k: (-scores[k], tb[k]))


def bm25(query: dict[str, int], docs: dict[str, dict], k1=1.5, b=0.75) -> dict[str, float]:
    """Same parameters as the frozen bm25 method; only the query changes."""
    if not docs or not query:
        return {}
    N = len(docs)
    lens = {p: sum(d.values()) for p, d in docs.items()}
    avg = (sum(lens.values()) / N) or 1.0
    df = collections.Counter(t for d in docs.values() for t in d)
    scores = {}
    for p, d in docs.items():
        sc = 0.0
        for t in query:
            tf = d.get(t, 0)
            if tf:
                idf = math.log(1 + (N - df[t] + 0.5) / (df[t] + 0.5))
                sc += idf * tf * (k1 + 1) / (tf + k1 * (1 - b + b * lens[p] / avg))
        scores[p] = sc
    return scores


def rrf(*orders):
    sc = collections.defaultdict(float)
    for o in orders:
        for i, p in enumerate(o):
            sc[p] += 1.0 / (RRF_K + i + 1)
    return dict(sc)


# ----------------------------------------------------------------- the methods

def orderings(nodes, edges, lines, seed, bags, issue_bag, rng):
    others = [p for p in nodes if p != seed]
    if not others:
        return {}
    G = nx.DiGraph()
    G.add_nodes_from(nodes)
    G.add_edges_from(e for e in edges if e[0] != e[1])
    U = G.to_undirected(as_view=False)
    cost = {p: max(lines.get(p, 0), 1) for p in nodes}

    out = {}

    # --- structure, seed-conditioned
    dist = nx.single_source_shortest_path_length(U, seed) if seed in U else {}
    far = len(nodes) + 1
    out["bfs_und"] = by_score({p: -dist.get(p, far) for p in others}, rng)
    out["hops_lines"] = sorted(others, key=lambda p: (dist.get(p, far), cost[p], p))
    if G.number_of_edges() and seed in U:
        ppr = nx.pagerank(U, alpha=0.85, personalization={seed: 1.0})
    else:
        ppr = {p: 0.0 for p in nodes}
    out["ppr_und"] = by_score({p: ppr.get(p, 0.0) for p in others}, rng)
    out["ppr_und_pl"] = by_score({p: ppr.get(p, 0.0) / cost[p] for p in others}, rng)

    # --- global priors: no seed, no issue
    pr = nx.pagerank(G, alpha=0.85) if G.number_of_edges() else {p: 1.0 for p in nodes}
    out["pagerank"] = by_score({p: pr.get(p, 0.0) for p in others}, rng)
    indeg = dict(G.in_degree())
    out["indegree"] = by_score({p: indeg.get(p, 0) for p in others}, rng)

    # --- lexical
    docs = {p: bags.get(p, {}) for p in others}
    out["bm25_seed"] = by_score(bm25(bags.get(seed, {}), docs), rng) if bags.get(seed) else []
    issue_scores = bm25(issue_bag, docs)
    out["bm25_issue"] = by_score(issue_scores, rng) if issue_scores else []
    out["bm25_issue_pl"] = (by_score({p: s / cost[p] for p, s in issue_scores.items()}, rng)
                            if issue_scores else [])
    pdocs = {p: path_bag(p) for p in others}
    out["path_issue"] = by_score(bm25(issue_bag, pdocs), rng) if issue_bag else []
    # control: the same path matching, queried by the seed path instead of the issue, so
    # any advantage of path_issue that is really just "files near this one in the tree"
    # shows up here too.
    out["path_seed"] = by_score(bm25(path_bag(seed), pdocs), rng)

    # --- fusion
    if out["bm25_issue"]:
        out["rrf_ppr_issue"] = by_score(rrf(out["ppr_und"], out["bm25_issue"]), rng)
        out["rrf_ppr_issue_path"] = by_score(
            rrf(out["ppr_und"], out["bm25_issue"], out["path_issue"]), rng)
        out["rrf_hops_path"] = by_score(rrf(out["hops_lines"], out["path_issue"]), rng)
        out["rrf_hops_issue_path"] = by_score(
            rrf(out["hops_lines"], out["bm25_issue"], out["path_issue"]), rng)
        out["rrf_pprpl_issue_path"] = by_score(
            rrf(out["ppr_und_pl"], out["bm25_issue"], out["path_issue"]), rng)
    else:
        out["rrf_ppr_issue"] = out["ppr_und"]
        out["rrf_ppr_issue_path"] = out["ppr_und"]
        out["rrf_hops_path"] = out["hops_lines"]
        out["rrf_hops_issue_path"] = out["hops_lines"]
        out["rrf_pprpl_issue_path"] = out["ppr_und_pl"]

    # --- references
    sdir = seed.rsplit("/", 1)[0] if "/" in seed else ""
    out["same_dir"] = by_score(
        {p: 1.0 if p.rsplit("/", 1)[0] == sdir else 0.0 for p in others}, rng)
    shuffled = sorted(others)
    rng.shuffle(shuffled)
    out["random"] = shuffled
    return out


METHODS = ["bfs_und", "hops_lines", "ppr_und", "ppr_und_pl", "pagerank", "indegree",
           "bm25_seed", "path_seed", "bm25_issue", "bm25_issue_pl", "path_issue",
           "rrf_ppr_issue", "rrf_ppr_issue_path", "rrf_hops_path",
           "rrf_hops_issue_path", "rrf_pprpl_issue_path", "same_dir", "random"]
STRUCTURE = ["bfs_und", "hops_lines", "ppr_und", "ppr_und_pl"]
GLOBAL = ["pagerank", "indegree"]
LEXICAL = ["bm25_seed", "path_seed", "bm25_issue", "bm25_issue_pl", "path_issue"]
FUSION = ["rrf_ppr_issue", "rrf_ppr_issue_path", "rrf_hops_path",
          "rrf_hops_issue_path", "rrf_pprpl_issue_path"]


def coverage_curve(order, key, cost):
    if not order:
        return [0.0] * len(BUDGETS)
    cum = np.cumsum([cost[p] for p in order])
    hit = np.cumsum([1 if p in key else 0 for p in order])
    out = []
    for b in BUDGETS:
        k = int(np.searchsorted(cum, b, side="right"))
        out.append(float(hit[k - 1]) / len(key) if k else 0.0)
    return out


def lines_to_reach(order, key, cost, fracs=(0.5, 1.0)):
    """Lines that must be read before the ordering has covered a fraction of the key.

    Reported instead of coverage at a fixed budget because it is the number a context
    budget is actually spent against. NaN when the ordering never gets there.
    """
    out = [float("nan")] * len(fracs)
    if not order:
        return out
    need = [int(np.ceil(f * len(key))) for f in fracs]
    run = 0
    found = 0
    for p in order:
        run += cost[p]
        if p in key:
            found += 1
            for i, n in enumerate(need):
                if found >= n and np.isnan(out[i]):
                    out[i] = float(run)
        if all(not np.isnan(v) for v in out):
            break
    return out


# ----------------------------------------------------------------- per repo

def run_repo(repo_key: str, tasks: list, issues: dict):
    repo_dir = repo_key.replace("/", "__")
    try:
        commits, blobs = load_repo(repo_dir)
    except FileNotFoundError:
        return [], [], []
    rows, curves, tops = [], [], []
    for t in tasks:
        sha = t["base_commit"]
        try:
            nodes, edges, lines = load_graph(repo_dir, sha)
        except FileNotFoundError:
            continue
        seed = t["seed"]
        nodeset = set(nodes)
        if seed not in nodeset:
            continue
        k = {s: set(v) for s, v in t["keys"].items()}
        k["union_static"] = k.get("co_edited", set()) | k.get("symbol", set())
        keys = {s: (v & nodeset) - {seed} for s, v in k.items()}
        if not any(keys.values()):
            continue
        mapping = commits.get(sha, {})
        bags = {p: blobs.get(mapping.get(p, ""), {}) for p in nodes}
        issue_bag = issues.get(t["instance_id"], {})
        cost = {p: max(lines.get(p, 0), 1) for p in nodes}

        per_run = []
        for r in range(RUNS):
            rng = random.Random("%s|%d|20260923" % (t["task_id"], r))
            per_run.append(orderings(nodes, edges, lines, seed, bags, issue_bag, rng))
        if not per_run[0]:
            continue

        for src, key in keys.items():
            if not key:
                continue
            ideal = sorted(key, key=lambda p: cost[p])
            for m in METHODS + ["oracle"]:
                cs, l50, l100 = [], [], []
                for run in per_run:
                    order = ideal if m == "oracle" else run.get(m, [])
                    cs.append(coverage_curve(order, key, cost))
                    a, b = lines_to_reach(order, key, cost)
                    l50.append(a)
                    l100.append(b)
                c = np.mean(cs, axis=0)
                rows.append({"task_id": t["task_id"], "instance_id": t["instance_id"],
                             "repo_key": repo_key, "file_group": t["file_group"],
                             "method": m, "source": src, "key_size": len(key),
                             "n_nodes": len(nodes),
                             "auc": float(np.mean(c)),
                             "lines_half": float(np.nanmean(l50)) if not all(
                                 np.isnan(l50)) else float("nan"),
                             "lines_all": float(np.nanmean(l100)) if not all(
                                 np.isnan(l100)) else float("nan")})
                for i, b in enumerate(BUDGETS):
                    curves.append({"task_id": t["task_id"], "instance_id": t["instance_id"],
                                   "repo_key": repo_key, "method": m, "source": src,
                                   "budget": b, "coverage": float(c[i])})
        tops.append({"task_id": t["task_id"], "instance_id": t["instance_id"],
                     "repo_key": repo_key, "seed": seed, "n_nodes": len(nodes),
                     "keys": {s: sorted(v) for s, v in keys.items()},
                     "lists": {m: per_run[0].get(m, [])[:TOPN] for m in METHODS}})
    return rows, curves, tops


def main(workers: int = 8):
    tasks = [json.loads(l) for l in open(ROOT / "data" / "tasks.jsonl", encoding="utf-8")]
    raw = json.loads((ROOT / "data" / "issue_bags.json").read_text())
    issues = {k: v["bag"] for k, v in raw.items()}
    by = collections.defaultdict(list)
    for t in tasks:
        by[t["repo_key"]].append(t)
    OUT.mkdir(parents=True, exist_ok=True)
    rows, curves = [], []
    done = 0
    with gzip.open(OUT / "top.jsonl.gz", "wt", encoding="utf-8") as tf, \
            ProcessPoolExecutor(workers) as ex:
        futs = {ex.submit(run_repo, k, v, issues): k for k, v in by.items()}
        for f in as_completed(futs):
            r, c, tops = f.result()
            rows += r
            curves += c
            for rec in tops:
                tf.write(json.dumps(rec) + "\n")
            done += 1
            print("[%d/%d] %s tasks=%d" % (done, len(by), futs[f], len(tops)), flush=True)
    pd.DataFrame(rows).to_parquet(OUT / "rows.parquet", index=False)
    pd.DataFrame(curves).to_parquet(OUT / "curves.parquet", index=False)
    print("rows", len(rows), "curves", len(curves))


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 8)
