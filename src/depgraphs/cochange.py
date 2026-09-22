"""Co-change scores from git history strictly before each task's base commit (Step 6, D22).

Per repo: one bare blobless clone of the full history. Per PR base commit: walk the
first-parent history starting at the base commit's parent (never the base commit itself or
anything after it — leakage guard), keep commits touching 1–50 non-test `.py` files, and for
each seed: score(x) = Σ over those commits containing seed and x of 1/(n − 1), n = files in
the commit.

Writes data/cochange/<instance_id>.json : {seed: {file: score}} plus the number of commits
used and the newest commit date seen (a leakage check: it must be before the base commit).
"""
from __future__ import annotations

import json
import subprocess
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed

import pandas as pd

from depgraphs import progress
from depgraphs.datasets import ROOT
from depgraphs.patches import is_py, is_test_path

HIST = ROOT / "data" / "history"
OUT = ROOT / "data" / "cochange"
MAX_FILES = 50


def _git(args, cwd=None, timeout=7200):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                          timeout=timeout, errors="replace")


def commit_filesets(repo_dir, base: str):
    """[(sha, unix_time, [files])] for first-parent history strictly before `base`."""
    r = _git(["log", "--first-parent", "--no-renames", "--name-only", "--format=@%H %ct",
              f"{base}^"], repo_dir)
    if r.returncode != 0:
        return None, r.stderr[-300:]
    out, cur = [], None
    for line in r.stdout.splitlines():
        if line.startswith("@"):
            sha, ts = line[1:].split()
            cur = (sha, int(ts), [])
            out.append(cur)
        elif line and cur is not None:
            cur[2].append(line)
    return out, None


def score(filesets, seeds):
    res = {s: Counter() for s in seeds}
    used = 0
    for _, _, files in filesets:
        src = [f for f in files if is_py(f) and not is_test_path(f)]
        if not (2 <= len(src) <= MAX_FILES):
            continue
        used += 1
        w = 1 / (len(src) - 1)
        present = set(src)
        for s in seeds:
            if s in present:
                for f in present - {s}:
                    res[s][f] += w
    return {s: dict(c) for s, c in res.items()}, used


def repo_job(repo_key: str, url: str, prs: list[dict]) -> int:
    d = HIST / (repo_key.replace("/", "__") + ".git")
    fails = 0
    if not d.exists():
        r = _git(["clone", "-q", "--bare", "--filter=blob:none", url, str(d)])
        if r.returncode != 0:
            for pr in prs:
                (OUT / f"{pr['instance_id']}.json").write_text(json.dumps(
                    {"error": "clone: " + r.stderr[-300:]}))
            return len(prs)
    for pr in prs:
        dest = OUT / f"{pr['instance_id']}.json"
        if dest.exists():
            continue
        fs, err = commit_filesets(d, pr["base_commit"])
        if fs is None:   # base commit not in the default history: fetch it explicitly
            _git(["fetch", "-q", "--filter=blob:none", "origin", pr["base_commit"]], d)
            fs, err = commit_filesets(d, pr["base_commit"])
        if fs is None:
            dest.write_text(json.dumps({"error": err}))
            fails += 1
            continue
        base_ts = _git(["show", "-s", "--format=%ct", pr["base_commit"]], d).stdout.strip()
        scores, used = score(fs, pr["seeds"])
        dest.write_text(json.dumps({
            "scores": scores, "commits_seen": len(fs), "commits_used": used,
            "newest_history_ts": max((t for _, t, _ in fs), default=None),
            "base_ts": int(base_ts) if base_ts else None}))
    return fails


def main(workers: int = 10):
    tasks = [json.loads(l) for l in open(ROOT / "data" / "tasks.jsonl", encoding="utf-8")]
    seeds = defaultdict(set)
    meta = {}
    for t in tasks:
        seeds[t["instance_id"]].add(t["seed"])
        meta[t["instance_id"]] = (t["repo_key"], t["base_commit"])
    repos = pd.read_csv(ROOT / "data" / "repos.csv").set_index("repo_key")
    by_repo = defaultdict(list)
    for iid, (rk, base) in meta.items():
        by_repo[rk].append({"instance_id": iid, "base_commit": base, "seeds": sorted(seeds[iid])})
    HIST.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    done = fails = 0
    with ProcessPoolExecutor(workers) as ex:
        futs = {ex.submit(repo_job, rk, repos.loc[rk, "url"] + ".git", prs): rk
                for rk, prs in by_repo.items()}
        for f in as_completed(futs):
            done += 1
            try:
                fails += f.result()
            except Exception as e:
                fails += 1
                print("FAILED", futs[f], repr(e)[:300], flush=True)
            progress.update("cochange", repos_done=done, repos_total=len(by_repo), failures=fails)
    print("cochange done; failures:", fails)


if __name__ == "__main__":
    main()
