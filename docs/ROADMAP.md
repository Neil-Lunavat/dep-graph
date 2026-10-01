# Research Roadmap — Reading Order over Python Import Graphs

## How to use this document

Each step below has: **Goal**, **Inputs**, **Do**, **Decide**, **Output**, **Done when**.

Work one step at a time. Say "do step N" and work through it collaboratively — every
step marked **Decide** needs a human call, not a default.

Do not skip ahead. Later steps depend on decisions recorded in earlier ones.

---

## Neutrality rule — read before every step

This is an open investigation. We do not know what the results are.

When executing any step:

- **Do not optimise toward an expected result.** No step exists to confirm a
  hypothesis. Each exists to produce a measurement.
- **A null result is a valid outcome and must be reported.** "No relationship
  between graph structure and which method wins" is a finding. "Ordering makes no
  difference to a model's success rate" is a finding. Neither is a failure.
- **Do not tune the pipeline after seeing results** unless the change is a
  correctness fix, and if you do, record what changed and re-run everything.
- **Do not discard tasks, repositories, or methods because they produce
  inconvenient numbers.** Filters are fixed in advance and written down.
- **Report the direction and size of every effect, including effects that go the
  wrong way.**

If at any point a step's instruction reads like "show that X," treat it as a
drafting error and rewrite it as "measure whether X."

---

## Decisions ledger

Keep this current. Every **Decide** resolved in any step gets recorded here with the
date and the reasoning.

| # | Decision | Status | Resolution |
|---|----------|--------|------------|
| D1 | Language scope | Settled | Python only |
| D2 | Graph granularity | Settled | File-level nodes |
| D3 | Edge types | Settled | Import edges only |
| D4 | Method input | Settled | One target file |
| D5 | Method output | Settled | Ordered list of files |
| D6 | Objective | Settled | Reduce the reading/context cost of reaching the files a change required |
| D7 | LLM role | Settled | Evaluation only, never inside the method |
| D8 | Human study | Settled | Out of scope |
| D9 | Graph builder tool | Open | Step 3 |
| D10 | Repository sample | Open | Step 2 |
| D11 | Task source | Open | Step 5 |
| D12 | Answer-key sources | Open | Step 5 |
| D13 | Budget units and grid | Open | Step 7 |
| D14 | Statistical tests | Open | Step 8 |
| D15 | Model and run count for the budget experiment | Open | Step 10 |

---

## Step 0 — Environment and repository skeleton

**Goal.** A reproducible workspace before any data is touched.

**Do.**
- Create a git repository with `src/`, `data/`, `results/`, `notebooks/`, `paper/`.
- Pin Python version and all library versions in a lockfile.
- Set up a single entry point (`make all` or `run.py`) that will eventually
  regenerate every result from scratch.
- Add a `DECISIONS.md` mirroring the ledger above.

**Output.** Empty but runnable pipeline.

**Done when.** A fresh clone installs and runs end to end with no data.

---

## Step 1 — Fix the question and the research questions

**Goal.** Write the problem statement and the RQs before any measurement, so
results cannot be retrofitted to whatever turns up.

**Do.**
Write the problem statement in one paragraph:

> Someone — a person or an automated agent — must change one file in a codebase
> they do not know. What else must they read, in what order, to reach the files the
> change actually required at the lowest reading cost?

Draft the research questions. Each must be answerable with a measurement and must
admit a negative answer. Working set:

- **RQ1.** Given a target file, how do existing strategies differ in how quickly
  their ordered output covers the files a change required?
- **RQ2.** Do measurable properties of a repository's import graph relate to which
  strategy performs best on it? If so, which properties, and how strongly?
- **RQ3.** How far, in graph distance, are the files a change required from the
  file being changed?
- **RQ4.** How does performance change when the starting file is wrong by one hop,
  two hops, or entirely?
- **RQ5.** Holding the file set fixed, does the order in which files are supplied
  change the context budget a language model needs to complete the change?
- **RQ6.** Under what graph conditions is an optimal bounded reading order
  computable?

