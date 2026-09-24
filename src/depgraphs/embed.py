"""D23 embeddings: every file version the scored graphs contain, and every issue text.

Runs in its own environment (CPU torch + sentence-transformers), separate from the main
lockfile so that nothing else needs torch; it imports nothing from this package:
    python src/depgraphs/embed.py <project root> [--threads 4]

Model and window are D23's, fixed before any run: jinaai/jina-embeddings-v2-base-code at the
pinned revision, the first 512 tokens of each file, L2-normalised. Inference is in bfloat16,
which D23 did not specify; on the machine used it is 3x faster than float32, and on a 256-file
check its vectors have cosine >= 0.997 to float32's and a median Spearman correlation of
0.9996 between the two similarity rankings (POSTHOC.md). Issues are embedded whole: split
into consecutive 512-token chunks, each embedded, and the chunk vectors averaged with weights
proportional to their length and re-normalised. Nothing is truncated, so deleting names from
an issue (redact.py) cannot pull text into a window that the unredacted issue had cut off.

Files are done in two passes: first those in graphs of pull requests carrying both keys (the
matched population every controlled comparison uses), then the rest, so that an interrupted
run still covers the matched population.

Writes data/embeddings/<repo>.p1.npz, <repo>.p2.npz   `blobs` (ids), `vecs` (float16)
       data/embeddings/issues.npz                      `ids` ("<task_id>|<arm>"), `vecs`
Resumable per file.
"""
from __future__ import annotations

import argparse
import gzip
import json
import subprocess
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

MODEL = "jinaai/jina-embeddings-v2-base-code"
REVISION = "516f4baf13dec4ddddda8631e019b5737c8bc250"
MAX_TOKENS = 512
CHUNK = 510   # 512 less the two special tokens


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


def needed_blobs(root: Path) -> dict[str, list[set[str]]]:
    """repo_dir -> [blobs for pass 1, blobs for pass 2 only]."""
    tasks = [json.loads(l) for l in open(root / "data" / "tasks.jsonl", encoding="utf-8")]
    shas = defaultdict(lambda: [set(), set()])
    for t in tasks:
        both = bool(t["keys"].get("co_edited")) and bool(t["keys"].get("symbol"))
        shas[t["repo_key"].replace("/", "__")][0 if both else 1].add(t["base_commit"])
    out = {}
    for d, (s1, s2) in sorted(shas.items()):
        commits = json.loads((root / "data" / "lexfeat" / d / "commits.json").read_text())
        passes = []
        for s in (s1, s2 - s1):
            blobs = set()
            for sha in s:
                gp = root / "data" / "graphs" / d / (sha + ".json.gz")
                if not gp.exists():
                    continue
                with gzip.open(gp, "rt", encoding="utf-8") as f:
                    nodes = json.load(f)["nodes"]
                m = commits.get(sha, {})
                blobs |= {m[p] for p in nodes if p in m}
            passes.append(blobs)
        passes[1] -= passes[0]
        out[d] = passes
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--threads", type=int, default=4)
    a = ap.parse_args()
    import torch
    from sentence_transformers import SentenceTransformer
    torch.set_num_threads(a.threads)
    model = SentenceTransformer(MODEL, revision=REVISION, trust_remote_code=True,
                                device="cpu", model_kwargs={"torch_dtype": torch.bfloat16})
    root = Path(a.root)
    out = root / "data" / "embeddings"
    out.mkdir(parents=True, exist_ok=True)

    def encode(texts):
        return model.encode(texts, batch_size=16, normalize_embeddings=True,
                            convert_to_tensor=True).float().numpy().astype(np.float16)

    dest = out / "issues.npz"
    if not dest.exists():
        texts = json.loads((root / "data" / "issue_texts_redacted.json").read_text())
        ids = sorted("%s|%s" % (t, arm) for t, v in texts.items() for arm in v)
        model.max_seq_length = MAX_TOKENS
        tok = model.tokenizer
        t0 = time.time()
        chunks, owner, weight = [], [], []
        for j, i in enumerate(ids):
            task, arm = i.rsplit("|", 1)
            toks = tok(texts[task][arm] or " ", add_special_tokens=False)["input_ids"] or [0]
            for k in range(0, len(toks), CHUNK):
                piece = toks[k:k + CHUNK]
                chunks.append(tok.decode(piece))
                owner.append(j)
                weight.append(len(piece))
        cv = encode(chunks).astype(np.float32) * np.array(weight, dtype=np.float32)[:, None]
        vecs = np.zeros((len(ids), cv.shape[1]), dtype=np.float32)
        np.add.at(vecs, np.array(owner), cv)
        vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)
        np.savez_compressed(dest, ids=np.array(ids), vecs=vecs.astype(np.float16))
        print("issues: %d texts, %d chunks in %.0fs" % (len(ids), len(chunks),
                                                        time.time() - t0), flush=True)

    model.max_seq_length = MAX_TOKENS
    need = needed_blobs(root)
    total = [sum(len(v[i]) for v in need.values()) for i in (0, 1)]
    print("files to embed: pass 1 %d, pass 2 %d" % tuple(total), flush=True)
    done = 0
    t_start = time.time()
    for p in (0, 1):
        for d, passes in need.items():
            dest = out / ("%s.p%d.npz" % (d, p + 1))
            ids = sorted(passes[p])
            if dest.exists() or not ids:
                done += len(ids) if dest.exists() else 0
                continue
            vecs = encode(read_blobs(root / "data" / "repos" / d, ids))
            np.savez_compressed(dest, blobs=np.array(ids), vecs=vecs)
            done += len(ids)
            rate = done / max(time.time() - t_start, 1)
            print("pass %d %s: %d files; %d/%d done, %.1f files/s" % (
                p + 1, d, len(ids), done, sum(total), rate), flush=True)


if __name__ == "__main__":
    main()
