"""Mean coverage–cost curve per method (union key, lines), PR-weighted, for the report figure.

Writes results/analysis/curves_union.csv: method, budget, mean coverage.
"""
from __future__ import annotations

import gzip
import json
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

from depgraphs.datasets import ROOT
from depgraphs.run_methods import FEAT, LISTS, load_blob_features, rng_for, task_hash
from depgraphs.scoring import key_sources

BUDGETS = [125, 250, 500, 1000, 2000, 4000, 8000, 16000, 32000, 64000]


def repo_curves(repo_key, tasks):
    blobs = load_blob_features(repo_key)
    acc = defaultdict(lambda: defaultdict(list))     # method -> instance -> [curve per task]
    for t in tasks:
        p = LISTS / "true" / repo_key.replace("/", "__") / f"{task_hash(t['task_id'])}.json.gz"
        if not p.exists():
            continue
        rec = json.load(gzip.open(p, "rt", encoding="utf-8"))
        key = key_sources(t)["union"]
        if not key or not rec["runs"]:
            continue
        mapping = json.loads((FEAT / repo_key.replace("/", "__") / "commits" / f"{t['base_commit']}.json").read_text())
        nodes = rec["nodes"]
        lines = {p_: blobs.get(mapping.get(p_), {}).get("lines", 0) for p_ in nodes}
        runs = []
        for i, run in enumerate(rec["runs"]):
            items = {m: [nodes[j] for j in v["list"]] for m, v in run.items()}
            orng = rng_for(t["task_id"], i)
            tb = {p_: orng.random() for p_ in sorted(key)}
            items["oracle"] = sorted(key, key=lambda p_: (lines[p_], tb[p_]))
            runs.append(items)
        for m in runs[0]:
            cs = []
            for items in runs:
                lst = items.get(m, [])
                cum = np.cumsum([lines[p_] for p_ in lst]) if lst else np.array([])
                hit = np.cumsum([p_ in key for p_ in lst]) if lst else np.array([])
                c = []
                for b in BUDGETS:
                    k = int(np.searchsorted(cum, b, side="right"))
                    c.append((hit[k - 1] if k else 0) / len(key))
                cs.append(c)
            acc[m][t["instance_id"]].append(np.mean(cs, axis=0))
    return {m: {iid: np.mean(v, axis=0).tolist() for iid, v in d.items()} for m, d in acc.items()}


def main():
    tasks = [json.loads(l) for l in open(ROOT / "data" / "tasks.jsonl", encoding="utf-8")]
    by = defaultdict(list)
    for t in tasks:
        by[t["repo_key"]].append(t)
    allc = defaultdict(list)
    with ProcessPoolExecutor(16) as ex:
        for res in ex.map(repo_curves, by.keys(), by.values()):
            for m, d in res.items():
                allc[m] += list(d.values())
    rows = [{"method": m, "budget": b, "coverage": float(np.mean([c[i] for c in cs]))}
            for m, cs in allc.items() for i, b in enumerate(BUDGETS)]
    (ROOT / "results" / "analysis").mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(ROOT / "results" / "analysis" / "curves_union.csv", index=False)
    print("curves written")


if __name__ == "__main__":
    main()
