"""Step 5b source 3 (execution): bundle everything the Docker runner needs, one line per PR.

Writes data/exec_bundle.jsonl: instance_id, dataset, image, gold patch, test patch,
fail-to-pass tests, and how the dataset runs its tests (SWE-bench eval_script, SWE-rebench
test_cmd, SWE-bench-Live test_cmds).
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from depgraphs.datasets import ROOT, load
from depgraphs.patches import is_py, parse


def _list(v):
    if isinstance(v, np.ndarray):
        return [str(x) for x in v.tolist()]
    return list(v) if v is not None else []


def main():
    tasks = pd.read_csv(ROOT / "data" / "sample_tasks.csv")
    ids = set(tasks.instance_id)
    out = []
    for name in ("swebench_full", "swebench_live_full", "swerebench_filtered"):
        df = load(name)
        # take each PR from the dataset the sample chose (G18 dedup order)
        df = df[df.instance_id.isin(set(tasks[tasks.dataset == name].instance_id))]
        for _, r in df.iterrows():
            test_files = sorted(f.path for f in parse(r["test_patch"])
                                if is_py(f.path) and not f.is_deleted)
            rec = {"instance_id": r["instance_id"], "dataset": name,
                   "repo": r["repo"], "base_commit": r["base_commit"],
                   "patch": r["patch"], "test_patch": r["test_patch"],
                   "test_files": test_files,
                   "f2p": _list(r["FAIL_TO_PASS"])}
            if name == "swebench_full":
                rec["image"] = r["image"]
                rec["eval_script"] = r["eval_script"]
            elif name == "swerebench_filtered":
                rec["image"] = r["docker_image"]
                rec["test_cmd"] = r["install_config"]["test_cmd"]
            else:
                rec["image"] = ("starryzhang/sweb.eval.x86_64."
                                + r["instance_id"].lower().replace("__", "_1776_"))
                rec["test_cmds"] = _list(r["test_cmds"])
            out.append(rec)
    missing = ids - {r["instance_id"] for r in out}
    assert not missing, missing
    assert len(out) == len(ids), (len(out), len(ids))
    with open(ROOT / "data" / "exec_bundle.jsonl", "w", encoding="utf-8") as f:
        for rec in sorted(out, key=lambda x: x["instance_id"]):
            f.write(json.dumps(rec) + "\n")
    print(len(out), "PRs bundled")


if __name__ == "__main__":
    main()
