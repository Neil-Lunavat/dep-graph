"""Check which tasks have a prebuilt Docker image on Docker Hub (rule R1, D11).

Docker Hub stops anonymous namespace listings after 100 items, so each expected image is
checked by name (one small API call, cached, resumable). Pro images are tags of one repo,
checked the same way. No image is pulled.

Writes:
  data/dockerhub/checked.json       cache: image -> exists
  results/step2/env_availability.csv          one row per task
  results/step2/env_availability_summary.csv  one row per dataset
"""
from __future__ import annotations

import json
import time

import pandas as pd
import requests

from depgraphs.datasets import ROOT, load

CACHE = ROOT / "data" / "dockerhub"
OUT = ROOT / "results" / "step2"
HUB = "https://hub.docker.com/v2"


def _exists(image: str) -> bool:
    repo, _, tag = image.partition(":")
    url = (f"{HUB}/repositories/{repo}/tags/{tag}" if tag and repo == "jefzda/sweap-images"
           else f"{HUB}/repositories/{repo}/")
    for attempt in range(10):
        r = requests.get(url, timeout=60)
        if r.status_code == 429:
            time.sleep(int(r.headers.get("retry-after", 30)) + 1)
            continue
        if r.status_code == 404:
            return False
        r.raise_for_status()
        return True
    raise RuntimeError(f"rate limited: {url}")


def check_all(images: list[str], workers: int = 4) -> dict[str, bool]:
    """Check images in the given order (callers put the most-needed first)."""
    from concurrent.futures import ThreadPoolExecutor
    f = CACHE / "checked.json"
    CACHE.mkdir(parents=True, exist_ok=True)
    done = json.loads(f.read_text()) if f.exists() else {}
    todo = list(dict.fromkeys(i for i in images if i not in done))
    with ThreadPoolExecutor(workers) as ex:
        for i, (img, ok) in enumerate(zip(todo, ex.map(_exists, todo)), 1):
            done[img] = ok
            if i % 200 == 0 or i == len(todo):
                f.write_text(json.dumps(done))
                (ROOT / "logs" / "progress.json").write_text(json.dumps(
                    {"stage": "envs", "done": i, "total": len(todo)}))
    return done


def image_names(name: str, df: pd.DataFrame) -> pd.Series:
    """Expected image (namespace/repo[:tag]) per task, from the dataset or its documented pattern."""
    if name.startswith("swebench_") and name != "swebench_pro" and name != "swebench_live_full":
        return df["image"]
    if name == "swegym":  # README: xingyaoww/sweb.eval.x86_64.<id with __ -> _s_>
        return "xingyaoww/sweb.eval.x86_64." + df.instance_id.str.lower().str.replace("__", "_s_")
    if name == "swebench_live_full":  # observed on Docker Hub: starryzhang/..._1776_...
        return "starryzhang/sweb.eval.x86_64." + df.instance_id.str.lower().str.replace("__", "_1776_")
    if name in ("swerebench_filtered", "swerebench_leaderboard"):
        return df["docker_image"]
    if name == "swebench_pro":
        return "jefzda/sweap-images:" + df["dockerhub_tag"]
    raise KeyError(name)


def main():
    frames = []
    for name in ["swebench_full", "swebench_verified", "swebench_lite", "swegym",
                 "swebench_live_full", "swerebench_filtered", "swebench_pro"]:
        df = load(name)
        if name == "swebench_pro":
            df = df[df.repo_language == "python"].reset_index(drop=True)
        img = image_names(name, df).str.replace(r":latest$", "", regex=True)
        frames.append(pd.DataFrame({"dataset": name, "instance_id": df.instance_id, "image": img}))
    t = pd.concat(frames, ignore_index=True)
    # Priority: eligible (1-10) tasks in candidate repos, then everything else.
    from depgraphs.recount import eligible
    idx = pd.read_parquet(OUT / "task_index.parquet")
    idx = idx[eligible(idx, 1)]
    per = idx.groupby("repo_key").size()
    hot = set(idx[idx.repo_key.isin(per[per >= 10].index)].instance_id)
    t["_p"] = ~t.instance_id.isin(hot)
    done = check_all(t.sort_values(["_p", "dataset", "instance_id"]).image.tolist())
    t = t.drop(columns="_p")
    t["on_dockerhub"] = t.image.map(done)
    OUT.mkdir(parents=True, exist_ok=True)
    t.to_csv(OUT / "env_availability.csv", index=False)
    s = t.groupby("dataset").on_dockerhub.agg(["size", "sum"]).rename(
        columns={"size": "tasks", "sum": "with_image"})
    s["pct"] = (100 * s.with_image / s.tasks).round(1)
    s.to_csv(OUT / "env_availability_summary.csv")
    print(s)


if __name__ == "__main__":
    main()
