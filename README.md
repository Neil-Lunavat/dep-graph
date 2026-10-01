# What Belongs in an Agent's Context Window? — replication package

Code, data and results for the paper in `paper/paper.pdf`. Given the file a change starts
from, the study compares reading orders built from the import graph, from the issue text, and
from both, on 2,412 change tasks from 1,162 pull requests in 112 Python repositories.

Every table in the paper is generated from the result files, and every number quoted in the
prose is recomputed from them by a checker that fails if a sentence disagrees.

## Layout

| Path | What it holds |
|---|---|
| `paper/` | Manuscript (`paper.tex`, `paper.pdf`), bibliography, generated table rows (`tab_*.tex`), and the two prediction files committed before their data were scored |
| `src/depgraphs/` | The pipeline, one module per stage |
| `run.py` | Entry point: `python run.py <stage> ...` |
| `tests/` | Unit tests for the graph builder, patch parser, sampling, methods and redaction |
| `data/` | Sample, tasks, answer keys (`keys_static/`), import graphs (`graphs/`), issue bags |
| `results/` | Scores and statistics of the main study (`study2/`, `seedless/`), sampling tables (`step2/`), graph and task summaries (`step3/`, `step5/`), the builder comparison (`step3_prep/`) and the key-rebuild comparison (`key_rebuild/`) |
| `external/` | The seven unseen repositories: sample, keys, tasks, scores, prediction outcomes |
| `contextbench/` | The ContextBench tasks with the human-annotated key: same contents |
| `docs/` | Design record and change log (see below) |

## Check the paper against the results

