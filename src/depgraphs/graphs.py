"""Step 3: build one import graph per task base commit, plus one at each repo's pinned SHA.

Builder and rules as recorded in D9/D17/D18. Each graph is cached by commit and written to
data/graphs/<repo>/<sha>.json.gz with nodes, edges, import loops (SCCs), per-file line
counts, construct counts, unresolved imports and parse/read failures.

Writes results/step3/graph_summary.csv (one row per graph) and
results/step3/unresolved_by_repo.csv. Failures go to logs/graph_failures.csv.
"""
from __future__ import annotations

import gzip
import json
import subprocess
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

from depgraphs import progress
from depgraphs.candidates import CLONES
from depgraphs.datasets import ROOT
from depgraphs.graph.ast_builder import Options, build
from depgraphs.graph.cycles import condense, to_nx

GRAPHS = ROOT / "data" / "graphs"
OUT = ROOT / "results" / "step3"
OPTS = Options(include_tests=False)   # D9 + D18


def _git(args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                          timeout=1800, check=True)


def graph_path(repo_key: str, sha: str) -> Path:
    return GRAPHS / repo_key.replace("/", "__") / f"{sha}.json.gz"


def load_graph(repo_key: str, sha: str) -> dict:
    with gzip.open(graph_path(repo_key, sha), "rt", encoding="utf-8") as f:
        return json.load(f)


def _line_count(p: Path) -> int:
    try:
        with open(p, "rb") as f:
            return sum(1 for _ in f)
    except OSError:
        return -1


def build_one(repo_dir: Path, repo_key: str, sha: str) -> dict:
    t0 = time.time()
    g = build(repo_dir, OPTS)
    secs = time.time() - t0
    dag, clumps, member = condense(to_nx(g.nodes, g.edges))
    tops = {m.split(".")[0] for m in g.module_of.values()}
    internal = sum(1 for r in g.records if r.level > 0 or r.module.split(".")[0] in tops)
    data = {
        "repo_key": repo_key, "sha": sha, "options": OPTS.__dict__,
        "nodes": g.nodes,
        "edges": [[a, b] for (a, b) in sorted(g.edges)],
        "clumps": [c for c in clumps.values() if len(c) > 1],
        "lines": {f: _line_count(repo_dir / f) for f in g.nodes},
        "counts": dict(g.counts),
        "unresolved": g.unresolved[:500],
        "n_unresolved": len(g.unresolved),
        "internal_statements": internal,
        "parse_failures": g.parse_failures,
        "build_seconds": round(secs, 3),
    }
    p = graph_path(repo_key, sha)
    p.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(p, "wt", encoding="utf-8") as f:
        json.dump(data, f)
    n = len(g.nodes)
    in_loops = sum(len(c) for c in data["clumps"])
    return {"repo_key": repo_key, "sha": sha, "nodes": n, "edges": len(g.edges),
            "clumps": len(data["clumps"]), "files_in_loops": in_loops,
            "import_statements": len(g.records),
            "internal_statements": internal,
            "unresolved_internal": g.counts.get("unresolved_internal", 0),
            "parse_failures": g.counts.get("parse_failure", 0),
            "read_failures": g.counts.get("read_failure", 0),
            "skipped_non_identifier": g.counts.get("skipped_non_identifier_path", 0),
            "skipped_duplicate": g.counts.get("skipped_duplicate_module_name", 0),
            "build_seconds": round(secs, 3)}


