# Methods — fixed before any run (D5, D21, D22; ROADMAP Step 6, Appendix D)

Written 2026-09-22, before any method was run on any task. Part of tag `freeze-1`.

## Interface

`method(context, seed) -> ordered list of files`, where `context` holds only what exists at the
task's base commit: the import graph G (D9/D17/D18), per-file lines, per-file identifier
bags, the def–ref graph (below), git history strictly **before** the base commit, and file
embeddings. No method sees the answer key, the PR, its tests, or the issue text. No method
uses a language model. The seed is never in a list. Lists contain graph nodes only.

**Sets to lists and ties (D21).** Whenever a method produces a set, or a ranking with ties,
the undecided order is a uniformly random permutation drawn with seed
`SHA-256("20260922" + str(i) + task_id)`, i = 0..4. Every method is run 5 times (i = 0..4) and
scores are averaged over the 5 runs. Methods with no ties give the same list each time.
Within an import loop (SCC), order is random by the same rule.

## Auxiliary structures (computed per base commit)

- **Def–ref graph R.** For each file: definitions = top-level `def`/`class` names and
  top-level assigned names, plus method names of top-level classes; references = every
  `ast.Name` id and `ast.Attribute` attr. Edge A → B (weight = number of distinct identifiers)
  if A references an identifier defined in B, A ≠ B. Identifiers defined in more than 5 files
  are ignored (too generic to link).
- **Call graph C ⊆ R.** Same, restricted to identifiers used as the callee of an `ast.Call`.
- **Identifier bag.** All identifiers in a file, split on `_` and camelCase boundaries,
  lower-cased, tokens of length ≥ 2.
- **History.** Commits reachable from the base commit's first parent line, strictly before it,
  from a blobless clone. Commits touching > 50 non-test `.py` files are ignored (bulk changes).

## Inventory

Directions: *fwd* = follow imports (files the seed imports), *rev* = against imports (files
that import the seed), *und* = ignore direction.

| # | Name | Family | Rule |
|---|---|---|---|
| 1 | `bfs_fwd` | traversal | BFS on G from seed, fwd; order by level, ties random |
| 2 | `bfs_rev` | traversal | same, rev |
| 3 | `bfs_und` | traversal | same, und |
| 4 | `dfs_und` | traversal | DFS preorder on G und; neighbour order random |
| 5 | `ids_und` | traversal | iterative deepening DFS, und, depth limits 1..∞; a file is listed the first time it is reached |
| 6 | `closure_fwd` | closure | set reachable fwd; random order |
| 7 | `closure_rev` | closure | set reachable rev; random order |
| 8 | `closure_comb` | closure | union of 6 and 7; random order |
| 9 | `khop1_und` | neighbourhood | files within 1 hop und; random order |
| 10 | `khop2_und` | neighbourhood | files within 2 hops und; random order |
| 11 | `closure_fwd_trim` | closure | `closure_fwd` ordered by fwd distance (near first), so truncating at any budget trims from the far end |
| 12 | `topo_fwd` | cycles/order | forward closure in dependency-first order: reverse topological order of the condensation (Kahn), clumps random inside, ties random |
| 13 | `pagerank` | ranking | all files by PageRank on G (α = 0.85), seed-independent |
| 14 | `ppr_und` | ranking | personalised PageRank on G und, restart at seed (α = 0.85) |
| 15 | `ppr_fwd` | ranking | personalised PageRank on G fwd, restart at seed |
| 16 | `indegree` | ranking | all files by in-degree |
| 17 | `hits_auth` | ranking | all files by HITS authority score |
| 18 | `betweenness` | ranking | all files by betweenness centrality on G (exact if N ≤ 1500, else 500 sampled sources, seed 0) |
| 19 | `closeness` | ranking | all files by closeness centrality on G und |
| 20 | `robillard` | ranking | greedy set expansion on G und. S = {seed}; repeatedly add the file x ∉ S maximising specificity(x) × reinforcement(x), where specificity = \|N(x)∩S\|/\|N(x)\| and reinforcement = \|N(x)∩S\|/\|S\| (Robillard 2008, adapted to files); stop when no x has a neighbour in S |
| 21 | `louvain` | clustering | files in the seed's Louvain community on G und (resolution 1, seed 0); random order |
| 22 | `labelprop` | clustering | files in the seed's label-propagation community on G und (networkx asynchronous LPA, seed 0); random order |
| 23 | `directory` | clustering | all files by folder-tree distance from the seed's folder (steps up to the common ancestor + steps down), nearest first; ties random. (Pre-run correction: a common-prefix rule could not separate same-folder files from others for seeds in the repo root.) |
| 24 | `bm25` | retrieval | BM25 (k1 = 1.5, b = 0.75) over identifier bags; query = seed's identifier bag; corpus = all other files; files with score > 0 |
| 25 | `embedding` | retrieval | cosine similarity of D23 embeddings (first 512 tokens of each file), seed vs every file; all files |
| 26 | `cochange` | history | score(x) = Σ over prior commits touching seed and x of 1/(files in commit − 1); files with score > 0 |
| 27 | `aider_repomap` | published (adapted) | Aider `repomap.py` idea with the seed as the only "chat file": personalised PageRank on R with personalisation on the seed, edge weight = √(identifier count) × 10 for identifiers ≥ 8 chars containing `_` or camelCase, × 0.1 for identifiers starting with `_`; files ranked by PageRank |
| 28 | `repograph_k1` | published (adapted) | RepoGraph ego-graph: search terms = the seed's definitions; files within 1 hop of the seed in R und; random order |
| 29 | `repograph_k2` | published (adapted) | same, 2 hops; ordered by hop, ties random |
| 30 | `locagent_bfs` | published (adapted) | LocAgent type-aware BFS without a model: BFS from the seed over the union of G und and R und; order by hop, then edge type (import < reference), then random |
| 31 | `cosil_bfs` | published (adapted) | CoSIL with a static module call graph instead of a model-built one: BFS from the seed over C und; order by hop, ties random |
| R1 | `random` | reference | uniform random permutation of all files (the random floor; 5 seeds like every method) |
| R2 | `same_dir` | reference | files in the seed's directory; random order |
| R3 | `whole_repo` | reference | all files in path order |
| R4 | `seed_alone` | reference | empty list |
| R5 | `oracle` | reference (uses the key) | key files, cheapest first; **labelled cheat ceiling, never a method** |

Structure-only adaptations (27–31) are never described as reproductions, and their numbers are
never placed beside the published ones (N8).

**Not implemented (decided before any run):** Bunch-style module clustering (Appendix D). No
maintained Python implementation exists, and a re-implementation of its search heuristic
would be a new method rather than Bunch. Excluded; this is noted as a limitation.

## Wrong seeds (Step 9, D26)

Same methods, with the seed replaced as D26 states. The answer key stays the one of the true
seed.
