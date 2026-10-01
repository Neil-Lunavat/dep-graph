# Metrics — formulas fixed before computing (ROADMAP Step 7, Appendix E; D13, D14)

Written 2026-09-22, before any list was scored. Part of tag `freeze-1`.

## Notation

Task t: seed s, answer key K (a set of files; per source or union, N4). Method output: list
L = (l_1, …, l_n), s ∉ L. cost(f) = physical lines of file f at the base commit (primary);
alternatives: cost(f) = 1 (files) and tokens under tiktoken `o200k_base`.
C_j = Σ_{i ≤ j} cost(l_i). Tasks with K = ∅ (for the source in question) are not scored and
are counted.

## Primary: coverage–cost curve and AUC

cov_t(b) = |K ∩ {l_i : C_i ≤ b}| / |K|  — the share of the key read within budget b.

Budget grid (lines) B = {250, 500, 1000, 2000, 4000, 8000, 16000, 32000}.
Files grid: {1, 2, 4, 8, 16, 32, 64, 128}. Tokens grid: 10 × the lines grid.

**AUC_t = (1/|B|) Σ_{b ∈ B} cov_t(b)**, in [0, 1] — equal weight per doubling of the budget.

Per PR: mean of AUC_t over its tasks (G11). Per method: mean over the 5 tie-breaking runs
(D21) first, then over tasks.

## Comparability with prior work (N8: never compared to published numbers)

Rank r(f) = position of f in L (1-based); ∞ if absent. R_K = sorted ranks of key files.
- Acc@k (k = 1, 3, 5, 10): 1 if every key file has rank ≤ k, else 0.
- Top-N (N = 1, 5, 10): 1 if some key file has rank ≤ N.
- MRR: 1 / min r(f) over f ∈ K (0 if none).
- AP: (1/|K|) Σ_{f ∈ K, r(f) < ∞} precision@r(f).
- NDCG@10: binary gains, log2 discount, ideal = all key files first.
- Empty rate: share of tasks where L = ∅.
- Odds ratio vs random: m = min(10, n) top files, h = key files among them,
  E = m·|K|/N the expected hits for m uniformly random files (N = graph files minus the seed).
  OR = [(h + 0.5)/(m − h + 0.5)] / [(E + 0.5)/(m − E + 0.5)] (Haldane +0.5 correction so it is
  defined at h = 0 and h = m). Undefined (not reported) when n = 0.

## Ordering checks

Over the files of L that are in G's condensation DAG D:
- valid_topo: 1 if for every edge u → v of G with u, v ∈ L in different clumps, v comes
  before u (dependencies first).
- inversions: share of such edge pairs in the wrong order (0 = valid).
- first_key_rank: min r(f) over f ∈ K.

## Also recorded per method and task

Wall-clock runtime, list length n, total lines Σ cost(l_i).

## Statistics (D14)

Unit: PR. Pairwise method comparisons and each method vs `random`: Wilcoxon signed-rank on
PR-level AUC, effect size Vargha–Delaney A12, Holm correction within each comparison family.
All methods across repos: Friedman test + Nemenyi post-hoc on per-repo mean AUC.
RQ2: Spearman ρ across repos for every (Table 1 metric, method) pair, where the method value
is the repo's mean AUC minus the random floor's; Benjamini–Hochberg; exploratory; all pairs
reported. 95% confidence intervals by bootstrap over repositories (2,000 resamples, seed
20260922). All results are reported per key source (co-edited, symbol, execution B, union),
and for single-file and multi-file PRs separately (D19).

## RQ3 distances

For each (seed, key file): shortest path length on G fwd, rev and und; "no path" counted
separately (share). Reported per key source.
