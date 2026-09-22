"""Step 9 summary (RQ4): PR-level mean AUC (union key) per method under each seed condition.
Writes results/analysis/wrong_seed.csv (all methods) — the page shows the top 8 + random."""
from __future__ import annotations

import pandas as pd

from depgraphs.analysis import EXCLUDED, REFS, pr_level
from depgraphs.datasets import ROOT


def main():
    cols = {}
    for c in ["true", "wrong1", "wrong2", "wrongrand"]:
        s = pd.read_parquet(ROOT / "results" / "scores" / f"{c}.parquet")
        pr = pr_level(s, "union")
        cols[c] = pr.mean()
    df = pd.DataFrame(cols)
    df = df[~df.index.isin(EXCLUDED | {"oracle", "closure_fwd_trim"})].sort_values("true", ascending=False)
    top = [m for m in df.index if m not in REFS][:8] + ["random"]
    df.loc[top].rename_axis("method").to_csv(ROOT / "results" / "analysis" / "wrong_seed.csv")
    df.rename_axis("method").to_csv(ROOT / "results" / "analysis" / "wrong_seed_all.csv")
    print(df.loc[top].round(3))


if __name__ == "__main__":
    main()
