# Table 1 — repository structure metrics (fixed before computing)

Fixed 2026-09-22, before any Table 1 value was computed (ROADMAP Step 4 constraint).
Source list: ROADMAP Appendix C. Nothing is added or removed after values exist; any change
goes to `POSTHOC.md`.

Graph G = (V, E): the D9/D18 import graph of one repository at one commit. V = importable
non-test `.py` files; E = directed import edges (unweighted, no self-loops).
N = |V|, M = |E|. Undirected view G_u ignores direction. Condensation C = G with each strongly
connected component (SCC, "import loop") collapsed to one node.

Computed at each repository's pinned SHA (the Table 1 row) and, as a robustness summary, the
median over that repository's task commits (D17).

| # | Metric | Definition |
|---|---|---|
| 1 | files | N |
| 2 | import_edges | M |
| 3 | density | M / (N(N−1)) |
| 4 | indeg_mean, indeg_median, indeg_max, indeg_gini | in-degree distribution over V; Gini coefficient of in-degrees |
| 5 | outdeg_mean, outdeg_median, outdeg_max, outdeg_gini | same for out-degree |
| 6 | hub_share_top5pct | share of edges whose target is among the top ⌈0.05·N⌉ files by in-degree (ties broken by path) |
| 7 | n_loops | number of SCCs with ≥ 2 files |
| 8 | largest_loop, largest_loop_share | files in the largest SCC; divided by N |
| 9 | share_in_loops | files in any SCC of size ≥ 2, divided by N |
| 10 | depth_condensed | number of edges on the longest path in C |
| 11 | spl_mean, spl_max | mean and maximum directed shortest-path length over ordered pairs (u, v), u ≠ v, with v reachable from u |
| 12 | n_wcc, largest_wcc_share | weakly connected components; largest one's size / N |
| 13 | isolated, isolated_share | files with in-degree = out-degree = 0; / N |
| 14 | modularity, n_clusters | Louvain on G_u (networkx `louvain_communities`, resolution 1, seed 0); modularity of that partition; number of communities |
| 15 | clustering | average clustering coefficient of G_u |
| 16 | single_importer_share | files with in-degree exactly 1, divided by N |
| 17 | nesting_max, nesting_mean | directory depth of each file path (number of `/`) |
| 18 | unresolved_share | unresolved internal import statements / internal import statements |
| 19 | loc_total, loc_mean, loc_median | physical lines per file in V |

Undefined cases: for N < 2 density is reported as NaN; spl_* are NaN when no pair is reachable.
