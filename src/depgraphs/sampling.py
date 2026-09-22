"""Mechanical repository draw (RUNBOOK 9.4, N7).

Within each stratum, sort candidates by SHA-256 of f"{seed}{repo_name}" and take the first n.
A fixed comparability block (if D11 includes one) is added as-is, never drawn.
"""
from __future__ import annotations

import hashlib

import pandas as pd


def draw_key(seed: str | int, repo: str) -> str:
    return hashlib.sha256(f"{seed}{repo}".encode("utf-8")).hexdigest()


def draw(candidates: pd.DataFrame, seed: str | int, n_per_stratum: dict | int,
         stratum_col: str = "stratum", repo_col: str = "repo",
         fixed_block: list[str] | None = None) -> pd.DataFrame:
    fixed_block = fixed_block or []
    pool = candidates[~candidates[repo_col].isin(fixed_block)].copy()
    pool["_key"] = pool[repo_col].map(lambda r: draw_key(seed, r))
    picked = []
    for stratum, d in pool.groupby(stratum_col, sort=True):
        n = n_per_stratum if isinstance(n_per_stratum, int) else n_per_stratum.get(stratum, 0)
        picked.append(d.sort_values(["_key", repo_col]).head(n))
    out = pd.concat(picked + [candidates[candidates[repo_col].isin(fixed_block)]],
                    ignore_index=True)
    out["in_fixed_block"] = out[repo_col].isin(fixed_block)
    return out.drop(columns="_key", errors="ignore")


def size_terciles(values: pd.Series) -> pd.Series:
    """Tercile label (small/medium/large) by rank, ties broken by order of appearance."""
    ranks = values.rank(method="first")
    return pd.qcut(ranks, 3, labels=["small", "medium", "large"]).astype(str)
