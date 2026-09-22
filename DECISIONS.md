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
| D9 | Graph builder + Appendix A rules | Open — Gate B | | | |
| D10 | Repository sample (rules R1–R5, K, strata, n, seed) | Open — Gate A | | | |
| D11 | Task source | Open — Gate A | | | |
| D12 | Primary vs validation key sources | Open — Gate C | | | |
| D13 | Cost unit, budget grid, seed cost | Open — Gate E | | | |
| D14 | Statistical tests, effect sizes, correction | Open — Gate E | | | |
| D15 | Model, repetitions, budget, spend (Step 10) | Open — Gate G | | | |
| D16 | Which RQs are in this paper | Open — Gate A | | | |
| D17 | Graph per task commit vs one pinned commit | Open — Gate B | | | |
| D18 | Role of test files | Open — Gate B | | | |
| D19 | File-count filter (2–10 vs 1–10), line cap, what the cap counts | Open — Gate A | | | |
| D20 | What counts as "executed" | Open — Gate C | | | |
| D21 | Tie-breaking and within-clump order | Open — Gate E | | | |
| D22 | Adaptation spec for BM25, co-change, published approaches | Open — Gate E | | | |
| D23 | Embedding model | Open — Gate E | | | |
| D24 | Freeze by git tag only, or also OSF pre-registration | Open — Gate E | | | |
| D26 | Wrong-seed sampling rule | Open — Gate E | | | |

Sampling seed for D10 (Neil writes it here): **(not yet set)**

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
