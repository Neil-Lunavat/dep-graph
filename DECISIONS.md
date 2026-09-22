# DECISIONS — the ledger

Mirrors the ROADMAP ledger, plus D16–D26 from RUNBOOK section 7, plus gap (G) applications
and working choices made by Claude Code. Neil's decisions are the only ones that settle a D.
Claude Code's working choices are listed separately so Neil can overrule any of them.

## Research decisions

| # | Decision | Status | Resolution | Date | Reason |
|---|---|---|---|---|---|
| D1 | Language scope | Settled | Python only | (roadmap) | |
| D2 | Graph granularity | Settled | File-level nodes | (roadmap) | |
| D3 | Edge types | Settled | Import edges only | (roadmap) | |
| D4 | Method input | Settled | One target file | (roadmap) | |
| D5 | Method output | Settled | Ordered list of files | (roadmap) | |
| D6 | Objective | Settled | Reduce reading/context cost of reaching the files a change required | (roadmap) | |
| D7 | LLM role | Settled | Evaluation only, never inside the method | (roadmap) | |
| D8 | Human study | Settled | Out of scope | (roadmap) | |
| D9 | Graph builder + Appendix A rules | **Decided (delegated)** | Custom `ast` builder (`src/depgraphs/graph/ast_builder.py`). Rules: `import a.b.c` → edge to the deepest existing module only, no extra edges to parent `__init__` (parent_inits=False); `from pkg import name` → `pkg.name` if it is a module, else `pkg/__init__.py` (as written, no re-export chasing); repeated imports count once (unweighted); `TYPE_CHECKING` and function-level imports kept; `.py` files not importable by name are not nodes (counted); test files are not nodes (D18) | 2026-09-22 | On all 4 comparison repos it gave exactly grimp's and tree-sitter's edges (independent tools), while also covering files outside packages and counting every Appendix B construct; "as written" rules keep the graph to imports actually typed, with no inferred edges |
| D10 | Repository sample (rules R1–R5, K, strata, n, seed) | **Decided (delegated)** | K=10; R2/R3 variant b; take every repo that passes (no draw of repos); at most 20 tasks (PRs) per repo, drawn by seed; domain list as proposed; archived and monorepo-flagged repos kept (no rule excludes them) | 2026-09-22 | RQ2 needs as many repos as possible (power table); variant b counts stubs/Cython as Python and `test/` as a test folder, which is what the rules are for; the 20-task cap keeps every repo but cuts test-box downloads by ~65% |
| D11 | Task source | **Decided (delegated)** | D: SWE-bench as a fixed comparability block + SWE-bench-Live + SWE-rebench | 2026-09-22 | Only option giving RQ2 ~100 repos while keeping a SWE-bench block; newer tasks usable in Step 10 |
| D12 | Primary vs validation key sources | **Decided (delegated)** | Primary key = union of co-edited + symbol + execution (D20 rule B). Every result is also reported per source (N4). If the execution run does not cover all PRs, the primary key for the uncovered PRs is co-edited + symbol, and the execution source is reported on its (random) subset only | 2026-09-22 | Three independent kinds of evidence; symbol overlaps the import graph by construction, so per-source reporting is mandatory |
| D13 | Cost unit, budget grid, seed cost | **Decided (delegated)** | Primary cost = physical lines of each listed file. Secondary: files, and tokens (tiktoken `o200k_base`). Budget grid (lines) = 250, 500, 1k, 2k, 4k, 8k, 16k, 32k; AUC = mean coverage over the grid (equal weight per doubling). Seed's own cost is not counted (same for all methods; the seed is never in a list) | 2026-09-22 | Lines are model-independent and simple; a doubling grid covers small and huge repos with one scale |
| D14 | Statistical tests, effect sizes, correction | **Decided (delegated)** | Unit = PR (tasks averaged within PR). Each method vs random floor and pairwise between methods: Wilcoxon signed-rank + Vargha–Delaney A12, Holm correction within each family. All methods over repos: Friedman + Nemenyi on per-repo means. RQ2: Spearman per pre-listed (Table 1 metric, method) pair across repos, Benjamini–Hochberg, labelled exploratory, every pair reported. 95% CIs by bootstrap resampling repos (2,000 resamples, seed 20260922) | 2026-09-22 | Standard for paired, non-normal SE data (Demšar 2006; Arcuri & Briand 2014) |
| D15 | Model, repetitions, budget, spend (Step 10) | Open — Gate G | | | |
| D16 | Which RQs are in this paper | **Decided (delegated)** | RQ1–RQ4 in; RQ5 in if the Gate G budget is approved; RQ6 deferred | 2026-09-22 | RQ1–RQ4 stand alone and cost nothing; RQ5 is the practical check; RQ6 needs separate proof checking |
| D17 | Graph per task commit vs one pinned commit | **Decided (delegated)** | One graph per task base commit (cached by commit). Table 1 at the pinned SHA, plus a summary across task commits | 2026-09-22 | G1 correctness (files must exist at the task's commit); cheap: 94% of tasks have their own commit and a graph takes 0.1–30 s |
| D18 | Role of test files | **Decided (delegated)** | Study test rule = 9.2 rule + folders named `test` (`is_test_path`). Test files are not graph nodes, cannot be seeds, and are never in the answer key; the file-count filter counts non-test files only | 2026-09-22 | The task is changing source files; SWE-bench-style datasets already separate tests into `test_patch`; one rule used everywhere |
| D19 | File-count filter (2–10 vs 1–10), line cap, what the cap counts | **Decided (delegated)** | 1–10 non-test `.py` files; single-file and multi-file tasks reported separately everywhere; cap 200 changed lines, counted on non-test `.py` files only | 2026-09-22 | 66% of usable tasks are single-file and still have symbol + execution keys (G4); the cap changes counts by only 1–4%; counts the cap as 9.2 is written |
| D20 | What counts as "executed" | **Decided (delegated)** | Primary B: a file counts if a line inside a function/method body ran during a fail-to-pass test. Sensitivity C: B minus files that run in a do-nothing test. A (any line) reported only to show the N5 effect | 2026-09-22 | B removes import-time noise (N5); C additionally removes framework/fixture noise; both are measured |
| D21 | Tie-breaking and within-clump order | **Decided (delegated)** | Random with a fixed seed, averaged over 5 seeds (20260922+i, i=0..4), for every method | 2026-09-22 | Cannot favour any directory layout; cheap without a model |
| D22 | Adaptation specs (BM25, co-change, published approaches) | **Decided (delegated)** | Written in `paper/methods.md` before any run | 2026-09-22 | Structure-only adaptations (N8) |
| D23 | Embedding model | **Decided (delegated)** | `jinaai/jina-embeddings-v2-base-code` (Apache-2.0, 161M params, runs on CPU/laptop GPU); input = file text truncated to the model's 8,192-token window; query = seed file text | 2026-09-22 | Only candidate small enough to embed every file version at every task commit on available hardware |
| D24 | Freeze by git tag only, or also OSF | **Decided (delegated)** | Git tag `freeze-1` only | 2026-09-22 | No OSF account; the tag is timestamped and public with the repo |
| D26 | Wrong-seed sampling rule | **Decided (delegated)** | For d = 1, 2: uniform random among graph files at undirected distance exactly d from the true seed (seeded by SHA-256 of 20260922+task_id); if none exist, the task is counted as 'no file at distance d' for that condition. Random condition: uniform over all graph files except the true seed | 2026-09-22 | G14 proposal as written |

Sampling seed for D10: **20260922**. Set mechanically as today's date (YYYYMMDD), committed *before* the draw ran, so it was not chosen by looking at outcomes.

**Delegation (2026-09-22).** Neil: "I think you can go ahead and make the decisions … only on cases that are just straight up obscure ambiguous" ask. From here Claude Code decides, marks each "Decided (delegated)" with its reason, and asks only on genuinely ambiguous calls. Neil can overrule any of them; an overrule after results exist goes in `POSTHOC.md`.

## Gap applications (RUNBOOK section 6)

| Gap | Applied how | Date |
|---|---|---|
| G13 | Patch parser and test-path rule have unit tests with hand-computed answers (`tests/test_patches.py`) | 2026-09-22 |
| G16 | Machine and accounts check done in Step 0 (`reports/01-step0-1-2.md` §4) | 2026-09-22 |
| G18 | Duplicate tasks across datasets removed by key (repo, PR number); Pro has no PR number, so its key is (repo, base commit). First occurrence kept in order SWE-bench → SWE-Gym → SWE-bench-Live → SWE-rebench → Pro (`src/depgraphs/candidates.py`) | 2026-09-22 |
| G2 | Count of tasks that create new source `.py` files, per dataset (`results/step2/recount_9_2.csv`, column `pct_tasks_create_src_py`) | 2026-09-22 |

## Working choices by Claude Code (not decisions — Neil can overrule any)

| Date | Choice | Why | What it affects |
|---|---|---|---|
| 2026-09-22 | Python 3.12 (uv-managed), dependencies pinned in `uv.lock` | Widest library support among current Pythons | Nothing in the research design |
| 2026-09-22 | Entry point is `python run.py all` (plus a `Makefile` that calls it) | `make` is not installed on this Windows machine | Nothing in the research design |
| 2026-09-22 | Datasets pinned to Hugging Face revisions recorded in `src/depgraphs/datasets.py` and checksummed in `data/datasets/MANIFEST.json` | Reproducibility | All counts |
| 2026-09-22 | Downloaded SWE-rebench `filtered` split only, not the ~21k-task full split | RUNBOOK 9.1 lists `filtered` as the one with prebuilt images for every task | Pool of fresh repos; full split can be added if Neil wants it |
| 2026-09-22 | Recount uses the 9.2 rule exactly as written (line cap counted on the source patch only). This differs from how the original 9.2 numbers were computed — see check-in 01 §5 | RUNBOOK rule 4: recount, don't copy | Eligible counts; raised as part of D19 |
| 2026-09-22 | Candidate pool for Gate A = repos with ≥10 eligible tasks under the widest option (1–10 files, 200-line cap), R1 datasets only, after G18 dedup. Narrower options are subsets | So every option at Gate A has real numbers behind it | Only what is measured; nothing is selected |
| 2026-09-22 | R2/R3 measured at a **provisional** snapshot = base commit of each repo's newest eligible task (Pro: newest by commit date) | 9.4 needs a snapshot to measure; D10 pins the real one | Only the R2/R3 numbers in `data/candidates.csv` |
| 2026-09-22 | R2 definition used for measuring: Python code lines ÷ code lines in a fixed list of programming-language extensions (`CODE_EXT` in `candidates.py`), non-test and non-vendored files only, counted with pygount 3.2.0 | 9.4 asks for one fixed tool, recorded | R2 outcome per repo |
| 2026-09-22 | Gate B prep: custom `ast` builder has one switch per open Appendix A rule. The "parent inits" switch covers `from a.b import x` as well as `import a.b.c`, because Python runs parent `__init__.py` files for both. Default switch values are placeholders for tests only — D9 sets the real ones | Seen on anyio: pydeps' extra edges were all parent `__init__` edges from from-imports; a switch limited to `import a.b.c` would have done nothing there | Only Gate B comparison numbers |
| 2026-09-22 | Gate B builder comparison repos chosen by rule: the passing repo with fewest non-test `.py` files from SWE-bench (pytest-dev/pytest, 89) and from the other datasets (cekit/cekit, 50; tie with django-rest-framework-json-api broken by name). I first ran seaborn and django-rest-framework-json-api by mistake (picked from memory, not by the rule); their results are kept and labelled as extras, not deleted | N7 spirit: picks by rule, not by judgement | Only Gate B comparison numbers |
| 2026-09-22 | R2 "variant b" measured alongside the rule as written (`.pyi/.pyx/.pxd/.pxi` count as Python; `test/` is a test folder; `cextern` is vendored). Not applied — offered in D10 | Several R2 failures came from definitions, not from non-Python code (mypy stubs, sqlfluff `.sql` test fixtures, astropy bundled C) | Which repos pass R2/R3 (7 flips) |
| 2026-09-22 | Graph discovery: `.py` files that cannot be imported by name (folders like `my-example/`), hidden folders, duplicate module names are not nodes and are **counted** per reason | Appendix B: handle or count; never drop silently | Node counts; D9 at Gate B decides whether to keep this |
| 2026-09-22 | "Vendored" = any path directory in {vendor, vendored, _vendor, third_party, thirdparty, 3rdparty, extern, externals, external}; "generated" = a marker (generated by / do not edit / autogenerated / @generated) in a file's first 5 lines | Needs a mechanical rule for the 30% exclusion | Exclusion flag only |