def repo_job(repo_key: str, shas: list[str]) -> tuple[list[dict], list[dict]]:
    """All commits of one repo, sequentially in its own working copy."""
    d = CLONES / repo_key.replace("/", "__")
    rows, fails = [], []
    todo = [s for s in shas if not graph_path(repo_key, s).exists()]
    for i in range(0, len(todo), 20):          # fetch in batches of 20 commits
        try:
            _git(["fetch", "-q", "--depth", "1", "origin", *todo[i:i + 20]], d)
        except subprocess.CalledProcessError as e:
            for s in todo[i:i + 20]:
                try:
                    _git(["fetch", "-q", "--depth", "1", "origin", s], d)
                except subprocess.CalledProcessError as e2:
                    fails.append({"repo_key": repo_key, "sha": s, "stage": "fetch",
                                  "error": e2.stderr.strip()[-300:]})
    for s in shas:
        p = graph_path(repo_key, s)
        if p.exists():
            continue
        if any(f["sha"] == s for f in fails):
            continue
        try:
            _git(["-c", "advice.detachedHead=false", "checkout", "-q", "-f", s], d)
            _git(["clean", "-q", "-fdx"], d)
            rows.append(build_one(d, repo_key, s))
        except Exception as e:
            fails.append({"repo_key": repo_key, "sha": s, "stage": "build",
                          "error": f"{type(e).__name__}: {getattr(e, 'stderr', '') or e}"[-300:]})
    return rows, fails


def summary_row(repo_key, sha) -> dict:
    g = load_graph(repo_key, sha)
    return {"repo_key": repo_key, "sha": sha, "nodes": len(g["nodes"]), "edges": len(g["edges"]),
            "clumps": len(g["clumps"]), "files_in_loops": sum(map(len, g["clumps"])),
            "unresolved_internal": g["counts"].get("unresolved_internal", 0),
            "internal_statements": g["internal_statements"],
            "parse_failures": g["counts"].get("parse_failure", 0),
            "read_failures": g["counts"].get("read_failure", 0),
            "skipped_non_identifier": g["counts"].get("skipped_non_identifier_path", 0),
            "skipped_duplicate": g["counts"].get("skipped_duplicate_module_name", 0),
            "build_seconds": g["build_seconds"]}


def main(workers: int = 6):
    tasks = pd.read_csv(ROOT / "data" / "sample_tasks.csv")
    repos = pd.read_csv(ROOT / "data" / "repos.csv")
    jobs = {}
    for rk, d in tasks.groupby("repo_key"):
        pinned = repos.set_index("repo_key").loc[rk, "pinned_sha"]
        jobs[rk] = list(dict.fromkeys([pinned, *d.base_commit]))
    fails = []
    done = 0
    with ProcessPoolExecutor(workers) as ex:
        futs = {ex.submit(repo_job, rk, shas): rk for rk, shas in jobs.items()}
        for f in as_completed(futs):
            done += 1
            try:
                _, fl = f.result()
                fails += fl
            except Exception as e:
                fails.append({"repo_key": futs[f], "sha": "*", "stage": "job", "error": str(e)[-300:]})
            progress.update("graphs", repos_done=done, repos_total=len(jobs), failures=len(fails))
    pd.DataFrame(fails, columns=["repo_key", "sha", "stage", "error"]).to_csv(
        ROOT / "logs" / "graph_failures.csv", index=False)
    rows = [summary_row(rk, s) for rk, shas in jobs.items() for s in shas
            if graph_path(rk, s).exists()]
    OUT.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    df["is_pinned"] = [s == repos.set_index("repo_key").loc[rk, "pinned_sha"]
                       for rk, s in zip(df.repo_key, df.sha)]
    df.to_csv(OUT / "graph_summary.csv", index=False)
    per = df.groupby("repo_key").agg(graphs=("sha", "size"),
                                     unresolved=("unresolved_internal", "sum"),
                                     internal_statements=("internal_statements", "sum"),
                                     parse_failures=("parse_failures", "sum"),
                                     median_build_s=("build_seconds", "median"))
    per["unresolved_share"] = (per.unresolved / per.internal_statements.clip(lower=1)).round(4)
    per.to_csv(OUT / "unresolved_by_repo.csv")
    print(len(df), "graphs;", len(fails), "failures")


if __name__ == "__main__":
    main()
