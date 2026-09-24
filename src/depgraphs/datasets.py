"""Download task datasets from Hugging Face at pinned revisions and record checksums.

Every file lands in data/datasets/<repo_id with / replaced by __>/<path>.
data/datasets/MANIFEST.json records revision, path, size and SHA-256 for each file.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pandas as pd
from huggingface_hub import hf_hub_download

# DEPGRAPHS_ROOT points the whole pipeline at another data/results tree, which is how
# the external repositories are run without touching the main study's files
ROOT = Path(os.environ.get("DEPGRAPHS_ROOT") or Path(__file__).resolve().parents[2])
DATA = ROOT / "data" / "datasets"

# (name, hf repo id, pinned revision, files). Revisions recorded 2026-09-22.
DATASETS = [
    ("swebench_full", "SWE-bench/SWE-bench", "c6fe717fd7a4c3ac1daa4055a4fd082c6a1d28a2",
     ["data/test-00000-of-00001.parquet"]),
    ("swebench_verified", "SWE-bench/SWE-bench_Verified", "78f471bf655a3137b2e8a75af1501690ec009ec3",
     ["data/test-00000-of-00001.parquet"]),
    ("swebench_lite", "SWE-bench/SWE-bench_Lite", "b0dde1093fe417d83b7184254edf8199c1f0dff5",
     ["data/test-00000-of-00001.parquet"]),
    ("swegym", "SWE-Gym/SWE-Gym", "bb94ed9e39bbeb96a7fcbfb533b80f25a7fd59cb",
     ["data/train-00000-of-00001.parquet"]),
    ("swebench_live_full", "SWE-bench-Live/SWE-bench-Live", "b51a86422e10cfd403beb4773e5a2947953e36ec",
     ["data/full-00000-of-00002.parquet", "data/full-00001-of-00002.parquet"]),
    ("swerebench_filtered", "nebius/SWE-rebench", "89cdfbab4ab1bd8f5a658bb212d1b63624f4f881",
     ["data/filtered-00000-of-00001.parquet"]),
    ("swebench_pro", "ScaleAI/SWE-bench_Pro", "7ab5114912baf22bb098818e604c02fe7ad2c11f",
     ["data/test-00000-of-00001.parquet"]),
    ("locbench_v1", "czlll/Loc-Bench_V1", "c44cf3b74e07ca642cec841b471a9939907c12a7",
     ["data/test-00000-of-00001.parquet"]),
    ("swerebench_leaderboard", "nebius/SWE-rebench-leaderboard", "34d5a58864acf91613740a09ec5d205228dcfa39",
     ["data/test-00000-of-00001.parquet"]),
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download() -> dict:
    DATA.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for name, repo, rev, files in DATASETS:
        local_dir = DATA / repo.replace("/", "__")
        entries = []
        for f in files:
            p = Path(hf_hub_download(repo, f, repo_type="dataset", revision=rev, local_dir=local_dir))
            entries.append({"path": str(p.relative_to(ROOT)).replace("\\", "/"),
                            "bytes": p.stat().st_size, "sha256": sha256(p)})
        manifest[name] = {"repo": repo, "revision": rev, "files": entries}
    (DATA / "MANIFEST.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def load(name: str) -> pd.DataFrame:
    """Load one dataset (all its files concatenated) from the local copy."""
    manifest = json.loads((DATA / "MANIFEST.json").read_text())
    return pd.concat([pd.read_parquet(ROOT / e["path"]) for e in manifest[name]["files"]],
                     ignore_index=True)


if __name__ == "__main__":
    for k, v in download().items():
        print(k, sum(e["bytes"] for e in v["files"]))
