"""Gate A extras: strata per option, and cost per repo (disk, fetch time, graph build time).

Graph build timing uses the custom ast builder with placeholder switches on the provisional
snapshot. It measures cost only; no graph from here is used for any result.
Writes results/step2/gate_a_strata.csv and results/step2/cost_per_repo.csv
"""
from __future__ import annotations

import time

import pandas as pd

from depgraphs.candidates import CLONES
from depgraphs.datasets import ROOT
from depgraphs.graph.ast_builder import build
from depgraphs.sampling import size_terciles

OUT = ROOT / "results" / "step2"


def strata():
    rules = pd.read_csv(OUT / "gate_a_repos.csv").set_index("repo_key")
    per = pd.read_csv(OUT / "gate_a_option_repos.csv")
    rows = []
    for (opt, filt, K), d in per.groupby(["option", "filter", "K"]):
        x = rules.loc[d.repo_key]
        size = size_terciles(x.nontest_py_files.reset_index(drop=True))
        src = x.datasets.str.contains("swebench_full").map({True: "swebench", False: "other"})
        tab = pd.crosstab(size.values, src.values)
        for s in tab.index:
            for c in tab.columns:
                rows.append({"option": opt, "filter": filt, "K": K, "size": s, "source": c,
                             "repos": int(tab.loc[s, c])})
        bounds = x.nontest_py_files.quantile([1 / 3, 2 / 3]).round().tolist()
        rows.append({"option": opt, "filter": filt, "K": K, "size": "tercile_cuts",
                     "source": f"{bounds[0]:.0f}/{bounds[1]:.0f} files", "repos": None})
    pd.DataFrame(rows).to_csv(OUT / "gate_a_strata.csv", index=False)


def cost(sample: int = 24):
    rules = pd.read_csv(OUT / "gate_a_repos.csv")
    r = rules[rules.passes_R2_R3_R5_X].sort_values("nontest_py_files")
    # evenly spaced by size, so timing covers small to large
    idx = [round(i * (len(r) - 1) / (sample - 1)) for i in range(sample)]
    rows = []
    for _, x in r.iloc[sorted(set(idx))].iterrows():
        t0 = time.time()
        g = build(CLONES / x.repo_key.replace("/", "__"))
        rows.append({"repo_key": x.repo_key, "nontest_py_files": x.nontest_py_files,
                     "all_py_files": x.py_files, "checkout_mb": x.checkout_mb,
                     "fetch_seconds": x.fetch_seconds,
                     "graph_build_seconds": round(time.time() - t0, 2),
                     "nodes": len(g.nodes), "edges": len(g.edges)})
    pd.DataFrame(rows).to_csv(OUT / "cost_per_repo.csv", index=False)


if __name__ == "__main__":
    strata()
    cost()
