"""Token counts for every graph node at every task base commit.

The frozen cost metric counts lines, because that is what the frozen design fixed
at freeze-1. Lines are a poor proxy for what a file costs to put in a model's context: a
line of Python is not a constant number of tokens. This module measures the conversion
rather than assuming it, so the paper can report a budget in both units and state the
calibration instead of hand-waving at it.

Tokenised with cl100k_base, a widely used byte-pair vocabulary. Absolute counts differ by
a small constant factor between model families; the ratios this module reports do not
depend on which family is chosen, and Section 4 says so.

Reads the same blobs as lexfeat, straight from the git object store (no checkout).

Writes data/lexfeat/<repo>/tokens.json   {blob oid: token count}
"""
from __future__ import annotations

import collections
import json
import subprocess
import sys
import threading
from concurrent.futures import ProcessPoolExecutor, as_completed

from depgraphs.lexfeat import OUT, ROOT

_ENC = None


def enc():
    """One encoder per worker process; constructing it costs a few seconds."""
    global _ENC
    if _ENC is None:
        import tiktoken
        _ENC = tiktoken.get_encoding("cl100k_base")
    return _ENC


def count(repo_key: str):
    repo_dir = repo_key.replace("/", "__")
    outdir = OUT / repo_dir
    dst = outdir / "tokens.json"
    if dst.exists():
        return repo_key, -1
    try:
        commits = json.loads((outdir / "commits.json").read_text())
    except FileNotFoundError:
        return repo_key, 0

    oids = sorted({oid for m in commits.values() for oid in m.values()})
    if not oids:
        dst.write_text("{}")
        return repo_key, 0

    d = str(ROOT / "data" / "repos" / repo_dir)
    proc = subprocess.Popen(["git", "-C", d, "cat-file", "--batch"],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE)

    # Same deadlock as lexfeat: git stalls once its stdout pipe fills, so the request
    # list has to be fed from a separate thread rather than written up front.
    def feed():
        try:
            proc.stdin.write(("\n".join(oids) + "\n").encode())
            proc.stdin.flush()
        finally:
            proc.stdin.close()

    threading.Thread(target=feed, daemon=True).start()
    e = enc()
    toks = {}
    for _ in oids:
        header = proc.stdout.readline().decode("utf-8", "replace").split()
        if len(header) < 3:
            continue
        oid, size = header[0], int(header[2])
        raw = proc.stdout.read(size)
        proc.stdout.read(1)
        text = raw.decode("utf-8", "replace")
        toks[oid] = len(e.encode(text, disallowed_special=()))
    proc.stdout.close()
    proc.wait()

    dst.write_text(json.dumps(toks))
    return repo_key, len(toks)


def load(repo_dir: str) -> dict[str, int]:
    """{blob oid: tokens} for one repository."""
    return json.loads((OUT / repo_dir / "tokens.json").read_text())


def main(workers: int = 8):
    tasks = [json.loads(l) for l in open(ROOT / "data" / "tasks.jsonl", encoding="utf-8")]
    repos = sorted({t["repo_key"] for t in tasks})
    done = 0
    with ProcessPoolExecutor(workers) as ex:
        futs = [ex.submit(count, r) for r in repos]
        for f in as_completed(futs):
            rk, n = f.result()
            done += 1
            print("[%d/%d] %s blobs=%s" % (done, len(repos), rk, n), flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 8)
