"""Per-file features at every task base commit, for the methods in paper/methods.md.

Reads file contents from git objects (no checkout). Each unique file version (git blob) is
processed once per repo:
  lines, tokens (tiktoken o200k_base), identifier bag (split on _ and camelCase),
  definitions, references, callee names
Writes data/features/<repo>/blobs.jsonl.gz and data/features/<repo>/commits/<sha>.json
(path -> blob id for every graph node). Failures to data/features/<repo>/failures.json.
"""
from __future__ import annotations

import ast
import gzip
import json
import re
import subprocess
import sys
import warnings
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

from depgraphs import progress
from depgraphs.candidates import CLONES
from depgraphs.datasets import ROOT
from depgraphs.graphs import load_graph

FEAT = ROOT / "data" / "features"
_SPLIT = re.compile(r"[A-Z]?[a-z0-9]+|[A-Z]+(?![a-z])")
sys.setrecursionlimit(20000)


def split_ident(name: str) -> list[str]:
    out = []
    for part in name.split("_"):
        out += [t.lower() for t in _SPLIT.findall(part)]
    return [t for t in out if len(t) >= 2]


def blob_features(text: str, enc) -> dict:
    lines = text.count("\n") + (0 if text.endswith("\n") or not text else 1)
    feats = {"lines": lines, "tokens": len(enc.encode(text, disallowed_special=()))}
    defs, refs, calls, bag = set(), set(), set(), Counter()
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            tree = ast.parse(text)
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                defs.add(node.name)
                if isinstance(node, ast.ClassDef):
                    for sub in node.body:
                        if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            defs.add(sub.name)
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for t in targets:
                    if isinstance(t, ast.Name):
                        defs.add(t.id)
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                refs.add(node.id)
                bag.update(split_ident(node.id))
            elif isinstance(node, ast.Attribute):
                refs.add(node.attr)
                bag.update(split_ident(node.attr))
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                bag.update(split_ident(node.name))
            if isinstance(node, ast.Call):
                f = node.func
                if isinstance(f, ast.Name):
                    calls.add(f.id)
                elif isinstance(f, ast.Attribute):
                    calls.add(f.attr)
        feats["parse_ok"] = True
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        feats["parse_ok"] = False
        for tok in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", text):
            bag.update(split_ident(tok))
    feats.update(defs=sorted(defs), refs=sorted(refs), calls=sorted(calls), bag=dict(bag))
    return feats


def _git(args, cwd, **kw):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, timeout=3600, **kw)


def repo_job(repo_key: str, url: str, shas: list[str]) -> dict:
    import tiktoken
    enc = tiktoken.get_encoding("o200k_base")
    d = CLONES / repo_key.replace("/", "__")
    out = FEAT / repo_key.replace("/", "__")
    (out / "commits").mkdir(parents=True, exist_ok=True)
    fails = []
    if not (d / ".git").exists():
        d.mkdir(parents=True, exist_ok=True)
        _git(["init", "-q"], d)
        _git(["remote", "add", "origin", url], d)
    todo = [s for s in shas if not (out / "commits" / f"{s}.json").exists()]
    for i in range(0, len(todo), 20):
        r = _git(["fetch", "-q", "--depth", "1", "origin", *todo[i:i + 20]], d)
        if r.returncode != 0:
            for s in todo[i:i + 20]:
                if _git(["fetch", "-q", "--depth", "1", "origin", s], d).returncode != 0:
                    fails.append({"sha": s, "stage": "fetch"})
    seen = set()
    bf = out / "blobs.jsonl.gz"
    if bf.exists():
        with gzip.open(bf, "rt", encoding="utf-8") as f:
            seen = {json.loads(l)["blob"] for l in f}
    with gzip.open(bf, "at", encoding="utf-8") as fout:
        for s in todo:
            if any(f["sha"] == s for f in fails):
                continue
            nodes = set(load_graph(repo_key, s)["nodes"])
            r = _git(["ls-tree", "-r", s], d)
            if r.returncode != 0:
                fails.append({"sha": s, "stage": "ls-tree"})
                continue
            mapping = {}
            for line in r.stdout.decode("utf-8", "replace").splitlines():
                meta, path = line.split("\t", 1)
                if path in nodes:
                    mapping[path] = meta.split()[2]
            missing = nodes - set(mapping)
            if missing:
                fails.append({"sha": s, "stage": "nodes_not_in_tree", "n": len(missing)})
            new = [b for b in set(mapping.values()) if b not in seen]
            if new:
                cat = subprocess.run(["git", "cat-file", "--batch"], cwd=d,
                                     input="\n".join(new).encode() + b"\n",
                                     capture_output=True, timeout=3600)
                buf, pos = cat.stdout, 0
                for b in new:
                    nl = buf.index(b"\n", pos)
                    header = buf[pos:nl].split()
                    size = int(header[2])
                    text = buf[nl + 1: nl + 1 + size].decode("utf-8", "replace")
                    pos = nl + 1 + size + 1
                    fout.write(json.dumps({"blob": b, **blob_features(text, enc)}) + "\n")
                    seen.add(b)
            (out / "commits" / f"{s}.json").write_text(json.dumps(mapping))
    (out / "failures.json").write_text(json.dumps(fails))
    return {"repo_key": repo_key, "failures": len(fails)}


def main(workers: int = 12):
    tasks = pd.read_csv(ROOT / "data" / "sample_tasks.csv")
    repos = pd.read_csv(ROOT / "data" / "repos.csv").set_index("repo_key")
    jobs = {rk: list(dict.fromkeys([repos.loc[rk, "pinned_sha"], *d.base_commit]))
            for rk, d in tasks.groupby("repo_key")}
    done = fails = 0
    with ProcessPoolExecutor(workers) as ex:
        futs = {ex.submit(repo_job, rk, repos.loc[rk, "url"] + ".git", shas): rk
                for rk, shas in jobs.items()}
        for f in as_completed(futs):
            done += 1
            try:
                fails += f.result()["failures"]
            except Exception as e:
                fails += 1
                print("FAILED", futs[f], repr(e)[:300], flush=True)
            progress.update("features", repos_done=done, repos_total=len(jobs), failures=fails)
    print("features done; failures:", fails)


if __name__ == "__main__":
    main()