**Decide.** Which RQs are in scope for this paper and which are deferred. Record in
the ledger.

**Output.** `paper/rqs.md`.

**Done when.** Every RQ has a stated measurement and a stated way it could come out
negative.

---

## Step 2 — Select repositories

**Goal.** A repository sample chosen by written rules, fixed before any results are
seen.

**Do.**
- Write the inclusion rules. Candidate criteria: primarily Python by line count,
  has a runnable test suite, minimum file count, active within the last N months,
  permissive licence.
- Write the exclusion rules: notebook-only projects, mostly generated code,
  vendored dependencies, monorepos containing unrelated projects.
- Sample to span a range of sizes and application domains. Record the sampling
  procedure, not just the outcome.
- Pin one commit SHA per repository.
- Record each repository's licence.

**Decide (D10).** How many repositories. Whether to include the 12 SWE-bench
repositories for comparability with prior work, an independent sample for
generalisation, or both.

**Constraint.** Selection rules must not reference graph structure or any expected
result. Size and domain are acceptable; "has few import cycles" is not.

**Output.** `data/repos.csv` — name, URL, pinned SHA, licence, size, domain.

**Done when.** Someone else could reproduce the sample from the written rules alone.

---

## Step 3 — Build the dependency graphs

**Goal.** One import graph per repository, built by one documented method.

**Do.**
- Evaluate candidate builders: `grimp`, `pydeps`, custom `ast`, `tree-sitter`.
  Compare their output on two small repositories.
- Apply the construction rules (Appendix A).
- Collapse import cycles into single nodes (Tarjan) and keep a mapping from
  collapsed node back to member files.
- Count every Python import construct the builder cannot resolve (Appendix B). Do
  not silently drop them.
- Hand-check 20 files per repository against the builder's output.

**Decide (D9).** Which builder, and why. Record the disagreements found during the
comparison.

**Output.** `data/graphs/<repo>.json` — nodes, edges, cycle groups, unresolved
import log.

**Done when.** The unresolved-import rate is measured and recorded per repository,
and the hand-check disagreement rate is known.

---

## Step 4 — Characterise each repository's graph

**Goal.** A fixed set of structural measurements per repository. This is the
independent variable for RQ2.

**Do.** Compute for every repository (Appendix C has the full list):
size, density, in/out-degree distributions, degree concentration, number and size
of cycle groups, depth, path lengths, connected components, modularity, cluster
count, share of files with exactly one importer, package nesting depth, lines of
code, unresolved-import share.

**Constraint.** Fix this list **before** running any experiment. Adding a metric
after seeing which one correlates is the definition of the error this rule prevents.

**Output.** `results/table1.csv` — one row per repository.

**Done when.** Every value is computed, none estimated. Flag any metric that could
not be computed and say why.

---

## Step 5 — Build the task set and the answer key

**Goal.** A set of tasks, each with a starting file and a set of files that the
change required, derived from evidence independent of the import graph.

This is the step the whole paper rests on. Do it slowly.

### 5a — Select tasks

Use **merged pull requests linked to exactly one issue**, not raw commits.

Mechanical filters, all fixed in advance:
- Linked to exactly one issue
- Touches between 2 and 10 Python files
- At least one test changes status
- Diff below a fixed line cap
- Excluded: merge commits, reverts, version bumps, formatting-only changes,
  dependency bumps, generated files, bot-authored commits

**Trap — do not filter on graph distance.** Excluding PRs whose touched files are
far apart in the graph removes exactly the cases where graph-based methods would
perform worst. Measure that distance instead and report it (this is RQ3).

**Decide (D11).** SWE-bench, Loc-Bench, an independent PR mining run, or a
combination. Trade-off: SWE-bench gives comparability with published numbers;
Loc-Bench and freshly mined PRs reduce the chance that a model has memorised the
answer.

### 5b — Build the answer key

Three independent sources. None derives from the import graph.

1. **Co-edited files.** Other Python files modified in the same PR.
2. **Symbol resolution.** For the lines the patch *added*, resolve each referenced
   name to the file defining it. Exclude standard library and third-party.
