"""Step 2: recount RUNBOOK section 9.2 from the raw dataset files.

Writes:
  results/step2/task_index.parquet     one row per task, every dataset, filter-relevant fields
  results/step2/recount_9_2.csv        the section 9.2 table, recomputed
  results/step2/linecap_grid.csv       eligible tasks under several line caps (for D19)
  results/step2/per_repo_eligible.csv  eligible tasks per repo per dataset
  results/step2/overlap.csv            repos that appear in more than one dataset (G18)
"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from depgraphs.datasets import DATASETS, ROOT, load
from depgraphs.patches import is_py, is_test_path_9_2, parse

OUT = ROOT / "results" / "step2"
LINE_CAPS = [50, 100, 200, 300, 500, None]
MAIN_CAP = 200  # the cap used in RUNBOOK 9.2; D19 decides the real one

# Datasets that appear in the 9.2 table. The leaderboard is a Step 10 source only.
TABLE_ORDER = ["swebench_full", "swebench_verified", "swebench_lite", "swegym",
               "swebench_live_full", "swerebench_filtered", "swebench_pro", "locbench_v1"]


def _as_list(v) -> list:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return []
    if isinstance(v, (list, tuple, np.ndarray)):
        return list(v)
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return []
        try:
            return list(json.loads(s))
        except json.JSONDecodeError:
            return list(ast.literal_eval(s))
    raise TypeError(type(v))


def _pr_number(row, name: str):
    if name == "swebench_live_full":
        return str(row["pull_number"])
    m = re.search(r"-(\d+)$", str(row["instance_id"]))
    return m.group(1) if m and name != "swebench_pro" else None


def _created(row, name: str):
    if name == "swebench_pro" or "created_at" not in row:
        return pd.NaT
    v = row["created_at"]
    if isinstance(v, (int, np.integer)):
        return pd.to_datetime(int(v), unit="ms", utc=True)
    return pd.to_datetime(v, utc=True)


def task_rows(name: str, df: pd.DataFrame) -> list[dict]:
    if name == "swebench_pro":
        df = df[df.repo_language == "python"]
    rows = []
    for _, r in df.iterrows():
        files = parse(r["patch"])
        py = [f for f in files if is_py(f.path)]
        src = [f for f in py if not is_test_path_9_2(f.path)]
        f2p_col = "fail_to_pass" if name == "swebench_pro" else "FAIL_TO_PASS"
        f2p = _as_list(r[f2p_col]) if f2p_col in r else None
        issues = _as_list(r["issue_numbers"]) if "issue_numbers" in r else None
        rows.append({
            "dataset": name,
            "instance_id": r["instance_id"],
            "repo": r["repo"],
            "repo_key": r["repo"].lower(),
            "pr_number": _pr_number(r, name),
            "base_commit": r["base_commit"],
            "created_at": _created(r, name),
            "n_patch_files": len(files),
            "n_py_files": len(py),
            "n_src_py_files": len(src),
            "n_test_py_in_patch": len(py) - len(src),
            "n_nonpy_files": len(files) - len(py),
            "src_changed_lines": sum(f.changed for f in src),
            "n_new_src_py": sum(f.is_new for f in src),
            "n_deleted_src_py": sum(f.is_deleted for f in src),
            "n_f2p": len(f2p) if f2p is not None else np.nan,
            "n_issues": len(issues) if issues is not None else np.nan,
            "licence": r.get("license_name"),
        })
    return rows


def eligible(t: pd.DataFrame, lo: int, hi: int = 10, cap: int | None = MAIN_CAP,
             need_f2p: bool = True) -> pd.Series:
    m = t.n_src_py_files.between(lo, hi)
    if cap is not None:
        m &= t.src_changed_lines <= cap
    if need_f2p:
        m &= t.n_f2p.fillna(0) >= 1
    return m


def build_index() -> pd.DataFrame:
    rows = []
    for name, *_ in DATASETS:
        rows += task_rows(name, load(name))
    t = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    t.to_parquet(OUT / "task_index.parquet", index=False)
    return t


def table_9_2(t: pd.DataFrame) -> pd.DataFrame:
    out = []
    for name in TABLE_ORDER:
        d = t[t.dataset == name]
        has_f2p = d.n_f2p.notna().any()
        e2 = eligible(d, 2, need_f2p=has_f2p)
        e1 = eligible(d, 1, need_f2p=has_f2p)
        per2 = d[e2].groupby("repo").size()
        per1 = d[e1].groupby("repo").size()
        out.append({
            "dataset": name,
            "tasks": len(d),
            "repos": d.repo.nunique(),
            "pct_1_file": round(100 * (d.n_src_py_files == 1).mean(), 1),
            "pct_2_10_files": round(100 * d.n_src_py_files.between(2, 10).mean(), 1),
            "pct_0_src_files": round(100 * (d.n_src_py_files == 0).mean(), 1),
            "pct_over_10_files": round(100 * (d.n_src_py_files > 10).mean(), 1),
            "eligible_2_10": int(e2.sum()),
            "eligible_1_10": int(e1.sum()),
            "repos_15plus_2_10": int((per2 >= 15).sum()),
            "repos_15plus_1_10": int((per1 >= 15).sum()),
            "repos_10plus_2_10": int((per2 >= 10).sum()),
            "repos_10plus_1_10": int((per1 >= 10).sum()),
            "pct_tasks_create_src_py": round(100 * (d.n_new_src_py > 0).mean(), 1),
            "f2p_filter_applied": bool(has_f2p),
            "date_min": d.created_at.min(),
            "date_max": d.created_at.max(),
            "pct_multi_issue": (round(100 * (d.n_issues > 1).mean(), 1)
                                if d.n_issues.notna().any() else None),
        })
    return pd.DataFrame(out)


def linecap_grid(t: pd.DataFrame) -> pd.DataFrame:
    out = []
    for name in TABLE_ORDER:
        d = t[t.dataset == name]
        has_f2p = d.n_f2p.notna().any()
        for lo in (2, 1):
            for cap in LINE_CAPS:
                e = eligible(d, lo, cap=cap, need_f2p=has_f2p)
                per = d[e].groupby("repo").size()
                out.append({"dataset": name, "files": f"{lo}-10", "line_cap": cap or "none",
                            "eligible": int(e.sum()), "repos_10plus": int((per >= 10).sum()),
                            "repos_15plus": int((per >= 15).sum())})
    return pd.DataFrame(out)


def per_repo(t: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (name, repo), d in t.groupby(["dataset", "repo"]):
        has_f2p = d.n_f2p.notna().any()
        rows.append({"dataset": name, "repo": repo, "tasks": len(d),
                     "eligible_2_10": int(eligible(d, 2, need_f2p=has_f2p).sum()),
                     "eligible_1_10": int(eligible(d, 1, need_f2p=has_f2p).sum()),
                     "date_min": d.created_at.min(), "date_max": d.created_at.max(),
                     "licence": d.licence.dropna().iloc[0] if d.licence.notna().any() else None})
    return pd.DataFrame(rows).sort_values(["dataset", "eligible_2_10"], ascending=[True, False])


def overlap(t: pd.DataFrame) -> pd.DataFrame:
    t = t[t.dataset.isin(TABLE_ORDER)]
    g = t.groupby("repo_key").dataset.agg(lambda s: sorted(set(s)))
    g = g[g.map(len) > 1]
    return pd.DataFrame({"repo_key": g.index, "datasets": g.map(";".join).values,
                         "n_datasets": g.map(len).values}).sort_values("n_datasets", ascending=False)


def main():
    t = build_index()
    table_9_2(t).to_csv(OUT / "recount_9_2.csv", index=False)
    linecap_grid(t).to_csv(OUT / "linecap_grid.csv", index=False)
    per_repo(t).to_csv(OUT / "per_repo_eligible.csv", index=False)
    overlap(t).to_csv(OUT / "overlap.csv", index=False)


if __name__ == "__main__":
    main()
