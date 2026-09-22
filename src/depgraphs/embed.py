"""D23 embeddings for every unique file version (git blob) in the feature store.

Runs in its own environment (CPU torch + sentence-transformers), separate from the main
lockfile so the laptop never needs torch:
    python embed.py <project root> --threads 6
Writes data/embeddings/<repo>.npz with `blobs` (ids) and `vecs` (float16, L2-normalised).
Resumable per repo.
"""
from __future__ import annotations

import argparse
import gzip
import json
import subprocess
import time
from pathlib import Path

import numpy as np

MODEL = "jinaai/jina-embeddings-v2-base-code"
REVISION = "516f4baf13dec4ddddda8631e019b5737c8bc250"
MAX_TOKENS = 512


def read_blobs(repo_dir: Path, ids: list[str]) -> list[str]:
    r = subprocess.run(["git", "cat-file", "--batch"], cwd=repo_dir,
                       input="\n".join(ids).encode() + b"\n", capture_output=True, check=True)
    buf, pos, out = r.stdout, 0, []
    for _ in ids:
        nl = buf.index(b"\n", pos)
        size = int(buf[pos:nl].split()[2])
        out.append(buf[nl + 1: nl + 1 + size].decode("utf-8", "replace"))
        pos = nl + 1 + size + 1
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--threads", type=int, default=6)
    a = ap.parse_args()
    import torch
    from sentence_transformers import SentenceTransformer
    torch.set_num_threads(a.threads)
    model = SentenceTransformer(MODEL, revision=REVISION, trust_remote_code=True, device="cpu")
    model.max_seq_length = MAX_TOKENS
    root = Path(a.root)
    out = root / "data" / "embeddings"
    out.mkdir(parents=True, exist_ok=True)
    feats = sorted((root / "data" / "features").iterdir())
    for i, fdir in enumerate(feats):
        dest = out / f"{fdir.name}.npz"
        if dest.exists():
            continue
        t0 = time.time()
        with gzip.open(fdir / "blobs.jsonl.gz", "rt", encoding="utf-8") as f:
            ids = [json.loads(l)["blob"] for l in f]
        vecs = []
        for j in range(0, len(ids), 64):
            texts = read_blobs(root / "data" / "repos" / fdir.name, ids[j:j + 64])
            vecs.append(model.encode(texts, batch_size=16, normalize_embeddings=True,
                                     show_progress_bar=False).astype(np.float16))
        np.savez_compressed(dest, blobs=np.array(ids), vecs=np.concatenate(vecs) if vecs else
                            np.zeros((0, 768), np.float16))
        (out / "_progress.json").write_text(json.dumps(
            {"repos_done": i + 1, "repos_total": len(feats), "last": fdir.name,
             "last_files": len(ids), "last_seconds": round(time.time() - t0)}))
        print(i + 1, len(feats), fdir.name, len(ids), round(time.time() - t0), flush=True)


if __name__ == "__main__":
    main()