3. **Execution.** Run the tests that change status with coverage enabled and record
   which repository files execute.

Take the union. Record which source contributed each file, so the key can be
recomputed per source later.

### 5c — Validate the key

- Compute agreement between the static key (1 + 2) and the execution key (3) on a
  subset. Report the agreement rate. Disagreement is a result about the limits of
  static analysis, not a bug to hide.
- Optionally have a language model independently produce a key on a sample and
  report agreement, treating it as a second annotator, never as truth.
- Hand-check 30 to 50 tasks yourself. Record how many are impure (bundling
  unrelated work) and how many have keys you disagree with.

### 5d — State what the key cannot capture

The key contains files with evidence attached. It will miss files a developer read
but never touched, and files affected transitively without appearing in any of the
three sources. It is therefore a **lower bound**, not a complete set.

This is why scoring is by *rank position* and not by set equality: a method is never
penalised for listing files outside the key, only charged for their reading cost
(Step 7).

### 5e — Seeding

A PR touching k files yields k tasks — each file in turn is the start, the rest of
the key is the target. Tasks from the same PR are not independent; group by PR in
all statistics.

**Decide (D12).** Which sources form the primary key, which form the validation key.

**Output.**
- `data/tasks.jsonl` — task id, repo, base SHA, seed file, key files, key sources,
  graph distances
- `results/key_agreement.csv`
- `results/manual_audit.csv`

**Done when.** The agreement rates and manual audit numbers exist and are recorded,
whatever they say.

---

## Step 6 — Generate ordered lists

**Goal.** Every method produces the same shape of output from the same input, so
they are comparable.

**Interface.** `method(graph, seed_file) -> ordered list of files`. No method sees
the answer key. No method uses a language model.

**Do.** Implement the inventory in Appendix D: traversals, closures and
neighbourhoods, cycle handling and topological orders, ranking methods, clustering
methods, retrieval baselines, co-change, and re-implementations of published
approaches.

For co-change, use only commits **before** the task's base commit. Any use of later
history is leakage and invalidates the run.

Record for every method: wall-clock runtime, list length, total lines.

**Decide.** Tie-breaking rule between files at the same level, and ordering rule
within a collapsed cycle group. Both must be fixed and identical across methods, or
the comparison measures tie-breaking rather than method.

**Output.** `results/lists/<method>/<task>.json`.

**Done when.** Every method runs on every task without error, and failures are
logged rather than silently dropped.

---

## Step 7 — Score the lists

**Goal.** A cost-versus-coverage curve per method per task, computed with no model
and no money.

**Do.**
- Walk down each ordered list accumulating reading cost.
- At each point, record how much of the answer key has been covered.
- Plot coverage against cost. Summarise with area under the curve.
- Also record, for comparability with published work: Acc@k, Top-N, MRR, MAP, NDCG,
  empty rate (Appendix E).
- Include the ordering checks: whether the output is a valid topological order, and
  its distance from one.

**Decide (D13).** Cost unit — files, lines, or tokens — and the grid of budgets.
Tokens are closest to the objective; lines are simpler and model-independent.
Consider reporting more than one.

**Constraint.** Fix the metric definitions before looking at results. Write the
formulas into `paper/metrics.md` first.

**Output.** `results/curves.parquet`, `results/summary.csv`.

**Done when.** Every method has a curve on every task, and the metric formulas are
written down.

---

## Step 8 — Relate structure to performance

**Goal.** Measure whether, and how strongly, repository structure relates to which
method performs best. The answer may be "not at all."

**Do.**
- Rank methods per repository. Record which method wins where, and by how much.
- Test whether the differences between methods are larger than chance, with an
  appropriate paired test and an effect size. Group by PR.
- Correlate each Table 1 property against each method's performance.
- Correct for multiple comparisons — you are testing many property/method pairs and
  some will look significant by chance. State the correction used.
- Answer RQ3: report the distribution of graph distance between seed and key files.
- Where one method wins on one repository and loses on another, examine those cases
  specifically and describe the mechanism, if one is visible.

