# Problem statement and research questions — DRAFT for D16

Status: draft by Claude Code, 2026-09-22. Scope is decided by Neil in D16. Wording is Neil's to edit.

## Problem statement

A developer or an automated agent must change one file in a codebase they do not know.
What else must they read, and in what order, to reach the files the change required at the
lowest reading cost?

We study this for Python repositories, with a file-level import graph as the only structural
input (D1–D3). A *method* receives one target file (the seed) and returns an ordered list of
repository files (D4, D5). No method uses a language model (D7). A method is evaluated by how
quickly, in cumulative reading cost, its list covers an evidence-based relevant set: files the
change is known to have required (the answer key, a lower bound on the true set; ROADMAP 5d).

## Terms used below

- *Seed*: the target file given to the method.
- *Answer key* K(t): for task t, the union of co-edited, symbol-resolved and executed files
  (ROADMAP 5b), minus the seed and minus files created by the change (G2). Reported per source
  as well as the union (N4).
- *Coverage–cost curve*: for a list L and cost unit c, coverage(b) = |K ∩ prefix_b(L)| / |K|,
  where prefix_b(L) is the longest prefix of L whose cumulative cost is ≤ b. AUC is the
  normalised area under this curve over the budget grid (D13; formulas in `paper/metrics.md`).
- *Random floor*: the expected curve of a uniformly random ordering of all candidate files.
- *Cheat ceiling* (oracle): K ordered to minimise cost. A reference, never a method (G9).

## RQ1 — How do ordering methods differ in how quickly they cover the answer key?

**Question.** Given a seed file, how do existing ordering strategies (Appendix D) differ in the
reading cost needed to cover the answer key?

**Measurement.** Per task, per method: coverage–cost curve and its AUC in each cost unit (D13),
plus Acc@k, Top-N, MRR, MAP, NDCG, empty rate (Appendix E) for comparability only (N8). Each PR
contributes one value per method (tasks averaged within a PR; G11). Methods compared with a
paired test and effect size (D14), and each against the random floor and cheat ceiling.

**How it could come out negative.** No method's AUC differs from the random floor, or from the
trivial references (same-directory files, seed alone), by more than chance; or all methods
differ from each other by less than the pre-set smallest effect of interest. Both are reported
as null results.

## RQ2 — Do import-graph properties of a repository relate to which method performs best?

**Question.** Across repositories, do the pre-listed structural properties (Table 1, fixed in
Step 4 before any results) co-vary with per-repository method performance?

**Measurement.** Per repository: each method's mean PR-level AUC and each method's rank. For
every pre-listed (property, method) pair: Spearman correlation across repositories, with a
multiple-comparison correction (D14); every pair reported; labelled exploratory. Confidence
intervals by bootstrap over repositories.

**How it could come out negative.** No pair survives correction; or rank order of methods is
stable across repositories (so there is nothing for structure to explain). The number of
repositories bounds the power of this RQ; the minimum detectable correlation for the chosen
sample size is reported up front (see D10 card).

## RQ3 — How far are the answer-key files from the seed in the import graph?

**Question.** What is the distribution of import-graph distance between a seed and its
answer-key files?

**Measurement.** For every (seed, key file) pair: shortest-path length following import
direction, following reverse direction, and ignoring direction; plus the share of key files
with no path at all (G14). Reported per key source (N4) and per repository.

**How it could come out negative.** This RQ is descriptive; it has no "positive" answer. The
result that would most limit graph-based methods — a large share of key files with no path, or
at long distance — is reported as measured. Tasks are never filtered on distance (N6).

## RQ4 — How does performance change when the seed is wrong?

**Question.** How does each method's coverage–cost AUC change when the seed is replaced by a
file at undirected distance 1, distance 2, or a uniformly random repository file?

**Measurement.** Re-run RQ1 under the four seed conditions (wrong seeds drawn by the fixed rule
in D26). Report per-method change in AUC, with paired tests; relate the rate of change to Table 1
properties as in RQ2.

**How it could come out negative.** AUC does not change measurably under wrong seeds (the
methods are insensitive to the seed, which would itself question RQ1), or all methods change by
the same amount (no method is more robust).

## RQ5 — Holding the file set fixed, does order change the context budget a model needs?

**Question.** When a language model receives the first N tokens of an ordered list, does the
order change the smallest N at which it produces a patch that passes the task's tests?

**Measurement.** Test-pass rate per (method, budget N), with repetitions; controls: same file
set in scrambled order, and seed file alone (ROADMAP Step 10). Reported separately for tasks
before and after the model's training cutoff. Requires money and Docker (D15, Gate G).

**How it could come out negative.** Pass rate at each budget does not differ between an ordered
list and the same files scrambled; or does not rise with budget; or differs only on tasks that
predate the training cutoff (contamination).

## RQ6 — Under what graph conditions is an optimal bounded reading order computable?

**Question.** For the bounded-order problem (maximise key coverage within a budget, given the
graph and seed but not the key — or, in the oracle version, given the key), what is its
complexity, and does tractability depend on graph shape (e.g. trees vs. DAGs with shared
dependencies)?

**Measurement.** Formal definitions; proofs marked DRAFT until Neil checks them (G19); exact
optima on small graphs by exhaustive search; the gap between heuristics and the optimum on those
instances. Every claim labelled proved, empirical, or open (Step 11).

**How it could come out negative.** The problem is hard even on restricted shapes, or no
shape-based tractability boundary is found. Either is stated as found; an unproved conjecture
stays labelled a conjecture.

## Dependencies between RQs

- RQ3 needs only graphs and keys (Steps 3, 5). It is the cheapest RQ.
- RQ1 needs graphs, keys, methods and scoring (Steps 3–7).
- RQ2 needs RQ1 plus Table 1, and **many repositories** (D10).
- RQ4 needs RQ1 plus re-runs (Step 9); cost is compute only.
- RQ5 needs RQ1 plus Docker, an API key and a budget (D15).
- RQ6 is independent of the data, apart from the small-graph comparison.
