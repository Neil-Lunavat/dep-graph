"""Issue text for every task instance, tokenised the same way as file contents.

The problem statement is the natural-language starting point a developer (or an agent)
actually has. Every instance in data/tasks.jsonl is matched to its source dataset row and
the statement is turned into the same identifier-subtoken bag used for file contents, so
lexical retrieval scores text against code on one vocabulary.

Writes data/issue_bags.json: {instance_id: {"chars": n, "bag": {token: count}}}
"""
from __future__ import annotations

import glob
import json
from pathlib import Path

import pandas as pd

from depgraphs.lexfeat import ROOT, bag_of


def load_statements() -> dict[str, str]:
    tasks = [json.loads(l) for l in open(ROOT / "data" / "tasks.jsonl", encoding="utf-8")]
    want = {t["instance_id"] for t in tasks}
    found: dict[str, str] = {}
    for f in sorted(glob.glob(str(ROOT / "data" / "datasets" / "*" / "data" / "*.parquet"))):
        df = pd.read_parquet(f)
        if "instance_id" not in df.columns or "problem_statement" not in df.columns:
            continue
        for iid, ps in zip(df["instance_id"], df["problem_statement"]):
            if iid in want and iid not in found and isinstance(ps, str) and ps.strip():
                found[iid] = ps
    return found


def main():
    st = load_statements()
    out = {iid: {"chars": len(text), "bag": bag_of(text)} for iid, text in st.items()}
    p = ROOT / "data" / "issue_bags.json"
    p.write_text(json.dumps(out))
    print("instances:", len(out), "->", p)


if __name__ == "__main__":
    main()
