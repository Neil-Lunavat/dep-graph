"""What no retrieval method can beat, and what a budget costs in tokens.

Two questions the coverage curves do not answer.

1. The ceiling. Coverage at a budget says how much of the key a method found. It does not
   say whether finding all of it was possible. If the key files together exceed the budget,
   no ordering of them fits, and no agent -- however capable -- can read what it was not
   given. The ceiling is a property of the task and the budget alone, independent of
   method, and it bounds every method at once.

2. The unit. The frozen metric counts lines because freeze-1 fixed it that way. A context
   window is measured in tokens, and a line of Python is not a constant number of them.
   This module measures the conversion across the corpus instead of assuming it.

Nothing here re-runs or revises the frozen metric; the line-based results stand as
pre-registered and these are reported alongside them.

Writes results/study2/ceiling_key.csv      share of tasks whose whole key fits a budget
       results/study2/ceiling_method.csv   share of tasks a method takes to full coverage
       results/study2/token_calibration.csv  tokens per line, corpus wide
"""
from __future__ import annotations

import collections
import gzip
import json

import numpy as np
import pandas as pd

from depgraphs.lexfeat import OUT as LEXOUT, ROOT
from depgraphs.study2 import BUDGETS, OUT, load_graph

# Budgets in tokens, chosen to bracket real context windows rather than to mirror the
# line grid: 4k and 8k are small-model windows, 32k-128k the common working range, 200k
# and 1M the current large ones.
TOKEN_BUDGETS = [4000, 8000, 16000, 32000, 64000, 128000, 200000, 1000000]
SOURCES = ["co_edited", "symbol"]


def blob_lines(repo_dir: str) -> dict[str, int]:
    out = {}
    with gzip.open(LEXOUT / repo_dir / "blobs.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            out[r["blob"]] = r["lines"]
    return out


def collect():
    """Per task and key source: size of the key in lines and in tokens."""
    tasks = [json.loads(l) for l in open(ROOT / "data" / "tasks.jsonl", encoding="utf-8")]
    by = collections.defaultdict(list)
    for t in tasks:
        by[t["repo_key"]].append(t)

    rows, cal = [], []
    for rk, ts in sorted(by.items()):
        rd = rk.replace("/", "__")
        try:
            toks = json.loads((LEXOUT / rd / "tokens.json").read_text())
            commits = json.loads((LEXOUT / rd / "commits.json").read_text())
            blines = blob_lines(rd)
        except FileNotFoundError:
            continue

        # corpus-wide tokens-per-line calibration, one row per unique blob
        for oid, nt in toks.items():
            nl = blines.get(oid)
            if nl:
                cal.append((rk, nl, nt))

        for t in ts:
            sha = t["base_commit"]
            m = commits.get(sha)
            if not m:
                continue
            try:
                nodes, _, lines = load_graph(rd, sha)
            except FileNotFoundError:
                continue
            nodeset = set(nodes)
            seed = t["seed"]
            for src in SOURCES:
                key = (set(t["keys"].get(src, [])) & nodeset) - {seed}
                if not key:
                    continue
                kt = sum(toks.get(m[p], 0) for p in key if p in m)
                kl = sum(lines.get(p, 0) for p in key)
                rows.append({
                    "task_id": t["task_id"], "instance_id": t["instance_id"],
                    "repo_key": rk, "source": src, "key_files": len(key),
                    "key_lines": kl, "key_tokens": kt,
                    "repo_files": len(nodes),
                    "repo_tokens": sum(toks.get(o, 0) for o in m.values()),
                })
    return pd.DataFrame(rows), pd.DataFrame(cal, columns=["repo_key", "lines", "tokens"])


def ceiling_key(df: pd.DataFrame) -> pd.DataFrame:
    """Share of pull requests whose entire key fits inside a budget.

    Averaged within a pull request first, so a PR touching many files counts once.
    """
    out = []
    for src, g in df.groupby("source"):
        for b in TOKEN_BUDGETS:
            fits = g.assign(f=(g.key_tokens <= b).astype(float)) \
                    .groupby("instance_id")["f"].mean()
            out.append({"source": src, "unit": "tokens", "budget": b,
                        "share_fits": fits.mean(), "n_prs": len(fits)})
        for b in BUDGETS:
            fits = g.assign(f=(g.key_lines <= b).astype(float)) \
                    .groupby("instance_id")["f"].mean()
            out.append({"source": src, "unit": "lines", "budget": b,
                        "share_fits": fits.mean(), "n_prs": len(fits)})
    return pd.DataFrame(out)


def ceiling_method(curves: pd.DataFrame) -> pd.DataFrame:
    """Share of pull requests a method actually takes to complete coverage."""
    c = curves[curves.source.isin(SOURCES)].copy()
    c["full"] = (c.coverage >= 0.999).astype(float)
    pr = c.groupby(["source", "method", "budget", "instance_id"])["full"].mean()
    return (pr.groupby(["source", "method", "budget"]).mean()
            .reset_index().rename(columns={"full": "share_full"}))


def calibration(cal: pd.DataFrame) -> pd.DataFrame:
    r = cal[cal.lines > 0].copy()
    r["tpl"] = r.tokens / r.lines
    q = r.tpl.quantile([0.05, 0.25, 0.5, 0.75, 0.95])
    return pd.DataFrame([{
        "n_blobs": len(r),
        "total_lines": int(r.lines.sum()), "total_tokens": int(r.tokens.sum()),
        "aggregate_tokens_per_line": r.tokens.sum() / r.lines.sum(),
        "median_tokens_per_line": q[0.5],
        "p05": q[0.05], "p25": q[0.25], "p75": q[0.75], "p95": q[0.95],
    }])


def main():
    df, cal = collect()
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT / "key_size.csv", index=False)

    ck = ceiling_key(df)
    ck.to_csv(OUT / "ceiling_key.csv", index=False)

    curves = pd.read_parquet(OUT / "curves.parquet")
    cm = ceiling_method(curves)
    cm.to_csv(OUT / "ceiling_method.csv", index=False)

    cb = calibration(cal)
    cb.to_csv(OUT / "token_calibration.csv", index=False)

    print("tasks scored:", len(df), " prs:", df.instance_id.nunique())
    print()
    print("tokens per line, %d blobs" % cb.n_blobs[0])
    print(cb.drop(columns=["n_blobs"]).round(3).to_string(index=False))
    print()
    print("key size (median per task)")
    print(df.groupby("source")[["key_files", "key_lines", "key_tokens"]]
          .median().round(0).to_string())
    print()
    print("repo size (median tokens):", int(df.repo_tokens.median()))
    print()
    print("share of PRs whose WHOLE key fits the budget")
    print(ck[ck.unit == "tokens"].pivot(index="budget", columns="source",
                                        values="share_fits").round(3).to_string())


if __name__ == "__main__":
    main()