**Decide (D14).** Statistical tests, effect size measure, and multiple-comparison
correction. Fix these before looking at p-values.

**Constraint.** Report every correlation computed, not only the ones that reached
significance. A pre-registered list of tested pairs prevents selective reporting.

**Output.** `results/structure_vs_performance.csv`, plots, and a written list of
observations — one line each, each traceable to a number.

**Done when.** Every planned test has been run and recorded, including the ones
that came out null.

---

## Step 9 — Sensitivity to a wrong starting file

**Goal.** Measure how performance degrades when the seed is not the correct file.

**Do.**
- Re-run Step 6 and Step 7 with the seed replaced by: a file one hop from the
  correct one, two hops, and a randomly chosen repository file.
- Plot degradation per method.
- Check whether degradation rate relates to any Table 1 property.

**Output.** `results/sensitivity.csv` and plots.

**Done when.** All four seed conditions have been run for all methods.

---

## Step 10 — Budget experiment with a language model

**Goal.** Measure whether the order in which the same files are supplied changes the
context budget a model needs to complete the change. The answer may be "it does
not."

Run this only after Steps 1–9 are complete. Steps 1–9 stand alone as a result.

**Do.**
- For each task and method, take the first N tokens of the ordered list as context
  and ask the model to produce the change.
- Judge success by the repository's own tests, in the prepared environment.
- Sweep N across a grid.
- Repeat each configuration multiple times and report mean and spread, not a single
  run.
- Fix and record the prompt, temperature, and model version.
- Include a control: the same file set supplied in a scrambled order, and the seed
  file alone.

**Contamination.** Report results separately for tasks predating and postdating the
model's training cutoff. If the gap is large, the headline number is the postdating
one.

**Decide (D15).** Model, repetition count, budget grid, total spend.

**Constraint.** The model never selects or reorders anything. It only receives a
list and attempts the change.

**Output.** `results/budget_curves.parquet`, full prompt and response logs.

**Done when.** Every configuration has its planned repetitions and the variance is
reported.

---

## Step 11 — Formal analysis

**Goal.** State precisely what can be proved about ordering on dependency graphs,
and what cannot.

**Do.**
- Define formally: the graph, a reading order, reading cost, coverage, and the
  bounded-order problem.
- Investigate whether a valid reading order always exists once cycles are collapsed,
  and under what conditions.
- Investigate whether truncating an order preserves dependency closure, and in which
  direction.
- Investigate the complexity of computing an optimal bounded reading order, and
  whether tractability depends on graph shape (for instance tree-structured versus
  graphs with shared dependencies).
- On small instances, compute the true optimum by exhaustive or exact methods and
  measure how far the heuristics fall short.
- Separate clearly: results proved, results supported by data only, and open
  questions.

**Constraint.** Do not state a theorem the proof does not support. A conjecture
labelled as a conjecture is acceptable; a conjecture presented as a theorem is not.

**Output.** `paper/formal.md`.

**Done when.** Each claim is labelled proved, empirical, or open.

---

## Step 12 — Report

**Goal.** Write what was measured and what it showed, including what it did not show.

**Do.**
- State the answer to each RQ, with the number that answers it, including null
  answers.
- Table 1 (repository structure), the curve figures, the structure-versus-performance
  results, the sensitivity results, the budget results.
- Threats to validity (Appendix F).
- Limitations: Python only, imports only, static analysis only, lower-bound answer
  key, repository sample.
- Release the artifact: code, pinned SHAs, graphs, tasks, keys, raw outputs, prompts.

**Constraint.** The conclusion reports findings. It does not argue for a position
formed before the data existed. If the data does not support a claim in the
introduction, change the introduction.

**Done when.** Every figure traces to a file in `results/`, and every claim traces to
a figure.

---

# Appendices

## Appendix A — Graph construction rules

- Nodes are Python files.
- A directed edge from X to Y whenever X imports Y. The reverse direction is the
  same edge traversed backwards.
- Only imports resolving inside the repository count.
- Standard library imports dropped.
- Third-party imports dropped.
- Import cycles collapsed into one node each, with membership recorded.

