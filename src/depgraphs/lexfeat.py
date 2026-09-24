"""Identifier bags for every graph node at every task base commit.

Reads blobs straight out of the git object store (no checkout). Each unique blob is
tokenised once per repo: source text -> identifier subtokens (split on _ and camelCase,
lowercased, length >= 2). Used by the lexical retrieval methods, which match these bags
against the issue text or the seed file.

Writes data/lexfeat/<repo>/blobs.jsonl.gz  (one {"blob": oid, "lines": n, "bag": {...}})
       data/lexfeat/<repo>/commits.json    ({sha: {path: oid}} for graph nodes only)
"""
from __future__ import annotations

import collections
import gzip
import json
import os
import re
import subprocess
import sys
import threading
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

# DEPGRAPHS_ROOT points the whole pipeline at another data/results tree, which is how
# the external repositories are run without touching the main study's files
ROOT = Path(os.environ.get("DEPGRAPHS_ROOT") or Path(__file__).resolve().parents[2])
OUT = ROOT / "data" / "lexfeat"
_SPLIT = re.compile(r"[A-Z]?[a-z0-9]+|[A-Z]+(?![a-z])")
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def split_ident(name: str) -> list[str]:
    out = []
    for part in name.split("_"):
        out += [t.lower() for t in _SPLIT.findall(part)]
    return [t for t in out if len(t) >= 2]


def bag_of(text: str) -> dict[str, int]:
    bag = collections.Counter()
    for tok in _IDENT.findall(text):
        bag.update(split_ident(tok))
    return dict(bag)


def graph_nodes(repo_dir: str, sha: str) -> list[str]:
    p = ROOT / "data" / "graphs" / repo_dir / (sha + ".json.gz")
    with gzip.open(p, "rt", encoding="utf-8") as f:
        return json.load(f)["nodes"]


def build(repo_key: str, shas: list[str]):
    repo_dir = repo_key.replace("/", "__")
    d = str(ROOT / "data" / "repos" / repo_dir)
    outdir = OUT / repo_dir
    outdir.mkdir(parents=True, exist_ok=True)
    if (outdir / "commits.json").exists():
        return repo_key, -1, -1

    commits = {}
    wanted = set()
    for sha in shas:
        try:
            nodes = set(graph_nodes(repo_dir, sha))
        except FileNotFoundError:
            continue
        r = subprocess.run(["git", "-C", d, "ls-tree", "-r", sha],
                           capture_output=True, text=True, errors="replace")
        if r.returncode != 0:
            continue
        m = {}
        for line in r.stdout.splitlines():
            meta, _, path = line.partition("\t")
            parts = meta.split()
            if len(parts) == 3 and parts[1] == "blob" and path in nodes:
                m[path] = parts[2]
        commits[sha] = m
        wanted |= set(m.values())

    oids = sorted(wanted)
    proc = subprocess.Popen(["git", "-C", d, "cat-file", "--batch"],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE)

    # git blocks once the stdout pipe fills, so the request list must be fed from a
    # separate thread; writing it all up front before reading deadlocks both ends.
    def feed():
        try:
            proc.stdin.write(("\n".join(oids) + "\n").encode())
            proc.stdin.flush()
        finally:
            proc.stdin.close()

    threading.Thread(target=feed, daemon=True).start()
    with gzip.open(outdir / "blobs.jsonl.gz", "wt", encoding="utf-8") as out:
        for _ in oids:
            header = proc.stdout.readline().decode("utf-8", "replace").split()
            if len(header) < 3:
                continue
            oid, size = header[0], int(header[2])
            raw = proc.stdout.read(size)
            proc.stdout.read(1)
            text = raw.decode("utf-8", "replace")
            lines = text.count("\n") + (0 if text.endswith("\n") or not text else 1)
            out.write(json.dumps({"blob": oid, "lines": lines, "bag": bag_of(text)}) + "\n")
    proc.stdout.close()
    proc.wait()

    (outdir / "commits.json").write_text(json.dumps(commits))
    return repo_key, len(commits), len(oids)


def main(workers: int = 8):
    tasks = [json.loads(l) for l in open(ROOT / "data" / "tasks.jsonl", encoding="utf-8")]
    by = collections.defaultdict(set)
    for t in tasks:
        by[t["repo_key"]].add(t["base_commit"])
    jobs = {k: sorted(v) for k, v in by.items()}
    done = 0
    with ProcessPoolExecutor(workers) as ex:
        futs = {ex.submit(build, k, v): k for k, v in jobs.items()}
        for f in as_completed(futs):
            rk, nc, nb = f.result()
            done += 1
            print("[%d/%d] %s commits=%s blobs=%s" % (done, len(jobs), rk, nc, nb), flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 8)
