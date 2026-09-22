"""Step 6 driver: run every method on every task, 5 tie-breaking runs each (D21).

Lists are stored as indices into the commit's node list, one gzip JSON per task:
data/lists/<condition>/<repo>/<task hash>.json.gz
Runtime and list length are recorded per (method, run). Failures are recorded, never dropped.
Also used for Step 9 with --condition wrong1 / wrong2 / wrongrand (D26).
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import random
import time
import traceback
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np

from depgraphs import progress
from depgraphs.datasets import ROOT
from depgraphs.graphs import load_graph
from depgraphs.methods import METHODS, Ctx

RUNS = 5
LISTS = ROOT / "data" / "lists"
FEAT = ROOT / "data" / "features"


def task_hash(task_id: str) -> str:
    return hashlib.sha1(task_id.encode()).hexdigest()[:16]


def rng_for(task_id: str, i: int) -> random.Random:
    return random.Random(int(hashlib.sha256(f"20260922{i}{task_id}".encode()).hexdigest(), 16))


def load_blob_features(repo_key: str) -> dict:
    out = {}
    with gzip.open(FEAT / repo_key.replace("/", "__") / "blobs.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            out[r.pop("blob")] = r
    return out


def load_embeddings(repo_key: str):
    p = ROOT / "data" / "embeddings" / f"{repo_key.replace('/', '__')}.npz"
    if not p.exists():
        return None
    z = np.load(p)
    return {b: v.astype(np.float32) for b, v in zip(z["blobs"].tolist(), z["vecs"])}


def build_ctx(repo_key, sha, blobs, emb, cochange) -> Ctx:
    g = load_graph(repo_key, sha)
    mapping = json.loads((FEAT / repo_key.replace("/", "__") / "commits" / f"{sha}.json").read_text())
    feats = {p: blobs[b] for p, b in mapping.items() if b in blobs}
    embed = None
    if emb is not None:
        embed = {p: emb[b].tolist() for p, b in mapping.items() if b in emb}
    return Ctx(g["nodes"], [tuple(e) for e in g["edges"]], feats, cochange, embed)


def wrong_seed(task: dict, ctx: Ctx, condition: str) -> str | None:
    """D26: file at undirected distance exactly d, or any other file; None if none exists."""
    r = random.Random(int(hashlib.sha256(f"20260922{task['task_id']}".encode()).hexdigest(), 16))
    s = task["seed"]
    if condition == "wrongrand":
        pool = sorted(set(ctx.nodes) - {s})
    else:
        import networkx as nx
        d = {"wrong1": 1, "wrong2": 2}[condition]
        lv = nx.single_source_shortest_path_length(ctx.U, s, cutoff=d)
        pool = sorted(n for n, k in lv.items() if k == d)
    return r.choice(pool) if pool else None


def repo_job(repo_key: str, tasks: list[dict], condition: str, methods: list[str]) -> dict:
    blobs = load_blob_features(repo_key)
    emb = load_embeddings(repo_key) if "embedding" in methods else None
    outdir = LISTS / condition / repo_key.replace("/", "__")
    outdir.mkdir(parents=True, exist_ok=True)
    stats = {"tasks": 0, "method_failures": 0, "no_seed": 0}
    by_commit = defaultdict(list)
    for t in tasks:
        by_commit[t["base_commit"]].append(t)
    for sha, ts in by_commit.items():
        todo = [t for t in ts if not (outdir / f"{task_hash(t['task_id'])}.json.gz").exists()]
        if not todo:
            continue
        cochange = {}
        for t in todo:
            p = ROOT / "data" / "cochange" / f"{t['instance_id']}.json"
            if p.exists():
                cochange.update(json.loads(p.read_text()).get("scores", {}))
        ctx = build_ctx(repo_key, sha, blobs, emb, cochange)
        index = {p: i for i, p in enumerate(ctx.nodes)}
        for t in todo:
            seed = t["seed"] if condition == "true" else wrong_seed(t, ctx, condition)
            rec = {"task_id": t["task_id"], "condition": condition, "seed_used": seed,
                   "nodes": ctx.nodes, "runs": [], "failures": {}}
            if seed is None:
                stats["no_seed"] += 1
            else:
                for i in range(RUNS):
                    run = {}
                    for name in methods:
                        t0 = time.perf_counter()
                        try:
                            lst = METHODS[name](ctx, seed, rng_for(t["task_id"], i))
                            run[name] = {"list": [index[p] for p in lst if p != t["seed"]],
                                         "seconds": round(time.perf_counter() - t0, 5)}
                        except Exception:
                            rec["failures"].setdefault(name, traceback.format_exc()[-600:])
                            stats["method_failures"] += 1
                    rec["runs"].append(run)
            with gzip.open(outdir / f"{task_hash(t['task_id'])}.json.gz", "wt", encoding="utf-8") as f:
                json.dump(rec, f)
            stats["tasks"] += 1
    return stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--condition", default="true", choices=["true", "wrong1", "wrong2", "wrongrand"])
    ap.add_argument("--repos", nargs="*")
    ap.add_argument("--methods", nargs="*", default=sorted(METHODS))
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    tasks = [json.loads(l) for l in open(ROOT / "data" / "tasks.jsonl", encoding="utf-8")]
    by_repo = defaultdict(list)
    for t in tasks:
        if not a.repos or t["repo_key"] in a.repos:
            by_repo[t["repo_key"]].append(t)
    total = defaultdict(int)
    done = 0
    with ProcessPoolExecutor(a.workers) as ex:
        futs = {ex.submit(repo_job, rk, ts, a.condition, a.methods): rk for rk, ts in by_repo.items()}
        for f in as_completed(futs):
            done += 1
            try:
                for k, v in f.result().items():
                    total[k] += v
            except Exception:
                total["repo_failures"] += 1
                print("REPO FAILED", futs[f], traceback.format_exc()[-800:], flush=True)
            progress.update(f"methods_{a.condition}", repos_done=done, repos_total=len(by_repo), **total)
    print(dict(total))


if __name__ == "__main__":
    main()