Rules to decide and record in Step 3:
- Whether `import a.b.c` also creates edges to `a/__init__.py` and `a/b/__init__.py`
- Whether `from pkg import name` points to `pkg/__init__.py` or to the defining file
- Whether repeated imports of the same file count once or carry a weight
- Whether test files are nodes in the graph

## Appendix B — Python import constructs to handle or count

Absolute imports · from-imports · relative imports · star imports · `__all__` ·
re-exports through `__init__.py` · namespace packages · `src/` versus flat layout ·
function-level imports · `if TYPE_CHECKING:` blocks · `try/except ImportError` ·
version and platform conditionals · `importlib.import_module` with a string ·
`__import__()` · module-level `__getattr__` · entry-point plugins · name-based
registries · `sys.path` manipulation · aliased imports · submodule versus attribute
name collisions · files that fail to parse.

For each: handle it, or count its frequency per repository and report it.

## Appendix C — Repository structure metrics

Files · import edges · density · in-degree distribution · out-degree distribution ·
share of imports reaching the top-k hub files · number of cycle groups · largest
cycle group · share of files inside a cycle · depth after collapsing · mean and max
shortest path · weakly connected components · isolated files · modularity · cluster
count · clustering coefficient · share of files with exactly one importer · package
nesting depth · unresolved-import share · lines of code total and per file.

## Appendix D — Method inventory

**Traversal.** BFS · DFS · depth-limited search · iterative deepening ·
bidirectional · uniform-cost.

**Closure and neighbourhood.** Forward closure · reverse closure · combined closure ·
k-hop neighbourhood · closure trimmed from the far end to fit a budget.

**Cycles and order.** Tarjan · Kosaraju · condensation · Kahn's algorithm ·
DFS-based topological sort · transitive reduction · within-cycle ordering rule ·
tie-breaking rule.

**Ranking.** Degree centrality · PageRank · personalised PageRank from the seed ·
HITS · betweenness · closeness · Robillard's specificity and reinforcement adapted
to file level.

**Clustering.** Louvain · label propagation · directory structure as clusters ·
Bunch-style module clustering.

**Retrieval and history.** BM25 over file contents · one or more code embedding
models · co-change from pre-commit git history.

**Published approaches.** RepoGraph's k-hop ego-graph · LocAgent's type-aware BFS ·
CoSIL's module call graph traversal · Aider's budgeted ranking (read `repomap.py`
for the actual algorithm before implementing).

**Trivial references.** Random files · same-directory files · whole repository ·
seed file alone.

## Appendix E — Metrics

**Primary.** Coverage-versus-cost curve and its area under the curve.

**Cost axes.** Files read · lines read · tokens supplied · method runtime.

**Comparability with prior work.** Acc@k (all key files within top k) · Top-N (at
least one key file within top N) · MRR · MAP · NDCG · empty rate · odds ratio
against random selection.

**Ordering.** Valid topological order (pass or fail) · inversions or Kendall tau
against a valid order · rank of the first key file.

**Budget experiment.** Test-pass rate at each budget · variance across repetitions ·
tokens and cost per task.

Write each formula in `paper/metrics.md` before computing anything.

## Appendix F — Threats to validity

**Internal.** Parser errors and unresolved imports · answer key is a lower bound ·
tasks bundling unrelated work · non-independence of tasks from the same PR ·
model non-determinism · training-data contamination.

**External.** Python only · file granularity only · import edges only · static
analysis only · the chosen repository sample.

**Construct.** Whether coverage of the answer key stands in for comprehension ·
whether test-pass rate at a budget stands in for a person's reading effort ·
whether the cost axis reflects real reading cost.

**Conclusion.** Statistical power · multiple comparisons across many
property/method pairs · effect sizes reported alongside significance.

## Appendix G — Reproducibility

One public repository · pinned repository SHAs · pinned library versions · one
command regenerating every result · released graphs, tasks, keys, and raw outputs ·
released prompts and model settings · archived with a DOI · checked against the
venue's artifact badging requirements.
