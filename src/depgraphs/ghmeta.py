"""Fetch GitHub repository metadata for candidates (fork flag, licence, description, archived).

Unauthenticated: 60 requests/hour, so this waits for the rate-limit reset when needed.
Set GITHUB_TOKEN to go faster. Cached per repo in data/github_meta.jsonl.
"""
from __future__ import annotations

import json
import os
import time

import pandas as pd
import requests

from depgraphs.datasets import ROOT

CACHE = ROOT / "data" / "github_meta.jsonl"
KEEP = ["full_name", "description", "fork", "archived", "stargazers_count", "created_at",
        "pushed_at", "default_branch", "language", "topics", "homepage"]


def _get(repo: str) -> dict:
    h = {"Accept": "application/vnd.github+json"}
    if os.environ.get("GITHUB_TOKEN"):
        h["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    while True:
        r = requests.get(f"https://api.github.com/repos/{repo}", headers=h, timeout=60)
        if r.status_code in (403, 429) and r.headers.get("x-ratelimit-remaining") == "0":
            wait = int(r.headers["x-ratelimit-reset"]) - time.time() + 5
            print(f"rate limited; sleeping {wait:.0f}s", flush=True)
            time.sleep(max(wait, 5))
            continue
        if r.status_code == 404:
            return {"repo_key": repo.lower(), "error": "404"}
        r.raise_for_status()
        j = r.json()
        out = {"repo_key": repo.lower(), **{k: j.get(k) for k in KEEP}}
        out["licence_spdx"] = (j.get("license") or {}).get("spdx_id")
        out["parent"] = (j.get("parent") or {}).get("full_name")
        return out


def main():
    cand = pd.read_parquet(ROOT / "results" / "step2" / "dedup_tasks.parquet")
    from depgraphs.recount import eligible
    per = cand[eligible(cand, 1)].groupby("repo_key").repo.agg(["first", "size"])
    repos = per[per["size"] >= 10]["first"].tolist()
    done = set()
    if CACHE.exists():
        done = {json.loads(line)["repo_key"] for line in CACHE.read_text().splitlines()}
    for i, repo in enumerate(r for r in repos if r.lower() not in done):
        rec = _get(repo)
        with open(CACHE, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")
        print(i, repo, flush=True)


if __name__ == "__main__":
    main()
