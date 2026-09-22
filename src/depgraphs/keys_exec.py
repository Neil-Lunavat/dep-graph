"""Execution answer key (source 3) from the Docker runs, under the three D20 rules.

  A: a line of the file ran during a fail-to-pass test
  B: a line inside a function/method body ran during a fail-to-pass test   (primary)
  C: B, minus files with function-body lines that ran in the do-nothing test
Only non-test `.py` repository files that are not created by the PR count.
Reads the runner's output dir; writes data/keys_exec/<instance_id>.json for runs with status
ok, and results/step5/keys_exec_status.csv for every run (so nothing is dropped silently).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

from depgraphs.datasets import ROOT
from depgraphs.patches import is_py, is_test_path


def keys_for(res: dict, new_files: set[str]) -> dict:
    main = res["main"]["files"]
    noop = (res.get("noop") or {}).get("files", {})
    A, B, C = set(), set(), set()
    for path, v in main.items():
        if path.startswith("/") or not is_py(path) or is_test_path(path) or path in new_files:
            continue
        f2p = set(v["f2p_lines"])
        if not f2p:
            continue
        A.add(path)
        fn = set(v["fn_lines"] or [])
        if f2p & fn:
            B.add(path)
            nv = noop.get(path)
            if not (nv and set(nv["executed"]) & fn):
                C.add(path)
    return {"A": sorted(A), "B": sorted(B), "C": sorted(C)}


def main(out_dir: str):
    rows = []
    dest = ROOT / "data" / "keys_exec"
    dest.mkdir(parents=True, exist_ok=True)
    for p in sorted(Path(out_dir).glob("*.json")):
        if p.name.startswith("_"):
            continue
        res = json.loads(p.read_text())
        iid = res["instance_id"]
        rows.append({"instance_id": iid, "status": res["status"], "tests_exit": res.get("tests_exit"),
                     "seconds": res.get("seconds")})
        if res["status"] != "ok":
            continue
        ks = ROOT / "data" / "keys_static" / f"{iid}.json"
        new = set(json.loads(ks.read_text()).get("new_files", [])) if ks.exists() else set()
        k = keys_for(res, new)
        rows[-1].update({f"n_{r}": len(v) for r, v in k.items()})
        (dest / f"{iid}.json").write_text(json.dumps({"keys": k}))
    (ROOT / "results" / "step5").mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(ROOT / "results" / "step5" / "keys_exec_status.csv", index=False)
    print(pd.DataFrame(rows).status.value_counts().to_dict())


if __name__ == "__main__":
    main(sys.argv[1])