Needs Python 3.12 and [uv](https://docs.astral.sh/uv/). Nothing is downloaded beyond the
locked dependencies.

```
uv sync
uv run --group dev pytest -q          # unit tests
uv run python run.py claims           # every number in the prose, against the result files
uv run python run.py checknums        # every qualitative claim, recomputed
uv run python run.py maketables       # regenerates paper/tab_*.tex; `git diff` should be empty
```

The statistics can be recomputed from the committed scores (`results/study2/rows.parquet`,
`curves.parquet`, `top.jsonl.gz`) without rebuilding anything:

```
uv run python run.py leakage ball analysis2 metric dense
uv run python -m depgraphs.seedless summarise
DEPGRAPHS_ROOT=external uv run python -m depgraphs.external_eval
DEPGRAPHS_ROOT=contextbench uv run python -m depgraphs.contextbench_eval
```

On a second machine this reproduces every result file; the only difference is the last
floating-point digit of some p-values in `results/study2/pairwise.csv`.

## Rebuild from scratch

`python run.py all` runs the main pipeline in order. The stages, grouped:

| Stages | What they do |
|---|---|
| `datasets` | Download the task datasets from Hugging Face at pinned revisions, with checksums |
| `recount envs candidates ghmeta r2_variant gate_a sample` | Apply the sampling rules and fix the repository and task sample |
| `graphs keys_static tasks` | One import graph per base commit; the co-edited and symbol keys; one task per seed file |
| `lexfeat issues redact features` | Identifier bags per file, issue bags, the three redaction arms, per-file definitions and references |
| `study2` | Every reading order on every task, scored |
| `tokcost leakage ceiling ball analysis2 metric dense seedless` | Token calibration, issue-naming strata, ceilings, the two-hop ball, statistics, cost rules, the dense retriever's tests, the condition without a free seed |
| `maketables checknums claims` | Table rows for the paper, and the two checkers |
| `builders_prep` | The comparison of graph builders behind the choice of builder |

Two things run outside `run.py`:

- **Dense embeddings**, before `study2`, in their own environment (CPU `torch` and
  `sentence-transformers`, kept out of the lockfile): `python src/depgraphs/embed.py .`
  Without them `study2` scores every other ordering and `dense` stops with a message.
- **The external and ContextBench trees**, which run the same stages under `DEPGRAPHS_ROOT`:

```
python -m depgraphs.external
DEPGRAPHS_ROOT=external python run.py graphs keys_static tasks lexfeat issues redact
DEPGRAPHS_ROOT=external python -m depgraphs.study2
DEPGRAPHS_ROOT=external python run.py leakage ball
DEPGRAPHS_ROOT=external python -m depgraphs.external_eval

python -m depgraphs.contextbench prepare
DEPGRAPHS_ROOT=contextbench python run.py graphs keys_static tasks
DEPGRAPHS_ROOT=contextbench python -m depgraphs.contextbench addkey
DEPGRAPHS_ROOT=contextbench python run.py lexfeat issues redact
DEPGRAPHS_ROOT=contextbench python -m depgraphs.study2
DEPGRAPHS_ROOT=contextbench python -m depgraphs.contextbench_eval
```

A full rebuild clones 113 repositories and needs network access to Hugging Face, GitHub and
Docker Hub (image names are checked, nothing is pulled).

### What is shipped and what is rebuilt

Shipped: the sample, the answer keys, the tasks, the import graphs of the main study, the
issue bags and their redacted versions, per-task scores, top-100 orderings, and every
statistic. Not shipped, because the pipeline regenerates them: repository clones, dataset
files, identifier bags, per-file features, dense embeddings, and the graphs of the external
and ContextBench trees.

The symbol key is not bit-reproducible across environments: `jedi` resolves a few names
differently from one machine to another. `results/key_rebuild/` records the comparison made
on a second machine (41 of 1,886 pull requests differ, usually by one file; no AUC moves by
more than 0.003). The paper reports the keys as first built, which are the ones in
`data/keys_static/`.

## Build the paper

```
cd paper && tectonic paper.tex
```

Any LaTeX distribution with `acmart` works; the table rows are read from `tab_*.tex`.

## Where each table comes from

Rows are written by `src/depgraphs/maketables.py`. Files are under `results/study2/` unless a
path is given.

| Table | Rows | Source |
|---|---|---|
| 1 | in `paper.tex` | read from each system's paper; notes in `docs/ground_truth_notes.txt` |
| 2 | in `paper.tex` | the orderings defined in `study2.py` |
| 3 | `tab_main` | `per_source.csv` |
| 4 | `tab_dense_decomp` | `dense_tests.csv` |
| 5 | `tab_robust` | `per_source.csv`, `per_source_shared.csv`, `heldout.csv`, `metric_auc.csv`, `results/seedless/rows.parquet`, and both `predictions.json` files |
| 6 | `tab_external`, `tab_cb_pred` | `external/results/study2/predictions.json`, `contextbench/results/study2/predictions.json` |
| 7 | `tab_shared` | `per_source.csv`, `per_source_shared.csv` |
| 8 | `tab_leak` | `per_source_joint.csv` |
| 9 | `tab_redact` | `redaction.csv` |
| 10 | `tab_dense_auc` | `dense_auc.csv` |
| 11 | `tab_metric` | `metric_auc.csv` |
| 12 | `tab_seedless` | `results/seedless/rows.parquet` |
| 13 | `tab_cb_auc` | `contextbench/results/study2/per_source.csv` |
| 14 | `tab_heldout` | `heldout.csv` |
| 15 | `tab_distance` | `ball.csv`, `distance_profile.csv` |
| 16 | `tab_comp` | `complementarity.csv` |
| 17 | `tab_lines` | `lines_to_reach.csv` |
| 18 | `tab_full` | `ceiling_method.csv` |
| 19 | `tab_size` | `by_size.csv` |
| 20 | `tab_families` | `pairwise.csv`, `mixed.csv`, `redaction.csv` |
| 21 | `tab_mixed` | `mixed.csv` |

## Design record and change log

`docs/` holds what was fixed before any method ran, and everything that changed afterwards.

| File | What it is |
|---|---|
| `docs/metrics.md`, `docs/methods.md` | The metric and the method inventory as frozen at tag `freeze-1` |
| `docs/DECISIONS.md` | The ledger of design decisions (`D1`, `D2`, ... as cited in the code) |
| `docs/POSTHOC.md` | Every change made after results existed, and every bug fix |
| `docs/ROADMAP.md`, `docs/RUNBOOK.md` | The plan the study started from: steps, sampling rules (`RUNBOOK` 9.4), appendices cited in the code |
| `docs/rqs.md` | The research questions as first drafted; the paper's are narrower |
| `docs/ground_truth_notes.txt` | Notes behind Table 1, from each system's own paper |
| `docs/AI_USE.md` | Log of the AI assistance used |
| `paper/external_predictions.md`, `paper/contextbench_predictions.md` | Predictions committed before the data they concern were scored |

These documents were written while the work was in progress and name files by the paths they
had then. The study began as a broader comparison of thirty orderings on a union key; its code
and results are not part of this package but remain in the history at tag `pre-cleanup`, and
`docs/POSTHOC.md` records the reframing.
